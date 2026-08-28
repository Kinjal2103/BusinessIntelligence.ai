import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv
from pipeline.contract_loader import registry

# Load env variables
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=dotenv_path, override=True)
DB_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DB_URL)

def query_kpi_data(kpi_name, region=None, start_date=None, end_date=None, conn=None):
    """Query Supabase to fetch KPI data based on its contract definition."""
    contract = registry.get(kpi_name)
    if not contract:
        raise ValueError(f"KPI contract not found for: {kpi_name}")
        
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    query = contract.calculation
    
    # We will build filters depending on grain
    filters = []
    params = []
    
    # Check table schema and fields
    source = contract.source_table
    date_col = "date"
    if source == "server_latency_hourly":
        date_col = "timestamp"
    elif source == "support_tickets":
        date_col = "created_at"
    elif source == "churn_monthly":
        date_col = "month_start_date"
    elif source == "marketing_spend_weekly":
        date_col = "week_start_date"
        
    if region:
        filters.append(f"region = %s")
        params.append(region)
        
    if start_date:
        filters.append(f"{date_col} >= %s")
        params.append(start_date)
        
    if end_date:
        filters.append(f"{date_col} <= %s")
        params.append(end_date)
        
    if filters:
        filter_str = " AND ".join(filters)
        sql = f"SELECT * FROM ({query}) AS sub WHERE {filter_str}"
    else:
        sql = query
        
    df = pd.read_sql(sql, conn, params=params)
    if should_close:
        conn.close()
    
    # Standardize column names for date/timestamp
    if date_col in df.columns:
        df['datetime'] = pd.to_datetime(df[date_col])
    elif 'created_at' in df.columns:
        df['datetime'] = pd.to_datetime(df['created_at'])
    elif 'timestamp' in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'])
        
    return df

def resample_to_daily(df, value_col, agg_func="sum"):
    """Resample finer grain (hourly/event) to daily."""
    df = df.copy()
    df['date'] = df['datetime'].dt.date
    
    if agg_func == "sum":
        return df.groupby(['date', 'region'])[value_col].sum().reset_index()
    elif agg_func == "mean":
        return df.groupby(['date', 'region'])[value_col].mean().reset_index()
    elif agg_func == "count":
        return df.groupby(['date', 'region'])[value_col].count().reset_index()
    else:
        return df.groupby(['date', 'region'])[value_col].first().reset_index()

def align_kpis(kpi_x, kpi_y, region=None, start_date=None, end_date=None, conn=None):
    """Align two KPIs to a common grain and calendar, returning a joined DataFrame."""
    contract_x = registry.get(kpi_x)
    contract_y = registry.get(kpi_y)
    
    df_x = query_kpi_data(kpi_x, region, start_date, end_date, conn=conn)
    df_y = query_kpi_data(kpi_y, region, start_date, end_date, conn=conn)
    
    if df_x.empty or df_y.empty:
        return pd.DataFrame()
        
    # Determine the coarse grain
    grain_hierarchy = {"event": 0, "hourly": 1, "daily": 2, "weekly": 3, "monthly": 4}
    grain_x = contract_x.grain
    grain_y = contract_y.grain
    
    target_grain = grain_x if grain_hierarchy[grain_x] >= grain_hierarchy[grain_y] else grain_y
    
    # Value columns to preserve and join
    val_x = "revenue" if kpi_x == "revenue" else ("avg_latency_ms" if kpi_x == "server_latency" else ("spend" if kpi_x == "marketing_spend" else ("churn_rate" if kpi_x == "churn" else "ticket_id")))
    val_y = "revenue" if kpi_y == "revenue" else ("avg_latency_ms" if kpi_y == "server_latency" else ("spend" if kpi_y == "marketing_spend" else ("churn_rate" if kpi_y == "churn" else "ticket_id")))
    
    # 1. Process KPI X to target grain
    df_x_aligned = process_to_grain(df_x, kpi_x, grain_x, target_grain, val_x)
    # Rename value column to avoid collision
    df_x_aligned = df_x_aligned.rename(columns={val_x: kpi_x})
    
    # 2. Process KPI Y to target grain
    df_y_aligned = process_to_grain(df_y, kpi_y, grain_y, target_grain, val_y)
    df_y_aligned = df_y_aligned.rename(columns={val_y: kpi_y})
    
    # Ensure join key date type matches
    df_x_aligned['join_date'] = pd.to_datetime(df_x_aligned['date'])
    df_y_aligned['join_date'] = pd.to_datetime(df_y_aligned['date'])
    
    # Perform inner merge on join_date and region
    merged = pd.merge(df_x_aligned, df_y_aligned, on=['join_date', 'region'], suffixes=('_x', '_y'))
    
    # Clean up and sort
    merged = merged.drop(columns=['date_x', 'date_y'], errors='ignore')
    merged = merged.rename(columns={'join_date': 'date'})
    merged = merged.sort_values(by=['region', 'date'])
    
    return merged[['date', 'region', kpi_x, kpi_y]]

def process_to_grain(df, kpi_name, current_grain, target_grain, val_col):
    """Aggregate or resample a DataFrame from current_grain to target_grain."""
    df = df.copy()
    
    if current_grain == target_grain:
        # If grains are equal, just return key columns
        # Aggregate duplicates if any
        date_key = "date"
        if current_grain == "hourly" or current_grain == "event":
            df['date'] = df['datetime']
            date_key = "date"
        elif current_grain == "weekly":
            df['date'] = pd.to_datetime(df['week_start_date']).dt.date
        elif current_grain == "monthly":
            df['date'] = pd.to_datetime(df['month_start_date']).dt.date
            
        agg_func = "count" if kpi_name == "support_tickets" else ("mean" if kpi_name == "server_latency" else "sum")
        if agg_func == "count":
            return df.groupby(['date', 'region'])[val_col].count().reset_index()
        elif agg_func == "mean":
            return df.groupby(['date', 'region'])[val_col].mean().reset_index()
        else:
            return df.groupby(['date', 'region'])[val_col].sum().reset_index()
            
    # If resampling is needed
    if target_grain == "daily":
        agg_func = "count" if kpi_name == "support_tickets" else "mean"
        return resample_to_daily(df, val_col, agg_func)
        
    elif target_grain == "weekly":
        # Group by week starting Monday
        df['date'] = df['datetime'].dt.to_period('W-SUN').dt.start_time
        agg_func = "count" if kpi_name == "support_tickets" else ("mean" if kpi_name == "server_latency" else "sum")
        if agg_func == "count":
            return df.groupby(['date', 'region'])[val_col].count().reset_index()
        elif agg_func == "mean":
            return df.groupby(['date', 'region'])[val_col].mean().reset_index()
        else:
            return df.groupby(['date', 'region'])[val_col].sum().reset_index()
            
    elif target_grain == "monthly":
        # Group by month start date
        df['date'] = df['datetime'].dt.to_period('M').dt.start_time
        agg_func = "count" if kpi_name == "support_tickets" else ("mean" if kpi_name == "server_latency" else "sum")
        if agg_func == "count":
            return df.groupby(['date', 'region'])[val_col].count().reset_index()
        elif agg_func == "mean":
            return df.groupby(['date', 'region'])[val_col].mean().reset_index()
        else:
            return df.groupby(['date', 'region'])[val_col].sum().reset_index()

    return df

if __name__ == "__main__":
    # Test reconciliation between hourly latency and daily revenue
    print("Testing reconciliation: server_latency (hourly) & revenue (daily)...")
    try:
        aligned_df = align_kpis("server_latency", "revenue", region="Southeast", start_date="2026-08-10", end_date="2026-08-20")
        print(aligned_df.head(10))
        print("Success! Merged data size:", len(aligned_df))
    except Exception as e:
        print(f"Failed: {e}")
