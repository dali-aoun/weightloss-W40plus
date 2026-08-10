import os, requests, json
from datetime import datetime, timedelta, timezone

result = {}
pt       = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
ig_token = os.environ.get("LONG_LIVED_TOKEN", "")
ig_id    = os.environ.get("INSTAGRAM_USER_ID", "")
headers_p = {"Authorization": f"Bearer {pt}"}

today = datetime.now(timezone.utc).date()
end   = today.strftime("%Y-%m-%d")

# ── Pinterest: account-level analytics (30 days) ──────────────────
start30 = (today - timedelta(days=30)).strftime("%Y-%m-%d")
r_ua = requests.get(
    "https://api.pinterest.com/v5/user_account/analytics",
    params={"start_date": start30, "end_date": end,
            "metric_types": "IMPRESSION,OUTBOUND_CLICK,PIN_CLICK,SAVE"},
    headers=headers_p)
print(f"Pinterest account analytics: {r_ua.status_code}")
if r_ua.ok:
    ua = r_ua.json()
    result["pinterest_account_analytics"] = ua
    summary = ua.get("all", {}).get("summary_metrics", {})
    result["pinterest_summary"] = summary
    print(f"Pinterest 30d: Impressions={summary.get('IMPRESSION',0)} | Outbound={summary.get('OUTBOUND_CLICK',0)} | PIN_CLICK={summary.get('PIN_CLICK',0)} | SAVE={summary.get('SAVE',0)}")
else:
    result["pinterest_account_analytics_error"] = r_ua.text[:300]
    print(f"Pinterest analytics error: {r_ua.text[:200]}")

# ── Pinterest: boards ──────────────────────────────────────────────
r_boards = requests.get("https://api.pinterest.com/v5/boards",
    params={"page_size": 25}, headers=headers_p)
if r_boards.ok:
    boards = r_boards.json().get("items", [])
    result["pinterest_boards"] = [{"id": b["id"], "name": b.get("name",""), "pin_count": b.get("pin_count",0)} for b in boards]
    result["pinterest_boards_count"] = len(boards)

# ── Instagram: account info ────────────────────────────────────────
r_acc = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}",
    params={"fields": "username,followers_count,media_count,biography,website", "access_token": ig_token}
)
print(f"Instagram account: {r_acc.status_code}")
result["instagram_account"] = r_acc.json() if r_acc.ok else {"error": r_acc.text[:300]}
if r_acc.ok:
    acc = r_acc.json()
    print(f"  @{acc.get('username','?')} | Followers: {acc.get('followers_count','?')} | Posts: {acc.get('media_count','?')}")

# ── Instagram: daily metrics 14 days ──────────────────────────────
since_ts = int((datetime.now(timezone.utc) - timedelta(days=14)).timestamp())
until_ts = int(datetime.now(timezone.utc).timestamp())

def fetch_ig_metric(metric):
    r = requests.get(
        f"https://graph.instagram.com/v21.0/{ig_id}/insights",
        params={"metric": metric, "period": "day", "since": since_ts, "until": until_ts, "access_token": ig_token}
    )
    if r.ok:
        return r.json().get("data", [{}])[0].get("values", [])
    return []

result["instagram_reach_14d"]       = fetch_ig_metric("reach")
result["instagram_profile_views_14d"] = fetch_ig_metric("profile_views")
result["instagram_website_clicks_14d"] = fetch_ig_metric("website_clicks")
result["instagram_interactions_14d"]  = fetch_ig_metric("total_interactions")

reach_vals = [v.get("value",0) for v in result["instagram_reach_14d"]]
wc_vals    = [v.get("value",0) for v in result["instagram_website_clicks_14d"]]
print(f"Reach 14d: {reach_vals}")
print(f"Website_clicks 14d: {wc_vals}")

# ── Instagram: recent 20 media with per-type insights ─────────────
r_media = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}/media",
    params={"fields": "id,media_type,timestamp,like_count,comments_count", "limit": 25, "access_token": ig_token}
)
print(f"Instagram media: {r_media.status_code}")
if r_media.ok:
    media_items = r_media.json().get("data", [])
    result["instagram_recent_media"] = media_items
    media_insights = []
    for m in media_items[:20]:
        mtype = m.get("media_type", "IMAGE")
        if mtype == "VIDEO":
            metrics = "reach,saved,shares,plays"
        else:
            metrics = "reach,saved,shares"
        ri = requests.get(
            f"https://graph.instagram.com/v21.0/{m['id']}/insights",
            params={"metric": metrics, "access_token": ig_token}
        )
        if ri.ok:
            vals = {}
            for v in ri.json().get("data", []):
                name = v["name"]
                # value can be in values[0]["value"] or directly in "value"
                if v.get("values"):
                    vals[name] = v["values"][0]["value"]
                elif "value" in v:
                    vals[name] = v["value"]
            media_insights.append({
                "id": m["id"],
                "type": mtype,
                "date": m["timestamp"][:10],
                "likes": m.get("like_count", 0),
                "comments": m.get("comments_count", 0),
                **vals
            })
        else:
            err = ri.json().get("error", {}).get("message", ri.text[:100])
            media_insights.append({"id": m["id"], "type": mtype, "date": m["timestamp"][:10], "error": err[:80]})
    result["instagram_media_insights"] = media_insights
    # Print summary
    print("\n=== RECENT MEDIA (newest first) ===")
    for m in media_insights[:10]:
        if "error" not in m:
            print(f"  {m.get('date','?')} {m.get('type','?')} reach={m.get('reach','?')} saved={m.get('saved','?')} plays={m.get('plays','?')}")
        else:
            print(f"  {m.get('date','?')} {m.get('type','?')} ERR: {m.get('error','?')[:60]}")

# ── Save ──────────────────────────────────────────────────────────
result["generated_at"] = datetime.now(timezone.utc).isoformat()
os.makedirs("analytics", exist_ok=True)
with open("analytics/snapshot.json", "w") as f:
    json.dump(result, f, indent=2)
print("\n=== SAVED ===")
ps = result.get("pinterest_summary", {})
print(f"Pinterest: Impressions={ps.get('IMPRESSION','?')} | Outbound={ps.get('OUTBOUND_CLICK','?')} | Saves={ps.get('SAVE','?')}")
