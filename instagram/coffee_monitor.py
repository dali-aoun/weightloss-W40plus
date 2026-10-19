"""
Instagram COFFEE Comment Monitor
- Scanne les 20 derniers posts toutes les heures
- Quand quelqu'un commente "COFFEE" -> DM avec lien Java Burn
- Fallback reponse publique si DM echoue
"""

import requests
import json
import os
import sys
from datetime import datetime

INSTAGRAM_USER_ID = os.environ["INSTAGRAM_USER_ID"]
LONG_LIVED_TOKEN  = os.environ["LONG_LIVED_TOKEN"]
BASE_URL          = "https://graph.instagram.com/v21.0"

KEYWORD      = "COFFEE"
REPLIED_FILE = "instagram/coffee_replied.json"
MAX_POSTS    = 20

DM_TEXT = (
    "Hey! ☕ Here's your free Java Burn morning ritual as promised!\n\n"
    "Watch this short 2-min video made for women 40+:\n"
    "-> coffee.thehappy-healthy-life.com\n\n"
    "It explains exactly why cortisol blocks weight loss after 40 "
    "and the specific coffee ritual that resets it in 21 days.\n\n"
    "Limited-time offer inside \U0001f4ab"
)

PUBLIC_REPLY_TEXT = (
    "Done! ☕ Here's the link:\n"
    "-> coffee.thehappy-healthy-life.com\n\n"
    "Short 2-min video made for women 40+ \U0001f525"
)


def log(msg):
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] {msg}", flush=True)


def load_replied():
    if os.path.exists(REPLIED_FILE):
        with open(REPLIED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_replied(data):
    with open(REPLIED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_recent_media():
    try:
        r = requests.get(
            f"{BASE_URL}/{INSTAGRAM_USER_ID}/media",
            params={
                "fields": "id,timestamp,media_type",
                "limit": MAX_POSTS,
                "access_token": LONG_LIVED_TOKEN
            },
            timeout=30
        )
        data = r.json()
        if "error" in data:
            log(f"Erreur media: {data['error'].get('message', data)}")
            return []
        return data.get("data", [])
    except Exception as e:
        log(f"Exception get_recent_media: {e}")
        return []


def get_comments(media_id):
    try:
        r = requests.get(
            f"{BASE_URL}/{media_id}/comments",
            params={
                "fields": "id,text,username,timestamp,from",
                "access_token": LONG_LIVED_TOKEN
            },
            timeout=30
        )
        data = r.json()
        if "error" in data:
            return []
        return data.get("data", [])
    except Exception as e:
        log(f"  Erreur comments {media_id}: {e}")
        return []


def send_dm(recipient_id, username):
    try:
        r = requests.post(
            f"{BASE_URL}/{INSTAGRAM_USER_ID}/messages",
            json={
                "recipient": {"id": recipient_id},
                "message":   {"text": DM_TEXT}
            },
            params={"access_token": LONG_LIVED_TOKEN},
            timeout=30
        )
        result = r.json()
        if "message_id" in result or "id" in result:
            log(f"  DM envoye -> @{username}")
            return True
        log(f"  DM echoue @{username}: {result.get('error', {}).get('message', result)}")
        return False
    except Exception as e:
        log(f"  Exception DM @{username}: {e}")
        return False


def send_public_reply(comment_id, username):
    try:
        r = requests.post(
            f"{BASE_URL}/{comment_id}/replies",
            params={"access_token": LONG_LIVED_TOKEN},
            data={"message": f"@{username} {PUBLIC_REPLY_TEXT}"},
            timeout=30
        )
        result = r.json()
        if "id" in result:
            log(f"  Reponse publique -> @{username}")
            return True
        log(f"  Reponse publique echouee: {result.get('error', {}).get('message', result)}")
        return False
    except Exception as e:
        log(f"  Exception reply @{username}: {e}")
        return False


def main():
    log("=== COFFEE Monitor (Java Burn) ===")

    replied = load_replied()
    new_replies = 0
    changed = False

    posts = get_recent_media()
    log(f"{len(posts)} posts recents trouves")

    for post in posts:
        media_id   = post["id"]
        media_type = post.get("media_type", "?")
        timestamp  = post.get("timestamp", "?")[:10]

        comments = get_comments(media_id)
        if not comments:
            continue

        log(f"Post {media_id} ({media_type} {timestamp}): {len(comments)} commentaire(s)")

        for comment in comments:
            comment_id = comment.get("id", "")
            text = comment.get("text", "")

            if KEYWORD.lower() not in text.lower():
                continue
            if comment_id in replied:
                continue

            from_data = comment.get("from", {})
            user_id   = from_data.get("id")
            username  = from_data.get("username", "?")

            log(f"  COFFEE detecte! @{username} : '{text[:60]}'")

            method = "none"
            if user_id and send_dm(user_id, username):
                method = "dm"
            elif send_public_reply(comment_id, username):
                method = "public_reply"
            else:
                log(f"  Echec total pour @{username}, on reessaiera")
                continue

            replied[comment_id] = {
                "user_id":      user_id,
                "username":     username,
                "media_id":     media_id,
                "method":       method,
                "replied_at":   datetime.utcnow().isoformat(),
                "comment_text": text[:100]
            }
            new_replies += 1
            changed = True

    if changed:
        save_replied(replied)
        log(f"=== {new_replies} reponse(s) envoyee(s) - replied.json mis a jour ===")
    else:
        log("=== Aucun nouveau commentaire COFFEE ===")

    sys.exit(0)


if __name__ == "__main__":
    main()
