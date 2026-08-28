import os
import json
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pipeline.contract_loader import registry

# Load env variables
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=dotenv_path, override=True)
DB_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DB_URL)

def load_threshold_overrides(kpi_name):
    """Load threshold overrides from Supabase config_overrides if they exist."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT pct_change_override, absolute_change_override FROM config_overrides WHERE kpi_name = %s;", (kpi_name,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            return {"pct_change": row[0], "absolute_change": row[1]}
    except Exception as e:
        # Silently ignore if table doesn't exist yet during bootstrapping
        pass
    finally:
        if conn:
            conn.close()
    return None

def load_kpi_dataframe(kpi_name):
    """Load the full historical dataset for a KPI from Supabase."""
    contract = registry.get(kpi_name)
    if not contract:
        raise ValueError(f"Contract not found for {kpi_name}")
        
    conn = get_connection()
    sql = contract.calculation
    df = pd.read_sql(sql, conn)
    conn.close()
    
    # Normalize date/timestamp columns to datetime
    date_col = "date"
    if "timestamp" in df.columns:
        date_col = "timestamp"
    elif "created_at" in df.columns:
        date_col = "created_at"
    elif "month_start_date" in df.columns:
        date_col = "month_start_date"
    elif "week_start_date" in df.columns:
        date_col = "week_start_date"
        
    df['datetime'] = pd.to_datetime(df[date_col])
    return df, date_col

def detect_anomalies_for_kpi(kpi_name):
    """Run anomaly detection algorithm for a specific KPI."""
    contract = registry.get(kpi_name)
    df, date_col = load_kpi_dataframe(kpi_name)
    
    if df.empty:
        return []
        
    # Value column to monitor
    val_col = "revenue" if kpi_name == "revenue" else ("avg_latency_ms" if kpi_name == "server_latency" else ("spend" if kpi_name == "marketing_spend" else ("churn_rate" if kpi_name == "churn" else "ticket_id")))
    
    # If the native grain is "event" (like support_tickets), we aggregate to daily counts for detection
    if contract.grain == "event":
        df['date'] = df['datetime'].dt.date
        df = df.groupby(['date', 'region']).size().reset_index(name='ticket_count')
        val_col = "ticket_count"
        date_col = "date"
        df['datetime'] = pd.to_datetime(df['date'])

    # Sort to ensure order
    df = df.sort_values(by=['region', 'datetime'])
    
    anomalies = []
    
    # Retrieve thresholds from contract or database overrides
    overrides = load_threshold_overrides(kpi_name)
    if overrides:
        min_pct = overrides["pct_change"]
        min_abs = overrides["absolute_change"]
        print(f"[{kpi_name}] Applying dynamic threshold overrides from recalibration: pct={min_pct:.4f}, abs={min_abs:.2f}")
    else:
        thresholds = contract.materiality_threshold
        min_pct = thresholds.get("pct_change", 0.15)
        min_abs = thresholds.get("absolute_change", 0.0)
    
    # Process region by region
    for region, region_df in df.groupby('region'):
        region_df = region_df.copy().reset_index(drop=True)
        n_rows = len(region_df)
        
        for idx in range(n_rows):
            curr_row = region_df.iloc[idx]
            curr_time = curr_row['datetime']
            curr_val = float(curr_row[val_col])
            
            # Determine history window (trailing 8 weeks, i.e., 56 days)
            # In monthly grain, 8 weeks translates to past available months
            # In hourly grain, we look at the same hour of day and day of week
            history_df = region_df[region_df['datetime'] < curr_time]
            
            # Calculate how much history is available in days
            if not history_df.empty:
                history_days = (curr_time - history_df['datetime'].min()).days
            else:
                history_days = 0
                
            low_history = (history_days < 56) # Less than 8 weeks of history
            
            mean, std = 0.0, 0.0
            
            if low_history:
                # SPARSE HISTORY FALLBACK
                # If we have very little history, use all available history points (no seasonality adjustment possible)
                if len(history_df) >= 3:
                    vals = history_df[val_col].astype(float).values
                    mean = float(np.mean(vals))
                    # Widen confidence interval by adding a minimum variance / multiplying std
                    std = float(np.std(vals))
                    std = max(std, mean * 0.15) # Ensure at least 15% standard deviation to avoid false positives
                else:
                    # Not enough points even to calculate a baseline, skip
                    continue
            else:
                # REGULAR ROLLING BASELINE WITH SEASONALITY
                # Filter history to trailing 12 weeks
                twelve_weeks_ago = curr_time - timedelta(weeks=12)
                recent_history = history_df[history_df['datetime'] >= twelve_weeks_ago]
                
                # Apply seasonality adjustment based on grain
                if contract.grain == "daily" or contract.grain == "event":
                    # Weekly seasonality: filter to same day of week (e.g. only Mondays)
                    day_of_week = curr_time.weekday()
                    seasonal_history = recent_history[recent_history['datetime'].dt.weekday == day_of_week]
                elif contract.grain == "hourly":
                    # Hourly seasonality: filter to same hour of day AND same day of week
                    hour_of_day = curr_time.hour
                    day_of_week = curr_time.weekday()
                    seasonal_history = recent_history[(recent_history['datetime'].dt.hour == hour_of_day) & 
                                                      (recent_history['datetime'].dt.weekday == day_of_week)]
                else:
                    # Weekly or monthly grains: use standard rolling history
                    seasonal_history = recent_history
                    
                if len(seasonal_history) >= 4:
                    vals = seasonal_history[val_col].astype(float).values
                    mean = float(np.mean(vals))
                    std = float(np.std(vals))
                else:
                    # Fallback if seasonal historical points are sparse
                    vals = recent_history[val_col].astype(float).values
                    mean = float(np.mean(vals))
                    std = float(np.std(vals))
                    
            # Compute statistical z-score
            # Avoid division by zero
            z_score = 0.0
            if std > 0:
                z_score = (curr_val - mean) / std
                
            # Configurable threshold: 2.0 for normal, 3.0 for sparse history to widen interval
            z_threshold = 3.0 if low_history else 2.0
            
            # Anomaly check:
            # We look for significant movements (spikes in latency/tickets/churn, drops in revenue)
            is_anomaly = False
            
            # Determine direction of anomaly we care about:
            # Revenue drop (z_score is negative)
            # Latency spike (z_score is positive)
            # Churn spike (z_score is positive)
            # Ticket spike (z_score is positive)
            if kpi_name == "revenue" and z_score <= -z_threshold:
                is_anomaly = True
            elif kpi_name in ["server_latency", "support_tickets", "churn"] and z_score >= z_threshold:
                is_anomaly = True
            elif kpi_name == "marketing_spend" and abs(z_score) >= z_threshold:
                is_anomaly = True
                
            if is_anomaly:
                # Check business-materiality thresholds
                abs_diff = abs(curr_val - mean)
                pct_diff = abs_diff / mean if mean > 0 else 0.0
                
                if abs_diff >= min_abs and pct_diff >= min_pct:
                    anomalies.append({
                        "kpi": kpi_name,
                        "timestamp": curr_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "region": region,
                        "actual": round(curr_val, 2),
                        "baseline_mean": round(mean, 2),
                        "baseline_std": round(std, 2),
                        "z_score": round(z_score, 2),
                        "pct_change": round(pct_diff, 4),
                        "absolute_change": round(abs_diff, 2),
                        "low_history_estimate": low_history
                    })
                    
    return anomalies

def run_detection():
    print("Running anomaly detection across all KPIs...")
    all_anomalies = []
    
    for kpi in registry.list_kpis():
        print(f"Detecting anomalies for '{kpi}'...")
        kpi_anomalies = detect_anomalies_for_kpi(kpi)
        print(f"Found {len(kpi_anomalies)} anomalies in '{kpi}'.")
        all_anomalies.extend(kpi_anomalies)
        
    # Sort anomalies by timestamp descending, and z-score magnitude
    all_anomalies = sorted(
        all_anomalies, 
        key=lambda x: (x['timestamp'], abs(x['z_score'])), 
        reverse=True
    )
    
    # Save output to pipeline/anomalies.json
    output_path = "pipeline/anomalies.json"
    with open(output_path, "w") as f:
        json.dump(all_anomalies, f, indent=2)
        
    print(f"\nSaved {len(all_anomalies)} anomalies to '{output_path}'.")
    return all_anomalies

if __name__ == "__main__":
    anoms = run_detection()
    # Print a few samples of detected anomalies
    print("\n--- Sample Detected Anomalies ---")
    for a in anoms[:10]:
        print(f"[{a['timestamp']}] KPI: {a['kpi']} | Region: {a['region']} | Actual: {a['actual']} (vs Baseline: {a['baseline_mean']}) | Z-Score: {a['z_score']} | Low History: {a['low_history_estimate']}")
