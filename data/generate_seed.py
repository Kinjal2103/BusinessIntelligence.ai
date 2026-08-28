import csv
import os
import random
from datetime import datetime, timedelta

# Create data directory if not exists
os.makedirs("data", exist_ok=True)

# Set random seed for reproducibility
random.seed(42)

start_date = datetime(2026, 6, 1)
end_date = datetime(2026, 8, 24)
delta_days = (end_date - start_date).days + 1

regions = ["Southeast", "Northeast", "Midwest", "West"]
new_region = "Europe"

# 1. Generate Revenue Daily (grain: daily, by region)
revenue_rows = []
for day_idx in range(delta_days):
    curr_date = start_date + timedelta(days=day_idx)
    date_str = curr_date.strftime("%Y-%m-%d")
    
    # Normal regions
    for region in regions:
        # Determine base revenue
        if region == "Southeast":
            base = 50000
        elif region == "Northeast":
            base = 40000
        elif region == "Midwest":
            base = 30000
        else: # West
            base = 45000
            
        # Add random noise (+/- 5%)
        noise = random.uniform(-0.05, 0.05)
        revenue = base * (1 + noise)
        
        # Scenario 1: Acute Case - Payment Gateway Outage in Southeast on 2026-08-15
        if region == "Southeast" and date_str == "2026-08-15":
            revenue = base * 0.2  # 80% drop in revenue
            
        # Scenario 2: Structural Case - Slow 30-day decline in Northeast starting 2026-07-01
        if region == "Northeast" and datetime(2026, 7, 1) <= curr_date <= datetime(2026, 7, 30):
            # Decline reaches up to 25% by the end of July
            day_in_decline = (curr_date - datetime(2026, 7, 1)).days
            decline_pct = (day_in_decline / 30.0) * 0.25
            revenue = base * (1 - decline_pct + noise)
            
        # Scenario 3: Unconfirmed Case - Server Latency Blip in West on 2026-08-20
        # Correlation: Latency blip causes 15% revenue drop on that day
        if region == "West" and date_str == "2026-08-20":
            revenue = base * 0.85 * (1 + noise)
            
        revenue_rows.append([date_str, region, round(revenue, 2)])
        
    # Scenario 4: Sparse-History Case - Europe launched on 2026-08-10 (under 8 weeks of data)
    if curr_date >= datetime(2026, 8, 10):
        base = 15000
        noise = random.uniform(-0.05, 0.05)
        revenue = base * (1 + noise)
        revenue_rows.append([date_str, new_region, round(revenue, 2)])

with open("data/revenue_daily.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["date", "region", "revenue"])
    writer.writerows(revenue_rows)


# 2. Generate Support Tickets (grain: event-level, Zendesk style)
ticket_rows = []
ticket_id_counter = 1000

# Base daily ticket volumes
region_ticket_base = {
    "Southeast": 15,
    "Northeast": 12,
    "Midwest": 8,
    "West": 10,
    "Europe": 3
}

categories = ["Login Issue", "Product Question", "Billing", "Shipping", "Refund Request", "Bug Report"]

for day_idx in range(delta_days):
    curr_date = start_date + timedelta(days=day_idx)
    date_str = curr_date.strftime("%Y-%m-%d")
    
    # Generate baseline tickets for active regions
    active_regions = regions.copy()
    if curr_date >= datetime(2026, 8, 10):
        active_regions.append(new_region)
        
    for region in active_regions:
        base_vol = region_ticket_base[region]
        # Random count around baseline
        count = max(0, int(random.gauss(base_vol, 3)))
        
        # Scenario 1: Acute Case - Payment Gateway Outage in Southeast on 2026-08-15
        # Southeast has a massive ticket spike in a short window on 2026-08-15
        is_outage_day = (region == "Southeast" and date_str == "2026-08-15")
        if is_outage_day:
            count += 45  # Spike of payment failure tickets
            
        for _ in range(count):
            ticket_id_counter += 1
            # Random time of day
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            
            # For Scenario 1, cluster the spike between 14:00 and 16:15
            if is_outage_day and len(ticket_rows) % 2 == 0:
                hour = random.choice([14, 15])
                minute = random.randint(0, 59)
                category = "Billing"
                priority = "High"
                desc = "Error: payment gateway timeout at checkout. Transaction failed."
            else:
                category = random.choice(categories)
                priority = random.choice(["Low", "Medium", "High"])
                desc = f"Customer inquiry regarding {category.lower()} issue."
                
            timestamp = f"{date_str} {hour:02d}:{minute:02d}:00"
            status = random.choice(["Closed", "Closed", "Closed", "Open", "Solved"])
            if is_outage_day and category == "Billing":
                status = "Open"
                
            ticket_rows.append([
                f"TKT-{ticket_id_counter}",
                f"USR-{random.randint(10000, 99999)}",
                region,
                timestamp,
                category,
                priority,
                status,
                desc
            ])

with open("data/support_tickets.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ticket_id", "customer_id", "region", "created_at", "category", "priority", "status", "description"])
    writer.writerows(ticket_rows)


# 3. Generate Marketing Spend Weekly (grain: weekly, by campaign)
marketing_rows = []
campaigns = ["AdWords_Search", "Facebook_Retargeting", "LinkedIn_B2B", "Influencer_Launch"]

# Weekly cadence (every Monday)
curr_date = start_date
while curr_date <= end_date:
    # Check if Monday
    if curr_date.weekday() == 0:
        date_str = curr_date.strftime("%Y-%m-%d")
        for region in regions:
            for campaign in campaigns:
                # Normal spend base
                base_spend = 1000
                if campaign == "AdWords_Search":
                    base_spend = 2500
                elif campaign == "Facebook_Retargeting":
                    base_spend = 1500
                
                spend = base_spend * (1 + random.uniform(-0.1, 0.1))
                marketing_rows.append([date_str, region, campaign, round(spend, 2)])
                
        # Europe starts marketing spend from 2026-08-10
        if curr_date >= datetime(2026, 8, 10):
            for campaign in campaigns[:2]:
                spend = 800 * (1 + random.uniform(-0.1, 0.1))
                marketing_rows.append([date_str, new_region, campaign, round(spend, 2)])
                
    curr_date += timedelta(days=1)

with open("data/marketing_spend_weekly.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["week_start_date", "region", "campaign_name", "spend"])
    writer.writerows(marketing_rows)


# 4. Generate Server Latency Hourly (grain: hourly)
latency_rows = []
for day_idx in range(delta_days):
    curr_date = start_date + timedelta(days=day_idx)
    date_str = curr_date.strftime("%Y-%m-%d")
    
    active_regions = regions.copy()
    if curr_date >= datetime(2026, 8, 10):
        active_regions.append(new_region)
        
    for region in active_regions:
        for hour in range(24):
            timestamp = f"{date_str} {hour:02d}:00:00"
            
            # Baseline latency
            if region == "West":
                base_latency = 120  # West region baseline
            elif region == "Europe":
                base_latency = 180
            else:
                base_latency = 90
                
            latency = base_latency + random.uniform(-10, 10)
            
            # Scenario 3: Unconfirmed Case - Latency spike in West on 2026-08-20 from 10:00 to 16:00
            if region == "West" and date_str == "2026-08-20" and 10 <= hour <= 16:
                latency = 1500 + random.uniform(-100, 100)  # Heavy spike
                
            latency_rows.append([timestamp, region, round(latency, 1)])

with open("data/server_latency_hourly.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "region", "avg_latency_ms"])
    writer.writerows(latency_rows)


# 5. Generate Customer Churn Monthly (grain: monthly)
churn_rows = []
# June, July, August 2026
months = [datetime(2026, 6, 1), datetime(2026, 7, 1), datetime(2026, 8, 1)]

for month in months:
    month_str = month.strftime("%Y-%m-%d")
    
    # Normal regions
    for region in regions:
        churn_rate = 0.02 + random.uniform(-0.005, 0.005) # 2% baseline
        cust_count = 10000
        
        # Scenario 2: Structural Case - Slow 30-day decline in July for Northeast
        # Correlated with a rise in monthly churn rate
        if region == "Northeast" and month.month == 7:
            churn_rate = 0.062  # July Northeast churn spikes to 6.2%
            
        churn_rows.append([month_str, region, round(churn_rate, 4), cust_count])
        
    # Europe has churn data only for August
    if month.month == 8:
        churn_rows.append([month_str, new_region, 0.015, 1200])

with open("data/churn_monthly.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["month_start_date", "region", "churn_rate", "customer_count"])
    writer.writerows(churn_rows)

print("Seed CSV files generated successfully in /data folder.")
