import requests
import json
import psycopg2
import os
import time
from dotenv import load_dotenv

# Load env variables
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=dotenv_path, override=True)
DB_URL = os.getenv("DATABASE_URL")

API_BASE = "http://localhost:8000"

def get_connection():
    return psycopg2.connect(DB_URL)

def run_tests():
    print("==================================================")
    print("STARTING E2E INTEGRATION & RBAC VALIDATION TESTS")
    print("==================================================")
    
    # Reset overrides and re-run pipeline so both West and Southeast anomalies are present
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config_overrides WHERE kpi_name IN ('revenue', 'confidence_weights');")
        conn.commit()
        cursor.close()
        conn.close()
        print("[SETUP] Cleared config overrides to reset thresholds.")
    except Exception as e:
        print(f"[SETUP] Failed to clear config overrides: {e}")
        return

    # Trigger end-to-end pipeline run to regenerate reports.json under default thresholds
    try:
        print("[SETUP] Triggering end-to-end pipeline execution...")
        res = requests.post(f"{API_BASE}/api/run-pipeline")
        assert res.status_code == 200
        print("[SETUP] Pipeline run completed successfully.")
    except Exception as e:
        print(f"[SETUP] Failed to run pipeline: {e}")
        return

    # Test 1: API Health Check
    try:
        res = requests.get(f"{API_BASE}/health")
        assert res.status_code == 200
        print("[PASS] Test 1: Health check passed.")
    except Exception as e:
        print(f"[FAIL] Test 1: Health check failed: {e}")
        return

    # Test 2: Server-Side RBAC for Regional Operations Manager
    # Regional Ops Manager (Southeast) should see Southeast reports
    headers_ops = {
        "X-User-Role": "Regional_Ops_Manager",
        "X-User-Region": "Southeast"
    }
    try:
        res = requests.get(f"{API_BASE}/api/reports", headers=headers_ops)
        assert res.status_code == 200
        reports = res.json()
        
        # Verify only Southeast is returned
        for r in reports:
            assert r["anomaly"]["region"] == "Southeast", f"Ops Manager saw region {r['anomaly']['region']}"
        print(f"[PASS] Test 2: Ops Manager Row-Level regional isolation passed. (Returned {len(reports)} Southeast reports)")
    except Exception as e:
        print(f"[FAIL] Test 2: Ops Manager regional isolation failed: {e}")

    # Test 2b: Ops Manager Cross-Region Reconcile Block (403)
    try:
        res = requests.get(
            f"{API_BASE}/api/reconcile?kpi_x=server_latency&kpi_y=revenue&region=West&start_date=2026-08-10&end_date=2026-08-25",
            headers=headers_ops
        )
        assert res.status_code == 403
        print("[PASS] Test 2b: Ops Manager cross-region access blocked (403 Forbidden).")
    except Exception as e:
        print(f"[FAIL] Test 2b: Ops Manager cross-region block failed: {e}")

    # Test 3: Server-Side RBAC PII Redaction for CFO
    headers_cfo = {
        "X-User-Role": "CFO"
    }
    try:
        res = requests.get(f"{API_BASE}/api/reports", headers=headers_cfo)
        assert res.status_code == 200
        reports = res.json()
        
        # Verify PII descriptions are redacted in retrieved tickets
        checked = False
        for r in reports:
            if r["retrieved_tickets"]:
                for t in r["retrieved_tickets"]:
                    assert "REDACTED" in t["description"], f"PII was not redacted: {t['description']}"
                    checked = True
        assert checked, "No tickets found to verify redaction."
        print(f"[PASS] Test 3: CFO Column-Level PII description redaction passed. (Verified {len(reports)} reports)")
    except Exception as e:
        print(f"[FAIL] Test 3: CFO PII redaction failed: {e}")

    # Test 4: Decision Submission and Threshold Recalibration
    decision_payload = {
        "incident_id": "INC-SOU-20260815",
        "decision": "reject",
        "analyst_comments": "False alarm. Adjusting sensitivity."
    }
    try:
        res = requests.post(f"{API_BASE}/api/decision", json=decision_payload)
        assert res.status_code == 200
        print("[PASS] Test 4: Decision logged to database.")
        
        # Verify override exists in config_overrides table
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT pct_change_override, absolute_change_override FROM config_overrides WHERE kpi_name = 'revenue';")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        assert row is not None, "Threshold overrides not written to DB"
        print(f"[PASS] Test 4b: Threshold overrides successfully written to database: pct={row[0]:.4f}, abs={row[1]:.2f}")
    except Exception as e:
        print(f"[FAIL] Test 4: Decision / recalibration failed: {e}")

    # Test 4c: Confidence weights recalibration (Judge override check)
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT pct_change_override, absolute_change_override FROM config_overrides WHERE kpi_name = 'confidence_weights';")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        assert row is not None, "Confidence weights overrides not written to DB"
        print(f"[PASS] Test 4c: Confidence weights recalibration passed: Acute weight={row[0]:.2f}, Structural weight={row[1]:.2f}")
    except Exception as e:
        print(f"[FAIL] Test 4c: Confidence weight recalibration check failed: {e}")

    # Test 5: Telemetry logs
    try:
        res = requests.get(f"{API_BASE}/api/telemetry")
        assert res.status_code == 200
        telemetry = res.json()
        assert len(telemetry) > 0
        print(f"[PASS] Test 5: Telemetry logs fetched successfully. Active cost logs found: {len(telemetry)} logs.")
    except Exception as e:
        print(f"[FAIL] Test 5: Telemetry retrieval failed: {e}")

    # Test 6: Price-Volume-Mix (PVM) and Difference-in-Differences (DiD) Causal Keys
    try:
        candidates_path = "pipeline/candidates.json"
        assert os.path.exists(candidates_path), "candidates.json missing"
        with open(candidates_path, "r") as f:
            candidates = json.load(f)
        
        for incident in candidates:
            for driver in incident["drivers"]:
                if driver["evidence_gate_passed"]:
                    assert "price_volume_mix" in driver, "Price-Volume-Mix key missing in accepted driver"
                    assert "causal_inference_did" in driver, "Causal DiD key missing in accepted driver"
                    
                    pvm = driver["price_volume_mix"]
                    did = driver["causal_inference_did"]
                    assert "volume_contribution_pct" in pvm, "PVM missing volume contribution percentage"
                    assert "causal_impact_dollars" in did, "DiD missing causal impact dollars value"
        print("[PASS] Test 6: Price-Volume-Mix decomposition and causal DiD keys verified in candidates.")
    except Exception as e:
        print(f"[FAIL] Test 6: PVM and Causal DiD verification failed: {e}")

    # Test 7: Persona-specific Summaries (CFO vs Ops)
    try:
        res_ops = requests.get(f"{API_BASE}/api/reports", headers=headers_ops)
        res_cfo = requests.get(f"{API_BASE}/api/reports", headers=headers_cfo)
        
        reports_ops = res_ops.json()
        reports_cfo = res_cfo.json()
        
        # Verify the Southeast report has differing headlines/summaries between CFO and Ops
        sou_ops = next(r for r in reports_ops if r["anomaly"]["region"] == "Southeast")
        sou_cfo = next(r for r in reports_cfo if r["anomaly"]["region"] == "Southeast")
        
        assert sou_ops["executive_summary"] != sou_cfo["executive_summary"], "CFO and Ops manager summaries are identical"
        assert sou_ops["title"] != sou_cfo["title"], "CFO and Ops headlines are identical"
        print("[PASS] Test 7: Persona-specific narrative framing verified (CFO vs Ops differ for the same anomaly).")
    except Exception as e:
        print(f"[FAIL] Test 7: Persona-specific summaries validation failed: {e}")

    # Test 8: Abstention case (West Region Latency)
    try:
        res = requests.get(f"{API_BASE}/api/reports", headers=headers_cfo)
        reports = res.json()
        west_incident = next(r for r in reports if r["anomaly"]["region"] == "West")
        
        assert west_incident["abstain"] == True, "West region incident is not flagged as Abstained"
        assert west_incident["clarifying_question"] != "", "Clarifying question is empty for Abstained incident"
        assert "latency" in west_incident["clarifying_question"].lower(), "Latency cause missing in West clarifying question"
        print("[PASS] Test 8: West region low-confidence abstention gate and SRE clarifying question verified.")
    except Exception as e:
        print(f"[FAIL] Test 8: West region abstention gate failed: {e}")

    print("==================================================")
    print("E2E TESTS COMPLETED")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
