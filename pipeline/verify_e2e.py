import requests
import json
import psycopg2
import os
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

    # Test 5: Telemetry logs
    try:
        res = requests.get(f"{API_BASE}/api/telemetry")
        assert res.status_code == 200
        telemetry = res.json()
        assert len(telemetry) > 0
        print(f"[PASS] Test 5: Telemetry logs fetched successfully. Active cost logs found: {len(telemetry)} logs.")
    except Exception as e:
        print(f"[FAIL] Test 5: Telemetry retrieval failed: {e}")

    print("==================================================")
    print("E2E TESTS COMPLETED")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
