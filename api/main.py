import os
import json
import subprocess
import sys
import psycopg2
from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pipeline.reconcile import align_kpis
from pipeline.recalibrate import run_recalibration

app = FastAPI(title="BusinessIntelligence.ai API", version="0.1.0")

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = os.getenv("DATABASE_URL")
REPORTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pipeline", "reports.json")
CANDIDATES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pipeline", "candidates.json")
ANOMALIES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pipeline", "anomalies.json")

def get_connection():
    return psycopg2.connect(DB_URL)

class DecisionPayload(BaseModel):
    incident_id: str
    decision: str  # 'approve', 'edit', 'reject'
    adjusted_narrative: str = None
    adjusted_action: str = None
    analyst_comments: str = None

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "BusinessIntelligence.ai API"}

@app.get("/api/reports")
def get_reports(
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_region: str = Header(None, alias="X-User-Region")
):
    """Retrieve synthesized executive triage reports, applying server-side RBAC entitlements."""
    if not os.path.exists(REPORTS_PATH):
        return []
        
    try:
        with open(REPORTS_PATH, "r") as f:
            reports = json.load(f)
            
        # SERVER-SIDE RBAC ENFORCEMENT
        print(f"[RBAC] Request by Role: {x_user_role} | Region: {x_user_region}")
        
        filtered_reports = []
        
        for r in reports:
            region = r["anomaly"]["region"]
            report_copy = dict(r)
            
            # Enforce Row-Level Regional Isolation for Ops Manager
            if x_user_role == "Regional_Ops_Manager":
                if region != x_user_region:
                    continue
                # Load Ops persona-specific narrative properties if available
                if "ops" in report_copy:
                    ops_data = report_copy["ops"]
                    report_copy["title"] = ops_data.get("title", report_copy["title"])
                    report_copy["executive_summary"] = ops_data.get("executive_summary", report_copy["executive_summary"])
                    report_copy["business_impact"] = ops_data.get("business_impact", report_copy["business_impact"])
                    report_copy["root_cause_analysis"] = ops_data.get("root_cause_analysis", report_copy["root_cause_analysis"])
                    report_copy["recommendations"] = ops_data.get("recommendations", report_copy["recommendations"])
                filtered_reports.append(report_copy)
                
            # Enforce Column-Level PII Redaction and CFO summaries for CFO
            elif x_user_role == "CFO":
                # Load CFO persona-specific narrative properties if available
                if "cfo" in report_copy:
                    cfo_data = report_copy["cfo"]
                    report_copy["title"] = cfo_data.get("title", report_copy["title"])
                    report_copy["executive_summary"] = cfo_data.get("executive_summary", report_copy["executive_summary"])
                    report_copy["business_impact"] = cfo_data.get("business_impact", report_copy["business_impact"])
                    report_copy["root_cause_analysis"] = cfo_data.get("root_cause_analysis", report_copy["root_cause_analysis"])
                    report_copy["recommendations"] = cfo_data.get("recommendations", report_copy["recommendations"])
                
                if "retrieved_tickets" in report_copy:
                    redacted_tickets = []
                    for t in report_copy["retrieved_tickets"]:
                        t_copy = dict(t)
                        t_copy["description"] = "[REDACTED - PII EXCLUSION FOR CFO ROLE]"
                        redacted_tickets.append(t_copy)
                    report_copy["retrieved_tickets"] = redacted_tickets
                filtered_reports.append(report_copy)
            else:
                # Admin / Default sees combined
                filtered_reports.append(r)
                
        return filtered_reports
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading reports: {e}")

@app.get("/api/reconcile")
def get_reconciled_kpis(
    kpi_x: str = Query(..., description="First KPI name"),
    kpi_y: str = Query(..., description="Second KPI name"),
    region: str = Query(None, description="Filter by region"),
    start_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    x_user_role: str = Header(None, alias="X-User-Role"),
    x_user_region: str = Header(None, alias="X-User-Region")
):
    """Align and reconcile two KPIs for timeseries charts, enforcing regional RBAC boundaries."""
    # SERVER-SIDE RBAC ENFORCEMENT
    if x_user_role == "Regional_Ops_Manager":
        if region != x_user_region:
            raise HTTPException(
                status_code=403, 
                detail="Forbidden: Regional Operations Managers are restricted to their assigned region."
            )
            
    try:
        df = align_kpis(kpi_x, kpi_y, region, start_date, end_date)
        if df.empty:
            return []
            
        df['date'] = df['date'].astype(str)
        df = df.replace({float('nan'): None})
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Alignment failed: {e}")

@app.post("/api/decision")
def post_decision(payload: DecisionPayload):
    """Log analyst decision (Approve/Reject/Edit) and run threshold recalibration."""
    print(f"[Decision] Incident: {payload.incident_id} | Choice: {payload.decision}")
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        sql = """
            INSERT INTO feedback_logs 
            (incident_id, decision, adjusted_narrative, adjusted_action, analyst_comments)
            VALUES (%s, %s, %s, %s, %s);
        """
        cursor.execute(sql, (
            payload.incident_id,
            payload.decision,
            payload.adjusted_narrative,
            payload.adjusted_action,
            payload.analyst_comments
        ))
        conn.commit()
        cursor.close()
        
        # Trigger dynamic threshold recalibration immediately
        run_recalibration()
        
        return {"status": "success", "message": "Decision logged and recalibration run successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database logging failed: {e}")
    finally:
        if conn:
            conn.close()

@app.get("/api/decisions")
def get_decisions():
    """Retrieve feedback/recalibration decisions log for Audits panel."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, incident_id, decision, analyst_comments, created_at
            FROM feedback_logs
            ORDER BY created_at DESC
            LIMIT 50;
        """)
        rows = cursor.fetchall()
        cursor.close()
        
        decisions = []
        for r in rows:
            decisions.append({
                "id": r[0],
                "incident_id": r[1],
                "decision": r[2],
                "analyst_comments": r[3] or "",
                "created_at": r[4].strftime("%Y-%m-%d %H:%M:%S")
            })
        return decisions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch decisions: {e}")
    finally:
        if conn:
            conn.close()

@app.get("/api/telemetry")
def get_telemetry_logs():
    """Retrieve telemetry log summary for cost/latency panel."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stage, model_name, input_tokens, output_tokens, latency_ms, estimated_cost_usd, timestamp
            FROM telemetry_logs
            ORDER BY timestamp DESC
            LIMIT 50;
        """)
        rows = cursor.fetchall()
        cursor.close()
        
        logs = []
        for r in rows:
            logs.append({
                "stage": r[0],
                "model_name": r[1],
                "input_tokens": r[2],
                "output_tokens": r[3],
                "latency": r[4],
                "cost": float(r[5] or 0.0),
                "timestamp": r[6].strftime("%Y-%m-%d %H:%M:%S")
            })
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch telemetry: {e}")
    finally:
        if conn:
            conn.close()

@app.post("/api/run-pipeline")
def run_analytical_pipeline():
    """Trigger the entire pipeline sequentially: Detect -> Investigate -> Judge -> Act."""
    print("Triggering full pipeline execution (Detect -> Investigate -> Judge -> Act)...")
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    
    # Dynamically resolve virtual environment python executable
    root_dir = os.path.dirname(os.path.dirname(__file__))
    python_exe = os.path.join(root_dir, "venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = os.path.join(root_dir, "venv", "bin", "python") # Unix fallback
    if not os.path.exists(python_exe):
        python_exe = sys.executable # Final fallback
        
    try:
        # 1. Run detection
        print(f"Running detect.py with {python_exe}...")
        subprocess.run([python_exe, "-m", "pipeline.detect"], env=env, check=True)
        # 2. Run investigation
        print("Running investigate.py...")
        subprocess.run([python_exe, "-m", "pipeline.investigate"], env=env, check=True)
        # 3. Run scoring/judging
        print("Running judge.py...")
        subprocess.run([python_exe, "-m", "pipeline.judge"], env=env, check=True)
        # 4. Run narration (Act)
        print("Running narrate.py...")
        subprocess.run([python_exe, "-m", "pipeline.narrate"], env=env, check=True)
        
        return {"status": "success", "message": "Pipeline completed successfully. All logs & reports updated."}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Pipeline step failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected pipeline error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
