import os, requests, json
from datetime import datetime, timedelta, timezone

result = {}
pt       = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
ig_token = os.environ.get("LONG_LIVED_TOKEN", "")
ig_id    = os.environ.get("INSTAGRAM_USER_ID", "")
headers_p = {"Authorization": f"Bearer {pt}"}

today = datetime.now(timezone.utc).date()
end   = today.strftime("%Y-%m-%d")

# ── Pinterest: list boards (works with pins:read) ────────────────────
r_boards = requests.get("https://api.pinterest.com/v5/boards",
    params={"page_size": 25}, headers=headers_p)
print(f"Pinterest boards: {r_boards.status_code}")
if r_boards.ok:
    boards = r_boards.json().get("items", [])
    result["pinterest_boards"] = [{"id": b["id"], "name": b.get("name",""), "pin_count": b.get("pin_count", 0)} for b in boards]
    result["pinterest_boards_count"] = len(boards)
else:
    result["pinterest_boards_error"] = r_boards.text[:300]

# ── Pinterest: recent pins via board ────────────────────────────────
pin_ids = []
if r_boards.ok:
    for b in r_boards.json().get("items", [])[:3]:
        rpins = requests.get(f"https://api.pinterest.com/v5/boards/{b['id']}/pins",
            params={"page_size": 5}, headers=headers_p)
        if rpins.ok:
            for p in rpins.json().get("items", []):
                pin_ids.append({"pin_id": p["id"], "board": b["name"], "title": p.get("note","")[:60]})

result["recent_pin_ids_sample"] = pin_ids[:10]

# Try analytics on one pin
if pin_ids:
    start7 = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    rpa = requests.get(
        f"https://api.pinterest.com/v5/pins/{pin_ids[0]['pin_id']}/analytics",
        params={"start_date": start7, "end_date": end,
                "metric_types": "IMPRESSION,OUTBOUND_CLICK,SAVE,PIN_CLICK"},
        headers=headers_p)
    print(f"Pin analytics test: {rpa.status_code}")
    result["pin_analytics_test"] = rpa.json() if rpa.ok else {"error": rpa.text[:300]}

# ── Instagram: account info ──────────────────────────────────────────
r_acc = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}",
    params={"fields": "username,followers_count,media_count,biography,website", "access_token": ig_token}
)
print(f"Instagram account: {r_acc.status_code}")
result["instagram_account"] = r_acc.json() if r_acc.ok else {"error": r_acc.text[:300]}

# ── Instagram: daily reach (7 days) ─────────────────────────────────
since_ts = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
until_ts = int(datetime.now(timezone.utc).timestamp())

r_reach = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}/insights",
    params={"metric": "reach", "period": "day", "since": since_ts, "until": until_ts, "access_token": ig_token}
)
print(f"Instagram reach: {r_reach.status_code}")
def ig_metric(resp, key):
    try:
        return resp.json().get("data", [])[0].get("values", [])
    except (IndexError, KeyError, AttributeError):
        return []

result["instagram_reach_7d"] = ig_metric(r_reach, "reach") if r_reach.ok else []

# profile_views
r_pv = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}/insights",
    params={"metric": "profile_views", "period": "day", "since": since_ts, "until": until_ts, "access_token": ig_token}
)
print(f"Instagram profile_views: {r_pv.status_code}")
result["instagram_profile_views_7d"] = ig_metric(r_pv, "profile_views") if r_pv.ok else []

# website_clicks
r_wc = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}/insights",
    params={"metric": "website_clicks", "period": "day", "since": since_ts, "until": until_ts, "access_token": ig_token}
)
print(f"Instagram website_clicks: {r_wc.status_code}")
result["instagram_website_clicks_7d"] = ig_metric(r_wc, "website_clicks") if r_wc.ok else []

# total_interactions (likes+comments+saves+shares)
r_ti = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}/insights",
    params={"metric": "total_interactions", "period": "day", "since": since_ts, "until": until_ts, "access_token": ig_token}
)
print(f"Instagram interactions: {r_ti.status_code}")
result["instagram_interactions_7d"] = ig_metric(r_ti, "total_interactions") if r_ti.ok else []

# ── Instagram: recent media with insights ───────────────────────────
r_media = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}/media",
    params={"fields": "id,media_type,timestamp,like_count,comments_count", "limit": 12, "access_token": ig_token}
)
print(f"Instagram media: {r_media.status_code}")
if r_media.ok:
    media_items = r_media.json().get("data", [])
    result["instagram_recent_media"] = media_items
    # Get insights for top 5
    media_insights = []
    for m in media_items[:5]:
        ri = requests.get(
            f"https://graph.instagram.com/v21.0/{m['id']}/insights",
            params={"metric": "reach,saved,shares", "access_token": ig_token}
        )
        if ri.ok:
            vals = {v["name"]: v["values"][0]["value"] if v.get("values") else v.get("value",0)
                    for v in ri.json().get("data", [])}
            media_insights.append({"id": m["id"], "type": m["media_type"], "date": m["timestamp"][:10], **vals})
        else:
            media_insights.append({"id": m["id"], "type": m["media_type"], "error": ri.text[:100]})
    result["instagram_media_insights"] = media_insights

# ── Save ─────────────────────────────────────────────────────────────
result["generated_at"] = datetime.now(timezone.utc).isoformat()
os.makedirs("analytics", exist_ok=True)
with open("analytics/snapshot.json", "w") as f:
    json.dump(result, f, indent=2)
print("\n=== KEY METRICS ===")
acc = result.get("instagram_account", {})
print(f"Username: @{acc.get('username','?')} | Followers: {acc.get('followers_count','?')} | Posts: {acc.get('media_count','?')}")
print("Reach 7d:", [v.get("value",0) for v in result.get("instagram_reach_7d", [])])
print("Profile_views 7d:", [v.get("value",0) for v in result.get("instagram_profile_views_7d", [])])
print("Website_clicks 7d:", [v.get("value",0) for v in result.get("instagram_website_clicks_7d", [])])
print("Interactions 7d:", [v.get("value",0) for v in result.get("instagram_interactions_7d", [])])
print("Media insights:", json.dumps(result.get("instagram_media_insights",[])[:3])[:400])
print("Pin analytics test:", json.dumps(result.get("pin_analytics_test",{}))[:300])
