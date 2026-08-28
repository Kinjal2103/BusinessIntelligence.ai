import csv
import os
import sys
import time
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

# Load env variables with explicit override
dotenv_path = r"c:\Users\kinja\Desktop\CSE\AIC\.env"
load_dotenv(dotenv_path=dotenv_path, override=True)

DB_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def connect_db(retries=5, delay=3):
    """Establish connection to PostgreSQL with retry logic."""
    print("Connecting to Supabase database...")
    for idx in range(retries):
        try:
            conn = psycopg2.connect(DB_URL)
            print("Connected to Supabase successfully!")
            return conn
        except Exception as e:
            print(f"Connection attempt {idx + 1}/{retries} failed. Error: {e}")
            time.sleep(delay)
    print("Could not connect to Supabase database.")
    sys.exit(1)

def create_supabase_schema(conn):
    """Create the tables and indices in Supabase with pgvector support."""
    cursor = conn.cursor()
    
    print("Enabling pgvector extension on Supabase...")
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
    except Exception as e:
        print(f"Warning: Could not enable vector extension: {e}")
        conn.rollback()

    # Drop tables if they exist for resettlement
    print("Dropping existing tables if they exist...")
    cursor.execute("DROP TABLE IF EXISTS revenue_daily CASCADE;")
    cursor.execute("DROP TABLE IF EXISTS support_tickets CASCADE;")
    cursor.execute("DROP TABLE IF EXISTS marketing_spend_weekly CASCADE;")
    cursor.execute("DROP TABLE IF EXISTS server_latency_hourly CASCADE;")
    cursor.execute("DROP TABLE IF EXISTS churn_monthly CASCADE;")
    cursor.execute("DROP TABLE IF EXISTS telemetry_logs CASCADE;")
    cursor.execute("DROP TABLE IF EXISTS feedback_logs CASCADE;")
    cursor.execute("DROP TABLE IF EXISTS config_overrides CASCADE;")
    
    print("Creating database schema...")
    
    # Revenue Daily
    cursor.execute("""
        CREATE TABLE revenue_daily (
            date DATE NOT NULL,
            region VARCHAR(50) NOT NULL,
            revenue DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (date, region)
        );
    """)
    
    # Support Tickets (with vector column of size 3072 for gemini-embedding-001)
    cursor.execute("""
        CREATE TABLE support_tickets (
            ticket_id VARCHAR(50) PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL,
            region VARCHAR(50) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            category VARCHAR(100) NOT NULL,
            priority VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL,
            description TEXT,
            embedding vector(3072)
        );
    """)
    
    # Marketing Spend Weekly
    cursor.execute("""
        CREATE TABLE marketing_spend_weekly (
            week_start_date DATE NOT NULL,
            region VARCHAR(50) NOT NULL,
            campaign_name VARCHAR(100) NOT NULL,
            spend DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (week_start_date, region, campaign_name)
        );
    """)
    
    # Server Latency Hourly
    cursor.execute("""
        CREATE TABLE server_latency_hourly (
            timestamp TIMESTAMP NOT NULL,
            region VARCHAR(50) NOT NULL,
            avg_latency_ms DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (timestamp, region)
        );
    """)
    
    # Churn Monthly
    cursor.execute("""
        CREATE TABLE churn_monthly (
            month_start_date DATE NOT NULL,
            region VARCHAR(50) NOT NULL,
            churn_rate DOUBLE PRECISION NOT NULL,
            customer_count INT NOT NULL,
            PRIMARY KEY (month_start_date, region)
        );
    """)
    
    # Telemetry Logs
    cursor.execute("""
        CREATE TABLE telemetry_logs (
            id SERIAL PRIMARY KEY,
            insight_id VARCHAR(50),
            stage VARCHAR(50) NOT NULL,
            model_name VARCHAR(100),
            input_tokens INT,
            output_tokens INT,
            latency_ms INT,
            estimated_cost_usd DOUBLE PRECISION,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Feedback Logs
    cursor.execute("""
        CREATE TABLE feedback_logs (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(50) NOT NULL,
            decision VARCHAR(20) NOT NULL,
            adjusted_narrative TEXT,
            adjusted_action TEXT,
            analyst_comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Config Overrides
    cursor.execute("""
        CREATE TABLE config_overrides (
            id SERIAL PRIMARY KEY,
            kpi_name VARCHAR(50) NOT NULL UNIQUE,
            pct_change_override DOUBLE PRECISION,
            absolute_change_override DOUBLE PRECISION,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create indexing for optimization
    cursor.execute("CREATE INDEX idx_revenue_region_date ON revenue_daily(region, date);")
    cursor.execute("CREATE INDEX idx_tickets_region_created ON support_tickets(region, created_at);")
    cursor.execute("CREATE INDEX idx_latency_region_timestamp ON server_latency_hourly(region, timestamp);")
    
    conn.commit()
    cursor.close()
    print("Schema created and indexed successfully.")

def load_csv_to_supabase(conn):
    """Read seed CSV files and insert them into Supabase in optimized batches."""
    cursor = conn.cursor()
    
    # 1. Load revenue_daily
    print("Loading revenue_daily.csv in batch...")
    data = []
    with open("data/revenue_daily.csv", "r") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            data.append((row[0], row[1], float(row[2])))
    execute_values(cursor, "INSERT INTO revenue_daily (date, region, revenue) VALUES %s", data)
            
    # 2. Load support_tickets (initially without embeddings)
    print("Loading support_tickets.csv in batch...")
    data = []
    with open("data/support_tickets.csv", "r") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            data.append((row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]))
    execute_values(
        cursor, 
        """INSERT INTO support_tickets 
           (ticket_id, customer_id, region, created_at, category, priority, status, description) 
           VALUES %s""", 
        data
    )
            
    # 3. Load marketing_spend_weekly
    print("Loading marketing_spend_weekly.csv in batch...")
    data = []
    with open("data/marketing_spend_weekly.csv", "r") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            data.append((row[0], row[1], row[2], float(row[3])))
    execute_values(cursor, "INSERT INTO marketing_spend_weekly (week_start_date, region, campaign_name, spend) VALUES %s", data)
            
    # 4. Load server_latency_hourly
    print("Loading server_latency_hourly.csv in batch...")
    data = []
    with open("data/server_latency_hourly.csv", "r") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            data.append((row[0], row[1], float(row[2])))
    execute_values(cursor, "INSERT INTO server_latency_hourly (timestamp, region, avg_latency_ms) VALUES %s", data)
            
    # 5. Load churn_monthly
    print("Loading churn_monthly.csv in batch...")
    data = []
    with open("data/churn_monthly.csv", "r") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            data.append((row[0], row[1], float(row[2]), int(row[3])))
    execute_values(cursor, "INSERT INTO churn_monthly (month_start_date, region, churn_rate, customer_count) VALUES %s", data)
            
    conn.commit()
    cursor.close()
    print("All CSV datasets loaded successfully using batch inserts.")

def generate_and_update_embeddings(conn):
    """Generate embeddings using Gemini API for critical outage tickets and update Supabase."""
    if not GEMINI_API_KEY or "your_gemini_api_key" in GEMINI_API_KEY or GEMINI_API_KEY == "your-api-key-here":
        print("\n[WARNING] GEMINI_API_KEY is not set or is a placeholder in .env!")
        print("Support tickets were loaded, but their vector embeddings were NOT generated.")
        return

    print("\nInitializing Gemini client for vector embeddings...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    cursor = conn.cursor()
    
    # CRITICAL OPTIMIZATION: Only embed Southeast billing outage tickets on Aug 15
    # Since these are the only ones critical to verify the evidence gate
    cursor.execute("""
        SELECT ticket_id, description FROM support_tickets 
        WHERE embedding IS NULL 
        AND created_at::date = '2026-08-15' 
        AND region = 'Southeast' 
        AND category = 'Billing';
    """)
    tickets = cursor.fetchall()
    
    if not tickets:
        print("No critical tickets need embedding.")
        cursor.close()
        return
        
    print(f"Generating embeddings for {len(tickets)} critical outage tickets one-by-one to avoid rate limits...")
    
    total_updated = 0
    
    for idx, (ticket_id, description) in enumerate(tickets):
        print(f"Embedding ticket {idx + 1}/{len(tickets)}: {ticket_id}...")
        
        retries = 3
        while retries > 0:
            try:
                # Embed single content
                response = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=description
                )
                
                embedding_vector = response.embeddings[0].values
                cursor.execute(
                    "UPDATE support_tickets SET embedding = %s WHERE ticket_id = %s;",
                    (embedding_vector, ticket_id)
                )
                conn.commit()
                total_updated += 1
                
                # Stay strictly under 15 RPM by sleeping 4.5s
                time.sleep(4.5)
                break
                
            except APIError as e:
                if "RESOURCE_EXHAUSTED" in str(e) or e.code == 429:
                    print("Rate limit hit. Waiting 60 seconds to retry...")
                    time.sleep(60.0)
                    retries -= 1
                else:
                    print(f"API Error: {e}")
                    retries = 0
            except Exception as e:
                print(f"Unexpected error: {e}")
                retries = 0
                
    cursor.close()
    print(f"Successfully generated and updated embeddings for {total_updated} outage tickets.")

if __name__ == "__main__":
    conn = connect_db()
    try:
        create_supabase_schema(conn)
        load_csv_to_supabase(conn)
        generate_and_update_embeddings(conn)
    finally:
        conn.close()
    print("Seed data load complete.")
