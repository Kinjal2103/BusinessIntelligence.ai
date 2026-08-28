# AGENTS.md — BusinessIntelligence.ai

This file gives an AI coding agent (Antigravity, Claude Code, or similar) the full context needed to start building this project without re-deriving the design from scratch. Read this before writing any code.

---

## 1. What this project is

**BusinessIntelligence.ai** is a KPI intelligence-to-action engine built for a hackathon-style Round 2 submission. It explains *why* a business metric moved, ranks the likely drivers, states its confidence honestly (including abstaining when evidence is thin), and recommends a concrete next action — all narrated in plain English for a specific persona (e.g. CFO vs. Regional Ops Manager).

**Core principle — do not violate this:** the LLM is a narration/interpretation layer only. It is never the source of a number. Every anomaly score, correlation, contribution %, causal estimate, or confidence score must come from deterministic logic, SQL, statistics, or traditional ML. If you find yourself asking the LLM to "calculate" or "decide" a number, stop — that belongs in Python/SQL, not a prompt.

---

## 2. The four-stage pipeline

The whole system is organized around one pipeline, always in this order:

```
Detect → Investigate → Judge → Act
```

| Stage | Purpose | LLM involved? |
|---|---|---|
| **Detect** (the Sentinel) | Find statistically real, business-material anomalies in KPIs | No — pure statistics |
| **Investigate** (Dynamic Neighborhood + Evidence-Gated Loop) | Find candidate driver metrics, require BOTH correlation AND corroborating evidence before accepting a candidate | Minimal — small model only for free-text evidence triage |
| **Judge** (the Ambiguity Engine) | Classify the finding into a confidence track (Acute / Structural / Unconfirmed / External), or abstain if nothing clears the confidence floor | Only to phrase the (locked) score into a caveat sentence — never to change the score |
| **Act** (Storyteller + Human-in-the-Loop) | Generate a persona-specific narrative and a structured action recommendation; require human Review & Authorize before anything executes | Yes — narrative synthesis and action drafting |

Full detail on each stage's mechanism is in `docs/architecture_plan.docx` (already produced) — read that file if it's present in the repo before implementing a stage.

---

## 3. The eight objectives this system must satisfy

Every piece of code should trace back to one of these (from the official brief):

1. Detect and prioritise material KPI movements.
2. Reconcile data and business context across heterogeneous sources (different systems, grains, refresh cadences).
3. Identify and rank explanatory drivers using appropriate analytical methods.
4. Generate persona-specific narratives supported by traceable evidence.
5. Communicate uncertainty and abstain when evidence is insufficient or contradictory.
6. Recommend practical actions grounded in business levers, constraints, and decision rights.
7. Learn from analyst and business-user feedback.
8. Operate within realistic security, cost, latency, and scalability constraints.

---

## 4. Non-negotiable design constraints

- **No auto-execution, ever.** Every recommended action ends at a "Review & Authorize" button. There is no code path where the system acts on the business without a human click.
- **RBAC before prompts.** Row/column/domain security is enforced in the API/middleware layer, before any data is assembled into an LLM prompt. The LLM must never see data outside the caller's entitlement.
- **Evidence gate is an AND, not an OR.** A candidate driver metric is only accepted if it is BOTH statistically correlated with the anomaly AND backed by a corroborating evidence record (ticket, log, campaign flag). Correlation alone = "rejected, no evidence."
- **Confidence scores are locked before the LLM sees them.** The LLM may phrase a score, never invent or adjust one.
- **Abstention is a real code path**, not just a prompt instruction. If no confidence track clears the minimum floor, the pipeline must return `abstain: true` with a clarifying question — this must be testable/verifiable in code, not just "the LLM said it wasn't sure."
- **Every LLM call is telemetry-logged**: model, tokens in/out, latency, estimated cost, tied to the insight ID it supported.

---

## 5. Tech stack

| Layer | Technology |
|---|---|
| Storage / warehouse | PostgreSQL |
| Evidence retrieval | ChromaDB or FAISS (vector search) |
| Analytics | Python — Pandas, NumPy, statsmodels, scikit-learn |
| Language layer | Claude API (small/cheap model for triage & phrasing, stronger model for narrative synthesis) |
| Service layer | FastAPI |
| Interface | React |

---

## 6. Repository layout (target structure)

```
/data          -> seed CSVs simulating heterogeneous source systems
/contracts     -> one YAML file per KPI (the "semantic contract")
/pipeline      -> detect.py, investigate.py, judge.py, act.py, recalibrate.py
/api           -> FastAPI app (routes, RBAC middleware, orchestration)
/web           -> React frontend
/telemetry     -> LLM call wrapper + cost/latency logging
/docs          -> architecture_plan.docx, execution_plan.md, this file
```

---

## 7. The five demo KPIs (use these exact ones unless told otherwise)

| KPI | Simulated source | Grain | Cadence |
|---|---|---|---|
| Revenue (by region) | Warehouse | Daily | Nightly batch |
| Support ticket volume | Zendesk-style | Event-level | Real-time |
| Marketing spend (by campaign) | Ad-platform API | Weekly | Weekly |
| Server latency | Monitoring stack | Hourly | Hourly |
| Customer churn | CRM export | Monthly | Monthly |

The seed data must have these scenarios baked in, reproducibly:
1. **Acute case:** payment-gateway outage — revenue drop + ticket spike in the same 15-minute window, one region.
2. **Structural case:** a slow 30-day decline with no single trigger.
3. **Unconfirmed/abstention case:** latency correlated with a revenue dip, but no ticket/log evidence exists.
4. **Sparse-history case:** a newly launched product/region with under 8 weeks of data.

---

## 8. Build order

Follow `docs/execution_plan.md` if present — it lays out 12 phases in dependency order (Setup → Seed Data → Semantic Contract → Detect → Investigate → Judge → Act → Feedback Loop → API → Telemetry → Frontend → End-to-end validation). Don't skip ahead to the frontend or API orchestration before the four pipeline stages are individually testable in isolation — each stage should have its own runnable script and test before being wired into the API.

---

## 9. Two personas to support from day one

- **CFO / Finance:** financial-impact framing, board-ready summary, dollar/margin language. Sees company-wide aggregates, never individual customer records.
- **Regional Ops Manager:** operational root cause, immediate fix, local framing. Sees only their own region's rows, no PII columns.

Same evidence bundle, different prompt template and different data entitlement — never fork the underlying facts, only the framing and access.

---

## 10. Definition of done for the prototype

The system is demo-ready when a single pipeline run can show, live:
- A material anomaly detected and prioritised (Detect).
- A multi-factor movement with more than one contributing driver (Investigate + Judge).
- One abstention case where the system asks a clarifying question instead of guessing (Judge).
- One sparse-history case flagged as a low-confidence estimate (Detect).
- Two different persona narratives for the same underlying event (Act).
- A Review & Authorize action that logs a decision without auto-executing (Act).
- A role-based security scenario proving data isolation between personas (Act/API).
- An evidence drill-down showing source freshness, method, contribution %, confidence, and lineage for at least one insight (Act/API).
- A telemetry panel showing real token/latency/cost numbers, plus a clear list of which calls in that run were LLM vs. non-LLM (Telemetry).