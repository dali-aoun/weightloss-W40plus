import os, requests, json
from datetime import datetime, timedelta, timezone

result = {}
pt       = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
ig_token = os.environ.get("LONG_LIVED_TOKEN", "")
ig_id    = os.environ.get("INSTAGRAM_USER_ID", "")
headers_p = {"Authorization": f"Bearer {pt}"}

today   = datetime.now(timezone.utc).date()
start7  = (today - timedelta(days=7)).strftime("%Y-%m-%d")
start30 = (today - timedelta(days=30)).strftime("%Y-%m-%d")
end     = today.strftime("%Y-%m-%d")

# ── Pinterest: try boards list (pins:read scope) ─────────────────────
r_boards = requests.get("https://api.pinterest.com/v5/boards",
    params={"page_size": 25}, headers=headers_p)
print(f"Pinterest boards: {r_boards.status_code}")
if r_boards.ok:
    boards = r_boards.json().get("items", [])
    result["pinterest_boards_count"] = len(boards)
    board_data = []
    for b in boards[:5]:  # top 5 boards
        bid = b["id"]
        bname = b.get("name","?")
        # board analytics (requires ads:read OR user_accounts:read — may fail)
        ra = requests.get(
            f"https://api.pinterest.com/v5/boards/{bid}/analytics",
            params={"start_date": start7, "end_date": end,
                    "metric_types": "IMPRESSION,OUTBOUND_CLICK,SAVE,PIN_CLICK"},
            headers=headers_p)
        if ra.ok:
            board_data.append({"board": bname, "id": bid, "analytics": ra.json()})
        else:
            board_data.append({"board": bname, "id": bid, "error": ra.json()})
    result["pinterest_boards"] = board_data
else:
    result["pinterest_boards_error"] = r_boards.text[:300]

# ── Pinterest: try user analytics (needs user_accounts:read) ─────────
r_ua = requests.get("https://api.pinterest.com/v5/user_account/analytics",
    params={"start_date": start30, "end_date": end,
            "metric_types": "IMPRESSION,OUTBOUND_CLICK,SAVE,PIN_CLICK,ENGAGEMENT"},
    headers=headers_p)
print(f"Pinterest user analytics: {r_ua.status_code}")
result["pinterest_30d"] = r_ua.json() if r_ua.ok else {"scope_error": True, "msg": r_ua.json().get("message","")}

# ── Pinterest: token info (what scopes do we have?) ──────────────────
r_me = requests.get("https://api.pinterest.com/v5/user_account", headers=headers_p)
print(f"Pinterest user_account: {r_me.status_code}")
result["pinterest_token_info"] = r_me.json() if r_me.ok else {"error": r_me.text[:200]}

# ── Instagram: correct metrics ───────────────────────────────────────
# Period=day metrics (7 days via since/until)
r_ig = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}/insights",
    params={
        "metric": "reach,profile_views,website_clicks,total_interactions,accounts_engaged",
        "period": "day",
        "since": int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp()),
        "until": int(datetime.now(timezone.utc).timestamp()),
        "access_token": ig_token
    }
)
print(f"Instagram insights (day): {r_ig.status_code}")
result["instagram_7d_daily"] = r_ig.json() if r_ig.ok else {"error": r_ig.text[:400]}

# Follower count (period=week)
r_fol = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}/insights",
    params={
        "metric": "follower_count",
        "period": "week",
        "access_token": ig_token
    }
)
print(f"Instagram followers: {r_fol.status_code}")
result["instagram_followers"] = r_fol.json() if r_fol.ok else {"error": r_fol.text[:300]}

# Account summary
r_acc = requests.get(
    f"https://graph.instagram.com/v21.0/{ig_id}",
    params={"fields": "username,followers_count,media_count,biography", "access_token": ig_token}
)
print(f"Instagram account: {r_acc.status_code}")
result["instagram_account"] = r_acc.json() if r_acc.ok else {"error": r_acc.text[:300]}

# ── Save ─────────────────────────────────────────────────────────────
result["generated_at"] = datetime.now(timezone.utc).isoformat()
os.makedirs("analytics", exist_ok=True)
with open("analytics/snapshot.json", "w") as f:
    json.dump(result, f, indent=2)
print("\n=== RESULT ===")
print(json.dumps(result, indent=2)[:3000])
