# BusinessIntelligence.ai — Prototype Execution Plan

A step-by-step build guide for the Detect → Investigate → Judge → Act engine, ordered so each phase produces something runnable before the next begins.

---

## Phase 0 — Setup & Scaffolding

**Goal:** a running skeleton with no logic yet, just the plumbing.

1. Initialize repo structure:
   ```
   /data          -> seed CSVs / mock source systems
   /contracts      -> KPI semantic contract YAML files
   /pipeline       -> detect.py, investigate.py, judge.py, act.py
   /api            -> FastAPI app
   /web            -> React frontend
   /telemetry      -> logging + cost tracking
   ```
2. Stand up PostgreSQL (local Docker container is fine for a demo).
3. Stand up ChromaDB or FAISS for evidence retrieval.
4. Create a `.env` with Claude API key, DB connection string, model names (cheap model vs. main model).
5. Scaffold FastAPI app with a single health-check route; scaffold React app with a blank shell page.
6. Confirm: `docker compose up` brings up Postgres + vector store + API + web, all reachable locally.

---

## Phase 1 — Seed Data & Simulated Sources

**Goal:** 3–5 KPIs across 2–3 sources with different grains and cadences, per the brief's minimum expectations.

1. Build seed tables/CSVs simulating heterogeneous sources:
   - `revenue_daily` (by region) — simulates a warehouse table.
   - `support_tickets` (event-level, timestamped) — simulates Zendesk.
   - `marketing_spend_weekly` (by campaign) — simulates an ad-platform export.
   - `server_latency_hourly` — simulates a monitoring feed.
   - `churn_monthly` — simulates a CRM export.
2. Inject the demo scenarios directly into the seed data so they're reproducible:
   - A payment-gateway outage: a revenue drop in one region + a ticket spike in the same 15-minute window.
   - A slow structural decline: a 30-day gradual dip with no single trigger.
   - An unconfirmed case: a latency blip correlated with a revenue dip but with no ticket/log evidence.
   - A sparse-history KPI: a newly launched product/region with under 8 weeks of data.
3. Load seed data into Postgres; write a `load_seed.py` script so the demo is resettable.
4. Sanity check: query each table directly and confirm grain/cadence differences are visible (e.g. daily vs weekly vs event-level timestamps).

---

## Phase 2 — KPI Semantic Contract

**Goal:** the lightweight metadata layer that lets later stages reconcile sources without hardcoding joins.

1. Design a YAML schema per KPI covering: `name`, `definition`, `calculation` (SQL snippet), `source_table`, `grain`, `calendar`, `refresh_cadence`, `known_drivers`, `materiality_threshold`, `lineage`, `access_restrictions` (roles/rows/columns).
2. Write one contract file per KPI (5 files) under `/contracts`.
3. Write a `contract_loader.py` that parses all contracts into a registry object the pipeline can query (e.g. `registry.get("revenue").grain`).
4. Write a `reconcile.py` that, given two KPI contracts, resamples/aligns them onto a common calendar and grain (e.g. resample hourly latency to daily to compare against daily revenue).
5. Test: pick any two KPIs with different grains and confirm `reconcile.py` returns a joined, calendar-aligned dataframe.

---

## Phase 3 — Detect (Stage 1)

**Goal:** a script that ingests the metric table and outputs a ranked list of material anomalies. No LLM calls in this phase.

1. Implement rolling baseline calculation (mean + std dev, trailing 8–12 weeks) per KPI, using the contract to know the correct grain/calendar.
2. Implement seasonality adjustment (day-of-week / month-end decomposition) so expected recurring dips aren't flagged.
3. Implement the statistical threshold (z-score ≥ 2 by default, configurable per KPI).
4. Implement the business-materiality threshold (min $ or % impact, from the contract).
5. Implement the sparse-history fallback: if a KPI has under 8 weeks of history, fall back to a category/cohort-level baseline and widen the confidence interval; flag output as `low_history_estimate: true`.
6. Output a prioritized `anomalies.json`: KPI, timestamp, magnitude, materiality score, statistical significance, history flag.
7. Test: run against the seed data and confirm the payment-outage scenario and the sparse-history scenario both surface correctly, and that a normal Monday dip does *not* surface.

---

## Phase 4 — Investigate (Stage 2)

**Goal:** for each anomaly from Phase 3, build the dynamic neighborhood, run correlation, and apply the evidence gate.

1. Implement `find_neighbors.py`: given an anomalous KPI, query the contract registry for all other KPIs, and compute lead-lag correlation (0–7 day lead window) between each candidate and the anomaly.
2. Implement the evidence retrieval layer: index support tickets, logs, and campaign notes into ChromaDB/FAISS as embeddings.
3. Implement the evidence gate: for each correlated candidate, query the vector store for corroborating evidence in the relevant time window; accept the candidate only if both the correlation *and* the evidence check pass.
4. Implement the small-model text triage call: classify retrieved free-text evidence for relevance (e.g. "is this ticket about payments?") using the cheap Claude model — first real LLM call in the pipeline.
5. Implement price/volume/mix decomposition for composite KPIs (deterministic formula, no LLM).
6. Implement a causal-comparison check (difference-in-differences) for cases where a valid control group exists (e.g. one region ran a campaign, a similar region didn't).
7. Output `candidates.json` per anomaly: each candidate driver with correlation strength, evidence records, contribution %, and causal estimate where applicable.
8. Test: confirm the outage scenario returns the ticket-spike candidate as evidence-gated "accepted," and the latency-only scenario returns "correlated only — rejected."

---

## Phase 5 — Judge (Stage 3)

**Goal:** classify each anomaly's candidate set into a confidence track, and implement abstention.

1. Implement the scoring rule for each track (Acute / Structural / Unconfirmed / External) based on evidence count/quality, correlation strength, and temporal proximity.
2. Implement the minimum-confidence floor: if no track's score clears the floor, output `abstain: true` with a clarifying question instead of a forced explanation.
3. Implement the LLM phrasing call: given the locked score + evidence bundle, ask the model to produce a calibrated confidence caveat sentence. Guardrail — validate the LLM output never contains a different track name or score than what was computed.
4. Output `judged.json`: anomaly, track, score, phrased caveat, abstain flag.
5. Test: confirm all four demo scenarios (acute, structural, unconfirmed, external/abstain) produce the correct track and that the abstention scenario correctly triggers a clarifying question instead of a narrative.

---

## Phase 6 — Act (Stage 4)

**Goal:** turn judged output into persona-specific narratives and actionable, human-approved recommendations.

1. Build the lever library: a business-rules table of controllable levers, owners, and permissible actions per KPI/driver type.
2. Implement persona prompt templates (start with two: CFO/Finance and Regional Ops Manager) that take the same evidence bundle and produce differently-framed narratives.
3. Implement the action-recommendation generator: populate driver → lever → action → expected impact → owner → confidence → monitoring plan from the lever library, phrased by the LLM.
4. Implement the RBAC entitlement check before any data reaches a prompt: Regional Ops Manager sees only their region's rows and no PII columns; CFO sees company-wide aggregates but not individual customer records.
5. Build the Review & Authorize UI flow: narrative + recommended action + a button that logs an approve/edit/reject decision — no auto-execution path exists anywhere in the code.
6. Implement feedback logging: every decision (and any edits to the narrative/action) is written to a `feedback` table with a diff of what changed.
7. Test: confirm the same anomaly produces two visibly different narratives for the two personas, and that a Regional Ops Manager query never returns cross-region or PII data even if asked.

---

## Phase 7 — Feedback Loop & Recalibration

**Goal:** close the loop so Detect/Judge improve from logged decisions.

1. Write a scheduled job (`recalibrate.py`) that reads the `feedback` table and adjusts: Detect's materiality thresholds (if analysts consistently dismiss certain anomaly sizes) and Judge's confidence weights (if analysts consistently override a track's confidence).
2. Add a simple report showing edit patterns (e.g. "confidence phrasing softened in 6 of last 10 Structural-track cases") to make drift visible before it's auto-applied.
3. Test: manually inject a batch of "reject, too sensitive" feedback records and confirm the next `recalibrate.py` run raises the materiality threshold accordingly.

---

## Phase 8 — API & Orchestration

**Goal:** wire Phases 3–7 into a single FastAPI service the frontend can call.

1. Build `/pipeline/run` endpoint: triggers Detect → Investigate → Judge → Act in sequence for the current data window, writing intermediate JSON to the DB at each stage for auditability.
2. Build `/insights` endpoint: returns judged + acted insights, filtered by the caller's persona/entitlement (enforced server-side, not client-side).
3. Build `/insights/{id}/decision` endpoint: records approve/edit/reject from the Review & Authorize UI.
4. Wrap every LLM call with the telemetry logger (Phase 9) so latency/tokens/cost are captured automatically, not bolted on later.
5. Test: call `/pipeline/run` end-to-end against seed data and confirm insights appear via `/insights` with the correct persona filtering.

---

## Phase 9 — Telemetry & Cost Governance

**Goal:** the auditable cost/latency/model-call record the brief requires.

1. Create a `telemetry` table: insight ID, stage latencies, LLM model calls, tokens in/out, LLM latency, estimated cost, confidence track.
2. Wrap each LLM call (triage, phrasing, narrative synthesis, action drafting) to log to this table automatically.
3. Add caching: cache evidence-retrieval and correlation results per anomaly window so repeated persona requests for the same insight don't recompute or re-call the LLM.
4. Add a small dashboard panel (or API endpoint) summarizing cost-per-insight and total spend for the demo run.
5. Test: run the pipeline twice on the same window and confirm the second run hits cache and shows near-zero incremental LLM cost.

---

## Phase 10 — Frontend

**Goal:** a usable UI covering the full demo script.

1. Build the insight feed view: list of judged insights, persona-filtered, with confidence-track badges.
2. Build the insight detail view: narrative, evidence drill-down (source freshness, method used, contribution %, lineage path), and the Review & Authorize action card.
3. Build the abstention view: clarifying-question prompt for low-confidence cases, with a way for the analyst to supply the missing context.
4. Build a lightweight persona switcher (for demo purposes) to show the same underlying event through both personas.
5. Build a telemetry/cost panel showing per-insight cost and latency.
6. Test: walk through the full demo script end-to-end in the UI (see Phase 11).

---

## Phase 11 — End-to-End Demo Script (Validation)

**Goal:** confirm every minimum prototype expectation from the brief is demonstrably working.

1. Run `/pipeline/run` on the seeded window.
2. Show the multi-factor scenario: Southeast revenue drop with both an Acute (outage) and Structural (seasonal) component reported together.
3. Show the abstention scenario: latency-correlated, evidence-gate-failed case triggering a clarifying question.
4. Show the sparse-history scenario: newly launched KPI flagged as a low-history estimate with a wider interval.
5. Show the security scenario: log in as Regional Ops Manager, confirm no cross-region/PII data is visible; switch to CFO, confirm company-wide but not customer-level data.
6. Show both persona narratives for the same underlying insight side by side.
7. Show the evidence drill-down (freshness, method, contribution, confidence, lineage) for at least one insight.
8. Show the LLM vs. non-LLM breakdown live — e.g. print which calls in the run were LLM vs. deterministic.
9. Show the telemetry panel with real latency/token/cost numbers from the run.
10. Approve one recommendation and reject another; show both land in the `feedback` table and that a subsequent `recalibrate.py` run reflects the rejection.

---

## Suggested Build Order Summary

| Order | Phase | Depends on |
|---|---|---|
| 1 | Setup & Scaffolding | — |
| 2 | Seed Data & Simulated Sources | 1 |
| 3 | KPI Semantic Contract | 2 |
| 4 | Detect | 3 |
| 5 | Investigate | 4 |
| 6 | Judge | 5 |
| 7 | Act | 6 |
| 8 | Feedback Loop & Recalibration | 7 |
| 9 | API & Orchestration | 4–8 (wraps them) |
| 10 | Telemetry & Cost Governance | 9 (wraps LLM calls) |
| 11 | Frontend | 9 |
| 12 | End-to-End Demo Validation | 10, 11 |
