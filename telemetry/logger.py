import os
import psycopg2
from dotenv import load_dotenv

# Load env variables
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=dotenv_path, override=True)
DB_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DB_URL)

def calculate_llm_cost(model_name, input_tokens, output_tokens):
    """Calculate the estimated USD cost of a Gemini API call based on token usage."""
    # Pricing per 1,000,000 tokens
    # gemini-2.5-flash: Input $0.075, Output $0.30
    # gemini-1.5-flash: Input $0.075, Output $0.30
    # gemini-3.1-pro-preview: Input $1.25, Output $5.00
    # gemini-embedding-001: Input $0.025 (output is 0)
    
    model = model_name.lower()
    
    if "flash" in model:
        input_rate = 0.075 / 1000000
        output_rate = 0.30 / 1000000
    elif "pro" in model:
        input_rate = 1.25 / 1000000
        output_rate = 5.00 / 1000000
    elif "embedding" in model:
        input_rate = 0.025 / 1000000
        output_rate = 0.0
    else:
        # Default fallback
        input_rate = 0.075 / 1000000
        output_rate = 0.30 / 1000000
        
    cost = (input_tokens * input_rate) + (output_tokens * output_rate)
    return cost

def log_llm_call(insight_id, stage, model_name, input_tokens, output_tokens, latency_ms):
    """Insert an LLM call telemetry record into the database."""
    cost = calculate_llm_cost(model_name, input_tokens, output_tokens)
    
    print(f"[Telemetry] Logging {stage} LLM call | Model: {model_name} | Latency: {latency_ms}ms | Cost: ${cost:.6f}")
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        sql = """
            INSERT INTO telemetry_logs 
            (insight_id, stage, model_name, input_tokens, output_tokens, latency_ms, estimated_cost_usd)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        cursor.execute(sql, (insight_id, stage, model_name, input_tokens, output_tokens, latency_ms, cost))
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"[Telemetry Warning] Failed to save telemetry log to database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Test logger
    log_llm_call(
        insight_id="INC-TEST-000",
        stage="test",
        model_name="gemini-2.5-flash",
        input_tokens=1500,
        output_tokens=300,
        latency_ms=1250
    )
