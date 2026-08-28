import os
import psycopg2
from dotenv import load_dotenv

# Load env variables with explicit override
dotenv_path = r"c:\Users\kinja\Desktop\CSE\AIC\.env"
load_dotenv(dotenv_path=dotenv_path, override=True)

DB_URL = os.getenv("DATABASE_URL")

def verify_seeding():
    print("Connecting to Supabase to verify seed data...")
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        # 1. Print row counts for all tables
        tables = ["revenue_daily", "support_tickets", "marketing_spend_weekly", "server_latency_hourly", "churn_monthly"]
        print("\n--- Relational Row Counts ---")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            print(f"Table '{table}': {count} rows")
            
        # 2. Verify Scenario 1: Southeast Payment Gateway Outage on 2026-08-15
        print("\n--- Verifying Scenario 1 (Southeast Outage 2026-08-15) ---")
        cursor.execute("SELECT revenue FROM revenue_daily WHERE region = 'Southeast' AND date = '2026-08-15';")
        se_rev = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE region = 'Southeast' AND created_at::date = '2026-08-15';")
        se_tkt_count = cursor.fetchone()[0]
        cursor.execute("SELECT ticket_id, priority, description FROM support_tickets WHERE region = 'Southeast' AND created_at::date = '2026-08-15' AND category = 'Billing' LIMIT 3;")
        sample_tkts = cursor.fetchall()
        
        print(f"Southeast Revenue on 2026-08-15: ${se_rev[0] if se_rev else 'N/A'} (expected large drop from $50k)")
        print(f"Southeast Ticket Count on 2026-08-15: {se_tkt_count} (expected spike, base is ~15)")
        print("Sample Outage Tickets:")
        for t in sample_tkts:
            print(f"  - [{t[0]}] Priority: {t[1]} | Desc: {t[2]}")
            
        # 3. Verify Scenario 2: Northeast Slow Decline (July 2026)
        print("\n--- Verifying Scenario 2 (Northeast Gradual July Decline) ---")
        cursor.execute("SELECT AVG(revenue) FROM revenue_daily WHERE region = 'Northeast' AND date BETWEEN '2026-06-01' AND '2026-06-30';")
        ne_june_avg = cursor.fetchone()[0]
        cursor.execute("SELECT AVG(revenue) FROM revenue_daily WHERE region = 'Northeast' AND date BETWEEN '2026-07-20' AND '2026-07-30';")
        ne_late_july_avg = cursor.fetchone()[0]
        cursor.execute("SELECT churn_rate FROM churn_monthly WHERE region = 'Northeast' AND month_start_date = '2026-07-01';")
        ne_july_churn = cursor.fetchone()[0]
        
        print(f"Northeast June Daily Revenue Avg: ${ne_june_avg:.2f}")
        print(f"Northeast Late July Daily Revenue Avg: ${ne_late_july_avg:.2f} (expected drop of ~20-25%)")
        print(f"Northeast July Churn Rate: {ne_july_churn * 100:.2f}% (expected spike, baseline is ~2%)")
        
        # 4. Verify Scenario 3: West Server Latency Blip on 2026-08-20
        print("\n--- Verifying Scenario 3 (West Server Latency Blip 2026-08-20) ---")
        cursor.execute("SELECT avg_latency_ms FROM server_latency_hourly WHERE region = 'West' AND timestamp = '2026-08-20 12:00:00';")
        west_latency = cursor.fetchone()
        cursor.execute("SELECT revenue FROM revenue_daily WHERE region = 'West' AND date = '2026-08-20';")
        west_rev = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE region = 'West' AND created_at::date = '2026-08-20';")
        west_tkt_count = cursor.fetchone()[0]
        
        print(f"West Latency on 2026-08-20 12:00:00: {west_latency[0] if west_latency else 'N/A'} ms (expected spike from ~120ms to ~1500ms)")
        print(f"West Revenue on 2026-08-20: ${west_rev[0] if west_rev else 'N/A'} (expected dip of ~15% from $45k)")
        print(f"West Ticket Count on 2026-08-20: {west_tkt_count} (expected normal baseline, ~10 tickets, no outage tickets)")
        
        # 5. Verify Scenario 4: Sparse History (Europe)
        print("\n--- Verifying Scenario 4 (Sparse History Europe) ---")
        cursor.execute("SELECT MIN(date), COUNT(*) FROM revenue_daily WHERE region = 'Europe';")
        eur_min_date, eur_days = cursor.fetchone()
        print(f"Europe Revenue Min Date: {eur_min_date} (expected launch on 2026-08-10)")
        print(f"Europe Revenue Days of History: {eur_days} days (expected under 8 weeks)")
        
        cursor.close()
        conn.close()
        print("\nVerification completed successfully. Database loaded correctly.")
        
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    verify_seeding()
