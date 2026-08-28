import os
import json
import time
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError
from telemetry.logger import log_llm_call

# Load env variables
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=dotenv_path, override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_URL = os.getenv("DATABASE_URL")

def get_gemini_client():
    if not GEMINI_API_KEY or "your_gemini_api_key" in GEMINI_API_KEY or GEMINI_API_KEY == "your-api-key-here":
        raise ValueError("GEMINI_API_KEY is not configured in .env file!")
    return genai.Client(api_key=GEMINI_API_KEY)

def count_historical_alerts(anomaly, anomalies_list):
    """Count anomalies for the same region and KPI within the last 14 days."""
    kpi = anomaly["kpi"]
    region = anomaly["region"]
    current_time = datetime.strptime(anomaly["timestamp"], "%Y-%m-%d %H:%M:%S")
    cutoff_time = current_time - timedelta(days=14)
    
    count = 0
    for a in anomalies_list:
        if a["kpi"] == kpi and a["region"] == region:
            a_time = datetime.strptime(a["timestamp"], "%Y-%m-%d %H:%M:%S")
            if cutoff_time <= a_time <= current_time:
                count += 1
    return count

def run_phrasing_call(client, insight_id, track, score, anomaly_details, driver_details):
    """Call Gemini to phrase the confidence caveat sentence based on locked scores."""
    prompt = f"""
You are a senior BI reporting assistant. You need to write a single, professional confidence caveat sentence for a metric dashboard.
We computed the following confidence score and track for an anomaly:
- Confidence Track: {track}
- Confidence Score: {score:.2f} (locked, do NOT change this number or invent a new one)

Anomaly Details:
- Region: {anomaly_details['region']}
- Metric: {anomaly_details['kpi']}
- Drop: {anomaly_details['pct_change']*100:.1f}%

Driver Details:
- Driver: {driver_details.get('candidate', 'None')}
- Correlation: {driver_details.get('correlation', 0.0):.2f}

Write a single, clear, business-friendly sentence stating this confidence level and why. 
Example: "Confidence is high (70%) that this represents a structural revenue drift, as multiple revenue alerts have been triggered without any acute support tickets."
Do NOT include any introduction or code markdown. Return ONLY the sentence.
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
        
        # Read exact token counts
        prompt_tokens = 0
        candidates_tokens = 0
        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count
            candidates_tokens = response.usage_metadata.candidates_token_count
            
        log_llm_call(insight_id, "judge_phrasing", model_name, prompt_tokens, candidates_tokens, latency)
        return text
    except Exception as e:
        print(f"Failed LLM Phrase Call: {e}")
        return f"Confidence score locked at {score * 100:.0f}% for the {track} track."

def run_abstention_call(client, insight_id, anomaly_details, driver_details):
    """Call Gemini to draft a clarifying question when confidence falls below the floor."""
    prompt = f"""
You are a senior Business Intelligence Analyst.
We detected a significant revenue anomaly in the '{anomaly_details['region']}' region on {anomaly_details['timestamp']}.
It is mathematically correlated with '{driver_details.get('candidate', 'server_latency')}' (r = {driver_details.get('correlation', 0.0):.2f}), but the Evidence Gate FAILED because no customer support tickets or error logs were found in this region/date window.

Since the evidence is thin, we are abstaining from a final root-cause conclusion.
Draft a concise, professional clarifying question (1-2 sentences) that we can present to the SRE/Ops team on their dashboard to prompt further investigation. Ask if there was a silent system update, a tracking deployment glitch, or an unlogged gateway outage.

Do NOT include any introductory or trailing text. Return ONLY the raw question.
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
        
        prompt_tokens = 0
        candidates_tokens = 0
        if response.usage_metadata:
            prompt_tokens = response.usage_metadata.prompt_token_count
            candidates_tokens = response.usage_metadata.candidates_token_count
            
        log_llm_call(insight_id, "judge_abstention", model_name, prompt_tokens, candidates_tokens, latency)
        return text
    except Exception as e:
        print(f"Failed LLM Abstention Call: {e}")
        return "A high correlation was found with server latency, but no support tickets exist. Was there a silent infrastructure outage in this region?"

def get_confidence_weight_overrides():
    """Retrieve dynamic track confidence weight overrides from Supabase config_overrides."""
    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT pct_change_override, absolute_change_override FROM config_overrides WHERE kpi_name = 'confidence_weights';")
        row = cursor.fetchone()
        cursor.close()
        if row:
            return {
                "Acute": row[0] if row[0] is not None else 0.90,
                "Structural": row[1] if row[1] is not None else 0.70
            }
    except Exception as e:
        print(f"Failed to fetch confidence overrides: {e}")
    finally:
        if conn:
            conn.close()
    return {"Acute": 0.90, "Structural": 0.70}

def run_judging():
    print("Starting confidence judgment stage (Judge)...")
    try:
        client = get_gemini_client()
    except Exception as e:
        print(f"Initialization error: {e}")
        return
        
    candidates_path = "pipeline/candidates.json"
    anomalies_path = "pipeline/anomalies.json"
    
    if not os.path.exists(candidates_path) or not os.path.exists(anomalies_path):
        print("Candidates or Anomalies file missing. Run previous stages first.")
        return
        
    with open(candidates_path, "r") as f:
        incidents = json.load(f)
    with open(anomalies_path, "r") as f:
        anomalies_list = json.load(f)
        
    overrides = get_confidence_weight_overrides()
    judged_incidents = []
    
    for incident in incidents:
        anomaly = incident["anomaly"]
        region = anomaly["region"]
        timestamp = anomaly["timestamp"]
        kpi = anomaly["kpi"]
        
        # Unique insight ID for telemetry tracking
        insight_id = f"INC-{region[:3].upper()}-{timestamp[:10].replace('-', '')}"
        
        # 1. Evaluate candidate drivers
        drivers = incident["drivers"]
        corroborated_drivers = [d for d in drivers if d["evidence_gate_passed"]]
        any_correlated = any(d["is_correlated"] for d in drivers)
        
        track = "Unconfirmed"
        score = 0.40
        primary_driver = {}
        
        if corroborated_drivers:
            # ACUTE TRACK (using dynamic database overrides if available)
            primary_driver = corroborated_drivers[0]
            corr = abs(primary_driver["correlation"])
            track = "Acute"
            score = overrides["Acute"] if corr >= 0.7 else max(0.50, overrides["Acute"] - 0.20)
        elif not any_correlated:
            # EXTERNAL TRACK (no internal driver correlates, likely market/competitor shift)
            track = "External"
            score = 0.60
            primary_driver = {"candidate": "external_market_competitor", "correlation": 0.0, "is_correlated": False}
        else:
            # Check if this anomaly is part of a rolling STRUCTURAL decline (multiple alerts in 14 days)
            alerts_count = count_historical_alerts(anomaly, anomalies_list)
            
            # Find the strongest correlated driver as reference
            sorted_drivers = sorted(drivers, key=lambda x: abs(x["correlation"]), reverse=True)
            strongest_driver = sorted_drivers[0] if sorted_drivers else {}
            
            if alerts_count >= 3:
                # STRUCTURAL TRACK (using dynamic database overrides if available)
                track = "Structural"
                score = overrides["Structural"]
                primary_driver = strongest_driver
            else:
                # UNCONFIRMED TRACK
                track = "Unconfirmed"
                score = 0.40
                primary_driver = strongest_driver
                
        # 2. Enforce minimum confidence floor (0.50)
        abstain = score < 0.50
        
        # 3. Phrasing or Abstention Call
        if abstain:
            phrased_caveat = "Confidence is low (40%) due to a lack of corroborating logs or customer support tickets."
            clarifying_question = run_abstention_call(client, insight_id, anomaly, primary_driver)
            print(f"[{region}] ABSTAIN: Confidence ({score:.2f}) is below floor! Clarifying Question: '{clarifying_question}'")
        else:
            clarifying_question = ""
            phrased_caveat = run_phrasing_call(client, insight_id, track, score, anomaly, primary_driver)
            print(f"[{region}] JUDGED: Track: {track} | Score: {score:.2f} | Caveat: '{phrased_caveat}'")
            
        # Build judged incident object
        judged_incidents.append({
            "anomaly": anomaly,
            "drivers": drivers,
            "confidence_track": track,
            "confidence_score": score,
            "confidence_caveat": phrased_caveat,
            "abstain": abstain,
            "clarifying_question": clarifying_question,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    output_path = "pipeline/judged.json"
    with open(output_path, "w") as f:
        json.dump(judged_incidents, f, indent=2)
        
    print(f"\nSuccessfully judged {len(judged_incidents)} incidents. Judgments saved to '{output_path}'.")
    return judged_incidents

if __name__ == "__main__":
    run_judging()
