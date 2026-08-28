import os
import json
import psycopg2
from dotenv import load_dotenv
from pipeline.contract_loader import registry

# Load env variables
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=dotenv_path, override=True)
DB_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DB_URL)

def run_recalibration():
    print("Running threshold recalibration loop...")
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Fetch all rejections from feedback_logs
        cursor.execute("SELECT incident_id FROM feedback_logs WHERE decision = 'reject';")
        rejections = cursor.fetchall()
        
        if not rejections:
            print("No rejections found in feedback logs. No recalibration needed.")
            return
            
        print(f"Found {len(rejections)} rejected alerts. Recalibrating materiality thresholds...")
        
        # 2. Read reports.json to map incident_id to KPI name
        reports_path = "pipeline/reports.json"
        if not os.path.exists(reports_path):
            print(f"Warning: reports.json not found at {reports_path}. Cannot map incident IDs.")
            return
            
        with open(reports_path, "r") as f:
            reports = json.load(f)
            
        # Map incident_id -> kpi_name
        incident_kpis = {}
        for r in reports:
            incident_kpis[r["incident_id"]] = r["anomaly"]["kpi"]
            
        # Count rejections per KPI
        rejection_counts = {}
        for rej in rejections:
            inc_id = rej[0]
            kpi = incident_kpis.get(inc_id)
            if kpi:
                rejection_counts[kpi] = rejection_counts.get(kpi, 0) + 1
                
        # 3. Apply thresholds recalibration per KPI
        for kpi, count in rejection_counts.items():
            contract = registry.get(kpi)
            if not contract:
                continue
                
            orig_thresholds = contract.materiality_threshold
            orig_pct = orig_thresholds.get("pct_change", 0.15)
            orig_abs = orig_thresholds.get("absolute_change", 0.0)
            
            # Increase thresholds by 10% per rejection to decrease sensitivity
            multiplier = 1.0 + (0.10 * count)
            new_pct = orig_pct * multiplier
            new_abs = orig_abs * multiplier
            
            print(f"Recalibrating KPI '{kpi}': {count} rejections.")
            print(f"  - Pct Change Threshold: {orig_pct:.4f} -> {new_pct:.4f}")
            print(f"  - Abs Change Threshold: {orig_abs:.2f} -> {new_abs:.2f}")
            
            # Upsert into config_overrides in Supabase
            sql = """
                INSERT INTO config_overrides (kpi_name, pct_change_override, absolute_change_override)
                VALUES (%s, %s, %s)
                ON CONFLICT (kpi_name)
                DO UPDATE SET 
                    pct_change_override = EXCLUDED.pct_change_override,
                    absolute_change_override = EXCLUDED.absolute_change_override,
                    updated_at = CURRENT_TIMESTAMP;
            """
            cursor.execute(sql, (kpi, new_pct, new_abs))
            
        conn.commit()
        cursor.close()
        print("Recalibration run complete. Overrides saved to Supabase.")
        
    except Exception as e:
        print(f"Recalibration failed: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_recalibration()
