import os
import json
import time
import psycopg2
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError
from telemetry.logger import log_llm_call

# Load env variables with explicit override
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=dotenv_path, override=True)

DB_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def get_connection():
    return psycopg2.connect(DB_URL)

def get_gemini_client():
    if not GEMINI_API_KEY or "your_gemini_api_key" in GEMINI_API_KEY or GEMINI_API_KEY == "your-api-key-here":
        raise ValueError("GEMINI_API_KEY is not configured in .env file!")
    return genai.Client(api_key=GEMINI_API_KEY)

def fetch_ticket_details(ticket_ids, conn):
    """Retrieve details for specific support tickets from Supabase."""
    if not ticket_ids:
        return []
        
    cursor = conn.cursor()
    # SQL IN clause
    sql = """
        SELECT ticket_id, category, priority, status, description, created_at
        FROM support_tickets
        WHERE ticket_id IN %s;
    """
    
    try:
        cursor.execute(sql, (tuple(ticket_ids),))
        rows = cursor.fetchall()
    except Exception as e:
        print(f"Failed to fetch ticket details: {e}")
        rows = []
    finally:
        cursor.close()
        
    details = []
    for r in rows:
        details.append({
            "ticket_id": r[0],
            "category": r[1],
            "priority": r[2],
            "status": r[3],
            "description": r[4],
            "created_at": r[5].strftime("%Y-%m-%d %H:%M:%S")
        })
    return details

def generate_report_narrative(client, incident, levers, conn):
    """Call Gemini 2.5 Flash to synthesize the final narrative report, logging telemetry."""
    anomaly = incident["anomaly"]
    region = anomaly["region"]
    kpi = anomaly["kpi"]
    timestamp = anomaly["timestamp"]
    actual = anomaly["actual"]
    baseline = anomaly["baseline_mean"]
    pct_change = anomaly["pct_change"]
    abs_change = anomaly["absolute_change"]
    
    insight_id = f"INC-{region[:3].upper()}-{timestamp[:10].replace('-', '')}"
    
    # Check if this is an abstention case (low confidence)
    if incident.get("abstain", False):
        print(f"[{region}] Incident is flagged as ABSTAIN. Skipping LLM narration, using direct template.")
        # Return deterministic abstention report without making LLM calls
        return {
            "incident_id": insight_id,
            "title": f"Unconfirmed Incident in {region} Region",
            "severity": "Medium",
            "executive_summary": f"A potential revenue anomaly was detected in the {region} region on {timestamp[:10]}. However, because no direct customer support tickets or error logs were found, we are abstaining from a final root-cause conclusion.",
            "business_impact": f"Revenue of ${actual:,.2f} represents a -{pct_change * 100:.1f}% drop (-${abs_change:,.2f}) from expected baseline of ${baseline:,.2f}.",
            "root_cause_analysis": f"The metric is mathematically correlated with server latency, but the Evidence Gate failed (0 customer support tickets matched). Clarifying Question: '{incident['clarifying_question']}'",
            "evidence_summary": "Evidence Gate failed. No matching billing outage tickets or SRE logs were found.",
            "recommendations": [
                "Investigate the SRE server performance logs for this period to see if there was an unlogged checkout failure.",
                "Review payment partner status dashboards to verify if billing callbacks were failing silently.",
                incident["clarifying_question"]
            ],
            "retrieved_tickets": [],
            "anomaly": anomaly,
            "drivers": incident["drivers"],
            "confidence_track": incident["confidence_track"],
            "confidence_score": incident["confidence_score"],
            "confidence_caveat": incident["confidence_caveat"],
            "abstain": True,
            "clarifying_question": incident["clarifying_question"]
        }

    # Identify corroborated driver
    corroborated_drivers = [d for d in incident["drivers"] if d["evidence_gate_passed"]]
    primary_driver = corroborated_drivers[0] if corroborated_drivers else incident["drivers"][0]
    
    driver_kpi = primary_driver["candidate"]
    corr = primary_driver["correlation"]
    lag = primary_driver["lag"]
    ticket_ids = primary_driver.get("evidence_tickets", [])
    
    evidence_details = fetch_ticket_details(ticket_ids, conn)
    tickets_text = ""
    for idx, t in enumerate(evidence_details):
        tickets_text += f"Ticket [{t['ticket_id']}] - Category: {t['category']} | Priority: {t['priority']}\n"
        tickets_text += f"Description: {t['description']}\n\n"
        
    # Get SRE/Business levers matching this driver
    candidate_levers = levers.get(driver_kpi, ["Investigate metric performance manually."])
    levers_text = "\n".join([f"- {l}" for l in candidate_levers])
    
    prompt = f"""
You are an expert BI narrative generation agent. You need to write two persona-specific incident reports based on the same anomaly data:
1. CFO / Finance Persona: framed around financial impact, board-ready summaries, margins, and dollar impact language.
2. Regional Ops Manager Persona: framed around immediate operational root causes, engineering checklists, and regional SRE action details.

Anomaly Details:
- Metric: {kpi} (Revenue drop)
- Region: {region}
- Date: {timestamp}
- Actual Value: ${actual:,.2f}
- Expected Baseline: ${baseline:,.2f}
- Absolute Drop: -${abs_change:,.2f}
- Percent Drop: -{pct_change * 100:.1f}%

Driver & Evidence:
- Correlated Driver: '{driver_kpi}' (r = {corr:.2f}, Lag: {lag} days)
- Customer support ticket logs:
---
{tickets_text}
---

Permissible Business & SRE Action Levers:
{levers_text}

Confidence Calibrations:
- Track: {incident['confidence_track']}
- Phrased Caveat: {incident['confidence_caveat']}

Respond in STRICT JSON format with these exact keys:
{{
  "incident_id": "{insight_id}",
  "severity": "Critical" | "High" | "Medium" | "Low" (Critical for drop >= 50%, High for drop >= 15%, Medium/Low otherwise),
  
  "cfo": {{
    "title": "Short, board-friendly financial headline",
    "executive_summary": "A 2-3 sentence overview for the CFO focusing on revenue and margin impact.",
    "business_impact": "Financial loss metrics and risk assessment.",
    "root_cause_analysis": "Explanation of how the driver impacted financial metrics.",
    "recommendations": [
      "Financial mitigation lever 1",
      "Financial mitigation lever 2",
      "Financial mitigation lever 3"
    ]
  }},
  
  "ops": {{
    "title": "Operational technical headline",
    "executive_summary": "A 2-3 sentence overview for the Ops Manager focusing on SRE metrics and customer tickets.",
    "business_impact": "Operational metrics (ticket count, latency, duration).",
    "root_cause_analysis": "Detailed technical explanation of the failure mode referencing tickets.",
    "recommendations": [
      "SRE operational lever 1",
      "SRE operational lever 2",
      "SRE operational lever 3"
    ]
  }}
}}
Do NOT include markdown formatting (like ```json). Return ONLY the raw JSON.
"""

    model_name = os.getenv("CHEAP_MODEL", "gemini-2.5-flash")
    start_time = time.time()
    
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        latency = int((time.time() - start_time) * 1000)
        text = response.text.strip()
        
        # Clean up any potential markdown formatting
        if text.startswith("```json"):
            text = text.replace("```json", "", 1)
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        
        raw_report = json.loads(text)
        
        # Merge telemetry logs
        prompt_tokens = 0
        candidates_tokens = 0
        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count
            candidates_tokens = response.usage_metadata.candidates_token_count
            
        log_llm_call(insight_id, "act_narration", model_name, prompt_tokens, candidates_tokens, latency)
        
        # Format unified report with backward-compatible top-level keys defaulting to ops
        report = {
            "incident_id": insight_id,
            "title": raw_report["ops"]["title"],
            "severity": raw_report.get("severity", "High"),
            "executive_summary": raw_report["ops"]["executive_summary"],
            "business_impact": raw_report["ops"]["business_impact"],
            "root_cause_analysis": raw_report["ops"]["root_cause_analysis"],
            "evidence_summary": f"Retrieved ticket logs match '{driver_kpi}' correlation.",
            "recommendations": raw_report["ops"]["recommendations"],
            "cfo": raw_report["cfo"],
            "ops": raw_report["ops"],
            "retrieved_tickets": evidence_details,
            "anomaly": anomaly,
            "drivers": incident["drivers"],
            "confidence_track": incident["confidence_track"],
            "confidence_score": incident["confidence_score"],
            "confidence_caveat": incident["confidence_caveat"],
            "abstain": False,
            "clarifying_question": ""
        }
        
        return report
        
    except Exception as e:
        print(f"Failed to generate narrative report for {region}: {e}")
        fallback_title = f"Revenue drop in {region}"
        fallback_summary = f"A revenue anomaly was detected in {region} on {timestamp} due to {driver_kpi}."
        fallback_recommendations = candidate_levers[:3]
        return {
            "incident_id": insight_id,
            "title": f"[Operational Summary] {fallback_title}",
            "severity": "High",
            "executive_summary": f"Ops Summary: {fallback_summary} Incident correlates with a support ticket surge.",
            "business_impact": f"Revenue dropped by -${abs_change:,.2f} (-{pct_change * 100:.1f}%).",
            "root_cause_analysis": f"Root cause driver: {driver_kpi}. Narrative synthesis failed: {e}",
            "evidence_summary": "Failed to analyze support tickets.",
            "recommendations": fallback_recommendations,
            "cfo": {
                "title": f"[Financial Summary] {fallback_title}",
                "executive_summary": f"CFO Summary: {fallback_summary} Total revenue impact calculated at -${abs_change:,.2f}.",
                "business_impact": f"Revenue drop of -${abs_change:,.2f} (-{pct_change * 100:.1f}%).",
                "root_cause_analysis": f"Root cause driver: {driver_kpi}",
                "recommendations": fallback_recommendations
            },
            "ops": {
                "title": f"[Operational Summary] {fallback_title}",
                "executive_summary": f"Ops Summary: {fallback_summary} Incident correlates with a support ticket surge.",
                "business_impact": f"Revenue drop of -${abs_change:,.2f} (-{pct_change * 100:.1f}%).",
                "root_cause_analysis": f"Root cause driver: {driver_kpi}",
                "recommendations": fallback_recommendations
            },
            "retrieved_tickets": evidence_details,
            "anomaly": anomaly,
            "drivers": incident["drivers"],
            "confidence_track": incident["confidence_track"],
            "confidence_score": incident["confidence_score"],
            "confidence_caveat": incident["confidence_caveat"],
            "abstain": False,
            "clarifying_question": ""
        }

def run_narration():
    print("Starting narration & action recommendation stage (Act)...")
    try:
        client = get_gemini_client()
    except Exception as e:
        print(f"Initialization error: {e}")
        return
        
    judged_path = "pipeline/judged.json"
    levers_path = "pipeline/levers.json"
    
    if not os.path.exists(judged_path) or not os.path.exists(levers_path):
        print("Missing judged.json or levers.json. Run previous pipeline stages first.")
        return
        
    with open(judged_path, "r") as f:
        incidents = json.load(f)
    with open(levers_path, "r") as f:
        levers = json.load(f)
        
    conn = get_connection()
    reports = []
    
    try:
        for idx, incident in enumerate(incidents):
            region = incident["anomaly"]["region"]
            date = incident["anomaly"]["timestamp"]
            print(f"Generating report {idx + 1}/{len(incidents)} for {region} ({date})...")
            report = generate_report_narrative(client, incident, levers, conn)
            reports.append(report)
    finally:
        conn.close()
        
    output_path = "pipeline/reports.json"
    with open(output_path, "w") as f:
        json.dump(reports, f, indent=2)
        
    print(f"\nSuccessfully saved {len(reports)} executive incident reports to '{output_path}'.")
    return reports

if __name__ == "__main__":
    run_narration()
