import os, requests, json
from datetime import datetime, timedelta, timezone

result = {}

# ── Pinterest Analytics ──────────────────────────────────────────────
pt = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
headers_p = {"Authorization": f"Bearer {pt}", "Content-Type": "application/json"}

today = datetime.now(timezone.utc).date()
start30 = (today - timedelta(days=30)).strftime("%Y-%m-%d")
start7  = (today - timedelta(days=7)).strftime("%Y-%m-%d")
end     = today.strftime("%Y-%m-%d")

METRICS = "IMPRESSION,OUTBOUND_CLICK,SAVE,PIN_CLICK,ENGAGEMENT"

# 30-day totals
r30 = requests.get(
    "https://api.pinterest.com/v5/user_account/analytics",
    params={"start_date": start30, "end_date": end, "metric_types": METRICS},
    headers=headers_p
)
print(f"Pinterest 30d: {r30.status_code}")
result["pinterest_30d"] = r30.json() if r30.ok else {"error": r30.text[:300]}

# 7-day totals
r7 = requests.get(
    "https://api.pinterest.com/v5/user_account/analytics",
    params={"start_date": start7, "end_date": end, "metric_types": METRICS},
    headers=headers_p
)
print(f"Pinterest 7d: {r7.status_code}")
result["pinterest_7d"] = r7.json() if r7.ok else {"error": r7.text[:300]}

# Top pins (7 days, by impression)
rtp = requests.get(
    "https://api.pinterest.com/v5/user_account/analytics/top_pins",
    params={"start_date": start7, "end_date": end,
            "sort_by": "IMPRESSION", "num_of_pins": 10,
            "metric_types": METRICS},
    headers=headers_p
)
print(f"Top pins: {rtp.status_code}")
result["top_pins"] = rtp.json() if rtp.ok else {"error": rtp.text[:300]}

# Daily breakdown (7 days)
rd = requests.get(
    "https://api.pinterest.com/v5/user_account/analytics",
    params={"start_date": start7, "end_date": end,
            "metric_types": METRICS, "granularity": "DAY"},
    headers=headers_p
)
print(f"Pinterest daily: {rd.status_code}")
result["pinterest_daily"] = rd.json() if rd.ok else {"error": rd.text[:300]}

# ── Instagram Insights ───────────────────────────────────────────────
ig_token = os.environ.get("LONG_LIVED_TOKEN", "")
ig_id    = os.environ.get("INSTAGRAM_USER_ID", "")

since_ts = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
until_ts = int(datetime.now(timezone.utc).timestamp())

r_ig = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}/insights",
    params={
        "metric": "impressions,reach,profile_views,website_clicks,follower_count",
        "period": "day",
        "since": since_ts,
        "until": until_ts,
        "access_token": ig_token
    }
)
print(f"Instagram insights: {r_ig.status_code}")
result["instagram_7d"] = r_ig.json() if r_ig.ok else {"error": r_ig.text[:300]}

# ── Save ─────────────────────────────────────────────────────────────
result["generated_at"] = datetime.now(timezone.utc).isoformat()
os.makedirs("analytics", exist_ok=True)
with open("analytics/snapshot.json", "w") as f:
    json.dump(result, f, indent=2)

print("\n=== SNAPSHOT PREVIEW ===")
print(json.dumps(result, indent=2)[:2000])
