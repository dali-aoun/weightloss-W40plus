"""
publish_period.py — Pinterest auto-publisher (100% autonomous)
6 pins/jour: 2 slots x 3 pins
  Slot 08h: 2 standard + 1 video pin (Pexels)
  Slot 17h: 2 standard + 1 idea pin (multi-image)
"""

import os, sys, json, time, random, tempfile, traceback
from datetime import date, datetime, timezone, timedelta

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DONE_FILE    = os.path.join(BASE_DIR, "published_done.json")
LOG_FILE     = os.path.join(BASE_DIR, "publish_log.txt")
STATE_FILE   = os.path.join(BASE_DIR, "pin_auto_state.json")
CONTENT_FILE = os.path.join(BASE_DIR, "pin_content.json")
IMAGES_DIR   = os.path.join(BASE_DIR, "pin_images")

PINTEREST_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
PEXELS_API_KEY  = os.environ.get("PEXELS_API_KEY", "")
REPO_RAW = "https://raw.githubusercontent.com/dali-aoun/weightloss-W40plus/refs/heads/main/pinterest/pin_images"

LINK_POOL = [
    "https://smoothie.thehappy-healthy-life.com",
    "https://smoothie.thehappy-healthy-life.com/blog/cortisol-belly-fat",
    "https://smoothie.thehappy-healthy-life.com/blog/menopause-weight-loss",
    "https://smoothie.thehappy-healthy-life.com/blog/morning-routine",
]

BOARD_LINK_MAP = {
    "Hormonal Belly Fat Tips": 1,
    "Anti-Inflammatory Diet Tips": 1,
    "Menopause Weight Loss Tips": 2,
    "Before and After Transformations": 2,
    "Morning Routines for Weight Loss": 3,
    "Energy Boosters for Women 40+": 3,
    "Metabolism Boosting Drinks Women Over 40": 3,
}

PEXELS_VIDEO_QUERIES = [
    "green smoothie",
    "healthy lifestyle women",
    "weight loss healthy food",
    "woman drinking smoothie",
    "fresh fruits blending",
    "healthy breakfast women",
    "fitness women over 40",
    "salad preparation",
    "morning routine wellness",
    "detox juice",
]


def log(msg):
    print(msg, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC] {msg}\n")
    except Exception:
        pass


def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_board_id(board_name, headers, board_cache):
    if board_name in board_cache:
        return board_cache[board_name]
    import requests
    for attempt in range(3):
        try:
            r = requests.get(
                "https://api.pinterest.com/v5/boards",
                headers=headers, params={"page_size": 100}, timeout=30
            )
            if r.status_code == 200:
                for board in r.json().get("items", []):
                    board_cache[board["name"]] = board["id"]
                return board_cache.get(board_name)
        except Exception as e:
            log(f"  get_board_id error attempt {attempt+1}: {e}")
        time.sleep(5)
    return None


def get_image_url(state):
    local_pins = sorted(f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".png", ".jpg", ".jpeg"))) if os.path.isdir(IMAGES_DIR) else []
    if not local_pins:
        return None
    idx = state.get("img_idx", 0) % len(local_pins)
    state["img_idx"] = idx + 1
    return f"{REPO_RAW}/{local_pins[idx]}"


def publish_standard_pin(title, description, board_id, image_url, link, headers):
    import requests
    payload = {
        "title": title[:100],
        "description": description[:500],
        "board_id": board_id,
        "media_source": {"source_type": "image_url", "url": image_url},
        "link": link,
    }
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.pinterest.com/v5/pins",
                json=payload, headers=headers, timeout=30
            )
            return r.status_code, r.json()
        except Exception as e:
            log(f"  publish error attempt {attempt+1}: {e}")
            time.sleep(5)
    return 0, {"error": "failed after 3 attempts"}


def fetch_pexels_video_url(query):
    import requests
    if not PEXELS_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 10, "orientation": "portrait"},
            timeout=30
        )
        if r.status_code != 200:
            return None
        videos = r.json().get("videos", [])
        random.shuffle(videos)
        for v in videos:
            files = v.get("video_files", [])
            for f in sorted(files, key=lambda x: x.get("width", 0)):
                if f.get("quality") in ("sd", "hd") and f.get("link"):
                    return f["link"]
    except Exception as e:
        log(f"  pexels error: {e}")
    return None


def register_pinterest_video(headers):
    import requests
    try:
        r = requests.post(
            "https://api.pinterest.com/v5/media",
            json={"media_type": "video"},
            headers=headers,
            timeout=30
        )
        if r.status_code in (200, 201):
            data = r.json()
            log(f"    → media register response keys: {list(data.keys())}")
            media_id = data.get("media_id")
            # upload_url can be top-level OR inside upload_parameters
            upload_params = dict(data.get("upload_parameters", {}))
            upload_url = data.get("upload_url") or upload_params.pop("upload_url", None)
            return media_id, upload_url, upload_params
        log(f"  register_video error {r.status_code}: {r.text[:300]}")
    except Exception as e:
        log(f"  register_video exception: {e}")
    return None, None, {}


def upload_video_file(video_url, upload_url, upload_params):
    import requests
    if not upload_url:
        log(f"  upload_video_file: no upload_url")
        return False
    tmp_path = None
    try:
        r = requests.get(video_url, timeout=90, stream=True)
        if r.status_code != 200:
            return False
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            for chunk in r.iter_content(chunk_size=65536):
                tmp.write(chunk)
            tmp_path = tmp.name
        with open(tmp_path, "rb") as f:
            resp = requests.post(upload_url, data=upload_params, files={"file": ("video.mp4", f, "video/mp4")}, timeout=180)
        return resp.status_code in (200, 201, 204)
    except Exception as e:
        log(f"  upload_video_file error: {e}")
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def wait_for_video_ready(media_id, headers, max_wait=150):
    import requests
    for _ in range(max_wait // 10):
        try:
            r = requests.get(f"https://api.pinterest.com/v5/media/{media_id}", headers=headers, timeout=30)
            if r.status_code == 200:
                status = r.json().get("status", "")
                if status == "succeeded":
                    return True
                if status == "failed":
                    log(f"  video processing failed: {r.json()}")
                    return False
        except Exception:
            pass
        time.sleep(10)
    log(f"  video processing timed out after {max_wait}s")
    return False


def publish_video_pin(title, description, board_id, image_url, link, headers):
    import requests
    query = random.choice(PEXELS_VIDEO_QUERIES)
    log(f"    → searching Pexels video: '{query}'")
    video_url = fetch_pexels_video_url(query)

    if video_url:
        media_id, upload_url, upload_params = register_pinterest_video(headers)
        if media_id:
            log(f"    → uploading video (media_id={media_id}, url={'yes' if upload_url else 'MISSING'})…")
            ok = upload_video_file(video_url, upload_url, dict(upload_params))
            if ok:
                log(f"    → waiting for Pinterest to process video…")
                if wait_for_video_ready(media_id, headers):
                    payload = {
                        "title": title[:100],
                        "description": description[:500],
                        "board_id": board_id,
                        "media_source": {
                            "source_type": "video_id",
                            "cover_image_url": image_url,
                            "media_id": media_id,
                        },
                        "link": link,
                    }
                    try:
                        r = requests.post("https://api.pinterest.com/v5/pins", json=payload, headers=headers, timeout=30)
                        if r.status_code in (200, 201):
                            log(f"    → VIDEO PIN OK (media_id={media_id})")
                            return r.status_code, r.json()
                        log(f"    → video pin create error {r.status_code}: {r.text[:200]}")
                    except Exception as e:
                        log(f"    → video pin post exception: {e}")

    log(f"    → video fallback → standard pin")
    return publish_standard_pin(title, description, board_id, image_url, link, headers)


def publish_idea_pin(title, pages_text, board_id, image_urls, headers):
    import requests
    items = [{"url": u} for u in image_urls]
    payload = {
        "title": title[:100],
        "description": " | ".join(pages_text)[:500],
        "board_id": board_id,
        "media_source": {"source_type": "multiple_image_urls", "items": items},
    }
    for attempt in range(3):
        try:
            r = requests.post("https://api.pinterest.com/v5/pins", json=payload, headers=headers, timeout=30)
            return r.status_code, r.json()
        except Exception as e:
            log(f"  idea pin error attempt {attempt+1}: {e}")
            time.sleep(5)
    return 0, {"error": "failed after 3 attempts"}


def main():
    if not PINTEREST_TOKEN:
        log("ERROR: PINTEREST_ACCESS_TOKEN not set")
        sys.exit(1)

    tz_tunis = timezone(timedelta(hours=1))
    now_utc   = datetime.now(timezone.utc)
    now_tunis = now_utc.astimezone(tz_tunis)

    if len(sys.argv) >= 3:
        target_date = sys.argv[1]
        period      = sys.argv[2]
    else:
        target_date = now_tunis.strftime("%Y-%m-%d")
        done  = load_json(DONE_FILE)
        slots = ["08h", "17h"]
        period = None
        for s in slots:
            if not done.get(f"{target_date}_{s}"):
                period = s
                break
        if not period:
            log(f"Both slots for {target_date} already published — skip")
            sys.exit(0)
        log(f"UTC {now_utc.hour}h{now_utc.minute:02d} → next slot: {period}")

    period_key = f"{target_date}_{period}"
    log(f"=== Pinterest Publisher {target_date} {period} (6 pins/day mode) ===")

    done = load_json(DONE_FILE)
    if done.get(period_key, {}).get("published", 0) > 0:
        log(f"Already published: {period_key} — skip")
        sys.exit(0)

    content      = load_json(CONTENT_FILE)
    boards_data  = content.get("boards", {})
    idea_sets    = content.get("idea_pin_sets", [])
    state        = load_json(STATE_FILE, {"content_idx": 0, "img_idx": 0, "idea_idx": 0, "board_order_idx": 0})

    headers = {
        "Authorization": f"Bearer {PINTEREST_TOKEN}",
        "Content-Type": "application/json"
    }
    board_cache_file = os.path.join(BASE_DIR, "boards.json")
    board_cache      = load_json(board_cache_file)
    board_names      = list(boards_data.keys())

    if not board_names:
        log("ERROR: no board content in pin_content.json")
        sys.exit(1)

    published = 0
    errors    = 0

    # 2 standard pins from different boards
    for i in range(2):
        board_idx  = (state.get("board_order_idx", 0) + i) % len(board_names)
        board_name = board_names[board_idx]
        pins_pool  = boards_data[board_name]
        cidx       = state.get("content_idx", 0) % len(pins_pool)
        pin_data   = pins_pool[cidx]
        state["content_idx"] = cidx + 1

        image_url = get_image_url(state)
        if not image_url:
            log(f"  [{i+1}] ERROR: no images")
            errors += 1
            continue

        board_id = get_board_id(board_name, headers, board_cache)
        if not board_id:
            log(f"  [{i+1}] ERROR: board not found: {board_name}")
            errors += 1
            continue

        link_idx = BOARD_LINK_MAP.get(board_name, (i + state.get("board_order_idx", 0)) % len(LINK_POOL))
        pin_link = LINK_POOL[link_idx]

        status, resp = publish_standard_pin(pin_data["title"], pin_data["desc"], board_id, image_url, pin_link, headers)
        if status in (200, 201):
            log(f"  [{i+1}] OK [{board_name}]: {pin_data['title'][:50]}")
            published += 1
        else:
            log(f"  [{i+1}] ERROR {status}: {resp}")
            errors += 1
        time.sleep(3)

    # 3rd pin: video pin (08h) or idea pin (17h)
    board_idx3  = (state.get("board_order_idx", 0) + 2) % len(board_names)
    board_name3 = board_names[board_idx3]
    board_id3   = get_board_id(board_name3, headers, board_cache)
    image_url3  = get_image_url(state)
    link3_idx   = BOARD_LINK_MAP.get(board_name3, state.get("board_order_idx", 0) % len(LINK_POOL))
    link3       = LINK_POOL[link3_idx]

    if period == "08h":
        # Video pin in morning slot
        log(f"  [3] VIDEO PIN [{board_name3}]")
        cidx = state.get("content_idx", 0) % len(boards_data[board_name3])
        pin_data3 = boards_data[board_name3][cidx]
        state["content_idx"] = cidx + 1

        if board_id3 and image_url3:
            status, resp = publish_video_pin(pin_data3["title"], pin_data3["desc"], board_id3, image_url3, link3, headers)
            if status in (200, 201):
                log(f"  [3] OK VIDEO/STANDARD [{board_name3}]")
                published += 1
            else:
                log(f"  [3] ERROR {status}: {resp}")
                errors += 1
        else:
            log(f"  [3] SKIP: missing board_id or image")
            errors += 1

    else:
        # Idea pin in evening slot
        if idea_sets:
            idea_idx = state.get("idea_idx", 0) % len(idea_sets)
            idea     = idea_sets[idea_idx]
            state["idea_idx"] = idea_idx + 1

            idea_images = []
            for _ in range(min(len(idea["pages"]), 4)):
                img = get_image_url(state)
                if img:
                    idea_images.append(img)

            log(f"  [3] IDEA PIN [{board_name3}]: {idea['title'][:40]}")
            if board_id3 and len(idea_images) >= 2:
                status, resp = publish_idea_pin(idea["title"], idea["pages"], board_id3, idea_images, headers)
                if status in (200, 201):
                    log(f"  [3] OK IDEA PIN [{board_name3}]")
                    published += 1
                else:
                    log(f"  [3] IDEA PIN ERROR {status}: {resp}")
                    # Fallback to standard
                    if image_url3 and board_id3:
                        cidx = state.get("content_idx", 0) % len(boards_data[board_name3])
                        fb_pin = boards_data[board_name3][cidx]
                        state["content_idx"] = cidx + 1
                        st2, rp2 = publish_standard_pin(fb_pin["title"], fb_pin["desc"], board_id3, image_url3, link3, headers)
                        if st2 in (200, 201):
                            log(f"  [3] OK FALLBACK [{board_name3}]")
                            published += 1
                        else:
                            log(f"  [3] FALLBACK ERROR {st2}")
                            errors += 1
                    else:
                        errors += 1
            else:
                errors += 1
        else:
            errors += 1

    state["board_order_idx"] = (state.get("board_order_idx", 0) + 3) % len(board_names)

    save_json(board_cache_file, board_cache)
    save_json(STATE_FILE, state)

    if published > 0:
        done[period_key] = {
            "published": published,
            "errors": errors,
            "total": 3,
            "at": datetime.utcnow().isoformat()
        }
        save_json(DONE_FILE, done)
    else:
        log("WARNING: 0 pins published — slot NOT marked done (will retry)")

    log(f"=== Done: {published} published | {errors} errors ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(f"EXCEPTION:\n{traceback.format_exc()}")
        sys.exit(1)
