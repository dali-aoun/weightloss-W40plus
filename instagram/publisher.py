"""
publisher.py — Instagram auto-publisher (GitHub Actions)
3 images + 2 reels par jour, espaces 3h
Tunisia UTC+1 : 07h(img) 10h(reel) 13h(img) 16h(reel) 19h(img)
Reels: Pexels video + background music via ffmpeg -> catbox.moe
"""

import os, sys, json, time, random, requests, traceback, subprocess, tempfile
from datetime import datetime, timezone, timedelta

IG_USER_ID  = os.environ.get("INSTAGRAM_USER_ID", "27645316161821605")
IG_TOKEN    = os.environ.get("LONG_LIVED_TOKEN", "")
PEXELS_KEY  = os.environ.get("PEXELS_API_KEY", "")
BASE_URL    = "https://graph.instagram.com/v21.0"
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
STATE_FILE  = os.path.join(BASE_DIR, "published_state.json")
LOG_FILE    = os.path.join(BASE_DIR, "publish_log.txt")
CAPS_FILE   = os.path.join(BASE_DIR, "captions.json")

TZ_TUNIS = timezone(timedelta(hours=1))

# Slots du jour en ordre : (heure Tunisia, type)
SLOTS_ORDER = [
    ("07h",   "reel"), ("08h30", "reel"), ("10h",   "reel"),
    ("11h30", "reel"), ("13h",   "reel"), ("15h30", "reel"),
    ("17h",   "reel"), ("19h",   "reel"),
]

IMAGE_KEYWORDS = [
    "smoothie healthy woman portrait",
    "weight loss women fitness",
    "healthy green smoothie",
    "women wellness morning routine",
    "healthy food women over 40",
    "green smoothie fresh fruit",
    "women yoga wellness",
    "flat belly healthy lifestyle",
    "healthy morning breakfast",
    "women fitness over 40",
]

REEL_KEYWORDS = [
    "woman transformation happy healthy confident",
    "mature woman glowing skin healthy lifestyle",
    "woman drinking green smoothie morning light",
    "woman fitness over 40 strong confident",
    "woman blending fresh smoothie close up",
    "woman yoga morning routine peaceful",
    "woman laughing healthy vibrant energy",
    "woman flat belly fitness healthy",
    "woman preparing healthy food kitchen",
    "woman running outdoors happy morning",
    "mature woman healthy breakfast beautiful",
    "woman wellness spa healthy glow",
    "woman hiking nature active lifestyle",
    "woman dancing happy carefree wellness",
    "woman meditation morning routine calm",
]

# Local royalty-free background music (Pixabay License - free commercial use)
MUSIC_DIR = os.path.join(BASE_DIR, "music")
MUSIC_FILES = ["track_01.mp3", "track_02.mp3", "track_03.mp3"]

VOICEOVER_SCRIPTS = [
    "Stop. If you're over 40 and can't lose belly fat no matter what you try, watch this. Your cortisol is blocking everything. This 2-minute smoothie resets it. Free protocol in bio.",
    "I lost 17 pounds in 21 days without changing what I eat. Just added this one smoothie every morning. It targets the hormone that traps belly fat after 40. Link in bio.",
    "Doctors don't tell you this: dieting after 40 actually raises cortisol and stores MORE belly fat. Stop dieting. Start this smoothie protocol instead. It's free in the bio.",
    "Your belly fat isn't about food. It's about cortisol. High stress, poor sleep, hormone shifts — they all signal your body to store fat around your waist. This smoothie reverses that signal. Free guide in bio.",
    "If you've tried everything and nothing works, you haven't tried fixing the root cause. After 40, it's always hormonal. This 21-day smoothie protocol is designed for your exact metabolism. Get it free — link in bio.",
    "47,000 women over 40 used this smoothie to finally lose their belly fat. Not by starving. By working with their hormones, not against them. Your turn. Free plan in bio.",
    "The first morning I made this smoothie I thought — this is too easy. Three weeks later I was 11 pounds lighter. No gym. No diet. Just this. Free 21-day protocol in my bio.",
    "Here's what nobody tells you about weight loss after 40: less food equals more cortisol equals more belly fat. This smoothie breaks the cycle. Free guide is in my bio right now.",
    "Perimenopause, cortisol, insulin resistance — all three make belly fat almost impossible to lose. Unless you address all three at once. That's exactly what this smoothie does. Free protocol in bio.",
    "Wake up. Blend this smoothie. Drink it in under 2 minutes. That's the entire morning routine that helped thousands of women over 40 lose their stubborn belly fat. It's free. Bio link.",
    "One smoothie. 21 days. Women over 40 are losing 10 to 20 pounds without starving, without the gym, without giving up the foods they love. The secret is in the ingredients. Free guide in bio.",
    "You've been told your metabolism is slow. It's not. It shifted. And there's a specific nutritional approach that works with this shift instead of fighting it. This is it. Free in bio.",
    "Every morning at 7am I blend this smoothie. It takes 90 seconds. It has reversed my hormonal belly fat completely. I'm sharing the exact recipe free in my bio. Go get it.",
    "Stop blaming yourself for the belly fat. After 40 it's biological. Your estrogen dropped. Your cortisol rose. Your body is doing exactly what it's programmed to do. This smoothie reprograms it. Free link in bio.",
    "The smoothie that 47,000 women are using to lose hormonal belly fat after 40. No gym required. No starvation. Just 2 minutes every morning. Free 21-day protocol — tap the link in my bio.",
]

TEXT_OVERLAYS = [
    ("Lost 17 lbs in 21 days", "Free 21-day plan - link in bio"),
    ("47000 women transformed", "Join them free - link in bio"),
    ("Cortisol blocks fat after 40", "Fix it free - link in bio"),
    ("No gym. No diet. Just this.", "Free protocol - link in bio"),
    ("Your hormones blocked fat loss", "Reset them - link in bio"),
    ("Works when nothing else does", "Free guide - link in bio"),
    ("21 days to reset your body", "Start free - link in bio"),
    ("The smoothie that works after 40", "Get it free - link in bio"),
    ("Stop blaming yourself", "It is hormonal - fix it free"),
    ("Dieting raises cortisol after 40", "This smoothie lowers it free"),
    ("Lost 11 lbs without the gym", "Free 21-day plan - link in bio"),
    ("One smoothie every morning", "47000 women already did this"),
    ("Perimenopause belly fat fix", "Free protocol - link in bio"),
    ("Hormonal belly fat is different", "This targets it free - bio"),
    ("Your metabolism did not break", "It shifted - fix it free"),
]



def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_state():
    defaults = {"image_idx": 0, "reel_idx": 0, "img_kw": 0, "reel_kw": 0,
                "music_idx": 0, "vo_idx": 0, "published": []}
    if not os.path.exists(STATE_FILE):
        return defaults
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in defaults.items():
                data.setdefault(k, v)
            return data
    except Exception:
        return defaults


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_captions():
    with open(CAPS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def download_file(url, dest_path, label="file"):
    """Download any file with progress log."""
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, stream=True, timeout=120)
    if r.status_code != 200:
        log(f"  Download {label} HTTP {r.status_code}: {url[:70]}")
        return False
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
    size_kb = os.path.getsize(dest_path) // 1024
    log(f"  Downloaded {label}: {size_kb}KB")
    return True


def generate_voiceover(text, output_path, voice="en-US-JennyNeural"):
    """Microsoft Neural TTS via edge-tts — free, no API key needed."""
    try:
        result = subprocess.run(
            ["edge-tts", "--voice", voice, "--text", text, "--write-media", output_path],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            log(f"  Voiceover OK: {os.path.getsize(output_path) // 1024}KB")
            return True
        log(f"  edge-tts erreur: {result.stderr[-200:]}")
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        log(f"  generate_voiceover erreur: {e}")
    return False


def merge_video_audio(video_path, audio_path, output_path):
    """ffmpeg: loop audio to cover full video, volume at -18dB background level."""
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", audio_path,
        "-i", video_path,
        "-map", "1:v:0",
        "-map", "0:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-af", "volume=-18dB",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            log(f"  ffmpeg merge OK: {size_mb:.1f}MB")
            return True
        log(f"  ffmpeg erreur: {result.stderr[-300:]}")
        return False
    except subprocess.TimeoutExpired:
        log("  ffmpeg timeout")
        return False


def merge_video_voiceover_music(video_path, voiceover_path, music_path, output_path, max_sec=30, text_overlay=None):
    """Mix: video + voiceover (foreground) + background music (-20dB)."""
    # Build text overlay filter for drawtext
    def esc_text(t):
        return t.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")

    if text_overlay:
        headline, subline = text_overlay
        headline_safe = esc_text(headline)
        subline_safe  = esc_text(subline)
        vf_filter = (
            f"drawtext=text=\'{headline_safe}\':"
            f"fontcolor=white:fontsize=54:x=(w-text_w)/2:y=70:"
            f"box=1:boxcolor=black@0.55:boxborderw=14,"
            f"drawtext=text=\'{subline_safe}\':"
            f"fontcolor=yellow:fontsize=38:x=(w-text_w)/2:y=h-90:"
            f"box=1:boxcolor=black@0.55:boxborderw=10"
        )
        vf_args = ["-vf", vf_filter]
    else:
        vf_args = []

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", music_path,
        "-i", voiceover_path,
        "-map", "0:v:0",
        "-filter_complex",
        f"[1:a]atrim=end={max_sec},volume=-20dB[bg];[2:a]volume=1.2[vo];[bg][vo]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "[aout]",
        *vf_args,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-t", str(max_sec), "-shortest",
        "-movflags", "+faststart",
        output_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            log(f"  ffmpeg 3-track merge OK: {size_mb:.1f}MB")
            return True
        log(f"  ffmpeg erreur: {result.stderr[-300:]}")
        return False
    except subprocess.TimeoutExpired:
        log("  ffmpeg timeout")
        return False


def upload_to_host(file_path):
    """Upload video to a public host. Tries multiple services as fallback."""
    hosters = [
        ("uguu.se", _upload_uguu),
        ("0x0.st", _upload_0x0),
        ("oshi.at", _upload_oshi),
        ("litterbox.catbox.moe", _upload_litterbox),
        ("tmpfiles.org", _upload_tmpfiles),
    ]
    for name, fn in hosters:
        log(f"  Upload vers {name}...")
        url = fn(file_path)
        if url:
            log(f"  URL publique: {url}")
            return url
        log(f"  {name} echec, essai suivant...")
    return None


def _upload_0x0(file_path):
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                "https://0x0.st",
                files={"file": ("reel.mp4", f, "video/mp4")},
                timeout=120
            )
        if r.status_code == 200 and r.text.strip().startswith("https://"):
            return r.text.strip()
        log(f"  0x0.st: {r.status_code} {r.text[:100]}")
    except Exception as e:
        log(f"  0x0.st exception: {e}")
    return None


def _upload_litterbox(file_path):
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": "72h"},
                files={"fileToUpload": ("reel.mp4", f, "video/mp4")},
                timeout=300
            )
        if r.status_code == 200 and r.text.strip().startswith("https://"):
            return r.text.strip()
        log(f"  litterbox: {r.status_code} {r.text[:100]}")
    except Exception as e:
        log(f"  litterbox exception: {e}")
    return None


def _upload_uguu(file_path):
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                "https://uguu.se/upload",
                files={"files[]": ("reel.mp4", f, "video/mp4")},
                timeout=300
            )
        if r.status_code == 200:
            data = r.json()
            files = data.get("files", [])
            if files and files[0].get("url"):
                return files[0]["url"]
        log(f"  uguu.se: {r.status_code} {r.text[:100]}")
    except Exception as e:
        log(f"  uguu.se exception: {e}")
    return None


def _upload_oshi(file_path):
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                "https://oshi.at",
                files={"f": ("reel.mp4", f, "video/mp4")},
                data={"expire": "1440"},
                timeout=120,
                verify=False
            )
        if r.status_code == 200:
            for line in r.text.split("\n"):
                if line.startswith("DL:"):
                    url = line[3:].strip()
                    if url.startswith("http"):
                        return url
        log(f"  oshi.at: {r.status_code} {r.text[:100]}")
    except Exception as e:
        log(f"  oshi.at exception: {e}")
    return None




def _upload_tmpfiles(file_path):
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": ("reel.mp4", f, "video/mp4")},
                timeout=300
            )
        if r.status_code == 200:
            data = r.json()
            url = data.get("data", {}).get("url", "")
            if url:
                return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        log(f"  tmpfiles: {r.status_code} {r.text[:100]}")
    except Exception as e:
        log(f"  tmpfiles exception: {e}")
    return None


def pexels_image(keyword):
    headers = {"Authorization": PEXELS_KEY}
    params  = {"query": keyword, "per_page": 15, "orientation": "portrait"}
    try:
        r = requests.get("https://api.pexels.com/v1/search",
                         headers=headers, params=params, timeout=30)
        if r.status_code == 200:
            photos = r.json().get("photos", [])
            if photos:
                photo = random.choice(photos[:10])
                return photo["src"]["large2x"]
        log(f"  Pexels image HTTP {r.status_code}")
    except Exception as e:
        log(f"  pexels_image erreur: {e}")
    return None


def pexels_video_url(keyword):
    """Return direct CDN mp4 URL from Pexels (portrait preferred)."""
    headers = {"Authorization": PEXELS_KEY}
    params  = {"query": keyword, "per_page": 15, "orientation": "portrait", "size": "medium"}
    try:
        r = requests.get("https://api.pexels.com/videos/search",
                         headers=headers, params=params, timeout=30)
        if r.status_code != 200:
            log(f"  Pexels video HTTP {r.status_code}")
            return None
        videos = r.json().get("videos", [])
        random.shuffle(videos)
        for video in videos[:8]:
            dur = video.get("duration", 0)
            if not (3 <= dur <= 88):
                continue
            files = video.get("video_files", [])
            for quality in ("hd", "sd", ""):
                for vf in files:
                    link = vf.get("link", "")
                    h = vf.get("height", 0)
                    w = vf.get("width", 1)
                    if (vf.get("file_type") == "video/mp4"
                            and "videos.pexels.com" in link
                            and h >= w and h >= 1280 and w >= 720):
                        if not quality or vf.get("quality") == quality:
                            return link
            # fallback: any pexels CDN mp4 in duration range
            for vf in files:
                link = vf.get("link", "")
                if vf.get("file_type") == "video/mp4" and "videos.pexels.com" in link:
                    return link
    except Exception as e:
        log(f"  pexels_video erreur: {e}")
    return None


def get_with_fallback(keyword, all_keywords, fetch_fn):
    url = fetch_fn(keyword)
    if url:
        return url
    for kw in all_keywords:
        if kw == keyword:
            continue
        url = fetch_fn(kw)
        if url:
            return url
    return None


def build_reel_url(pexels_video_url_str, music_idx, vo_idx, text_overlay=None):
    """Download Pexels video + voiceover + music, merge 3 tracks, upload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path  = os.path.join(tmpdir, "video.mp4")
        vo_path     = os.path.join(tmpdir, "voiceover.mp3")
        output_path = os.path.join(tmpdir, "reel.mp4")

        log("  Download video Pexels...")
        if not download_file(pexels_video_url_str, video_path, "video"):
            return None

        audio_path = os.path.join(MUSIC_DIR, MUSIC_FILES[music_idx % len(MUSIC_FILES)])
        log(f"  Musique: {MUSIC_FILES[music_idx % len(MUSIC_FILES)]}")
        if not os.path.exists(audio_path):
            log(f"  ERREUR: musique introuvable: {audio_path}")
            return None

        vo_text = VOICEOVER_SCRIPTS[vo_idx % len(VOICEOVER_SCRIPTS)]
        log(f"  Voiceover: {vo_text[:60]}...")
        vo_ok = generate_voiceover(vo_text, vo_path)

        if vo_ok:
            if not merge_video_voiceover_music(video_path, vo_path, audio_path, output_path, text_overlay=text_overlay):
                return None
        else:
            log("  Voiceover indisponible — fallback musique seule")
            if not merge_video_audio(video_path, audio_path, output_path):
                return None

        return upload_to_host(output_path)


def ig_create_image(image_url, caption):
    data = {"image_url": image_url, "caption": caption, "access_token": IG_TOKEN}
    r = requests.post(f"{BASE_URL}/{IG_USER_ID}/media", data=data, timeout=60)
    return r.status_code, r.json()


def ig_create_reel(video_url, caption):
    data = {
        "media_type":    "REELS",
        "video_url":     video_url,
        "caption":       caption,
        "share_to_feed": "true",
        "access_token":  IG_TOKEN,
    }
    r = requests.post(f"{BASE_URL}/{IG_USER_ID}/media", data=data, timeout=60)
    return r.status_code, r.json()


def ig_wait_ready(container_id, max_sec=360):
    params = {"fields": "status_code,status", "access_token": IG_TOKEN}
    for i in range(max_sec // 10):
        time.sleep(10)
        try:
            r = requests.get(f"{BASE_URL}/{container_id}", params=params, timeout=30)
            if r.status_code == 200:
                d = r.json()
                sc = d.get("status_code", "")
                if sc == "FINISHED":
                    log(f"  Container pret ({(i+1)*10}s)")
                    return True
                if sc == "ERROR":
                    log(f"  Container ERROR: {d.get('status')}")
                    return False
                log(f"  status={sc} ({(i+1)*10}s)...")
        except Exception as e:
            log(f"  wait erreur: {e}")
    log(f"  Timeout {max_sec}s")
    return False


def ig_publish(container_id):
    data = {"creation_id": container_id, "access_token": IG_TOKEN}
    r = requests.post(f"{BASE_URL}/{IG_USER_ID}/media_publish", data=data, timeout=60)
    return r.status_code, r.json()


def main():
    if not IG_TOKEN:
        log("ERREUR: LONG_LIVED_TOKEN manquant")
        sys.exit(1)
    if not PEXELS_KEY:
        log("ERREUR: PEXELS_API_KEY manquant")
        sys.exit(1)

    now_utc   = datetime.now(timezone.utc)
    now_tunis = now_utc.astimezone(TZ_TUNIS)

    # FORCE_SLOT permet de relancer un slot manqué : "2026-06-20_07h:image"
    force = os.environ.get("FORCE_SLOT", "").strip()
    if force:
        parts     = force.split(":")
        slot_key  = parts[0]   # ex: 2026-06-20_07h
        slot_type = parts[1]   # ex: image ou reel
        log(f"=== FORCE_SLOT {slot_key} type={slot_type} ===")
    else:
        state_tmp = load_state()
        slot_date = now_tunis.strftime("%Y-%m-%d")
        published_today = {p["slot"] for p in state_tmp["published"] if p["slot"].startswith(slot_date)}
        slot_key, slot_type = None, None
        for hour_label, stype in SLOTS_ORDER:
            key = f"{slot_date}_{hour_label}"
            if key not in published_today:
                slot_key, slot_type = key, stype
                break
        if not slot_key:
            log(f"Les 5 slots de {slot_date} sont deja publies - skip")
            sys.exit(0)
        log(f"UTC {now_utc.hour}h{now_utc.minute:02d} -> prochain slot: {slot_key} type={slot_type}")
        log(f"=== Instagram Publisher {slot_key} type={slot_type} ===")

    state    = load_state()
    captions = load_captions()

    if any(p["slot"] == slot_key for p in state["published"]):
        log(f"Deja publie: {slot_key} - skip")
        sys.exit(0)

    media_id = None

    if slot_type == "image":
        imgs    = captions["image_captions"]
        idx     = state["image_idx"] % len(imgs)
        caption = imgs[idx]
        kw_idx  = state["img_kw"] % len(IMAGE_KEYWORDS)
        keyword = IMAGE_KEYWORDS[kw_idx]

        log(f"Recherche image Pexels: {keyword}")
        image_url = get_with_fallback(keyword, IMAGE_KEYWORDS, pexels_image)
        if not image_url:
            log("ERREUR: aucune image Pexels disponible")
            sys.exit(1)
        log(f"Image: {image_url[:80]}...")

        sc, resp = ig_create_image(image_url, caption)
        if sc not in (200, 201) or "id" not in resp:
            log(f"ERREUR container image: {sc} {resp}")
            sys.exit(1)
        container_id = resp["id"]
        log(f"Container: {container_id} - attente 20s...")
        time.sleep(20)

        sc2, resp2 = ig_publish(container_id)
        if sc2 not in (200, 201) or "id" not in resp2:
            log(f"ERREUR publication image: {sc2} {resp2}")
            sys.exit(1)
        media_id = resp2["id"]
        log(f"OK image publiee: {media_id}")

        state["image_idx"] = (idx + 1) % len(imgs)
        state["img_kw"]    = (kw_idx + 1) % len(IMAGE_KEYWORDS)

    elif slot_type == "reel":
        reels      = captions["reel_captions"]
        idx        = state["reel_idx"] % len(reels)
        caption    = reels[idx]
        kw_idx     = state["reel_kw"] % len(REEL_KEYWORDS)
        keyword    = REEL_KEYWORDS[kw_idx]
        music_idx  = state.get("music_idx", 0)
        vo_idx     = state.get("vo_idx", 0)

        log(f"Recherche video Pexels (personne reelle): {keyword}")
        raw_video_url = get_with_fallback(keyword, REEL_KEYWORDS, pexels_video_url)
        if not raw_video_url:
            log("ERREUR: aucune video Pexels disponible")
            sys.exit(1)
        log(f"Video Pexels: {raw_video_url[:80]}...")

        # Build reel: video + voiceover + background music
        txt_idx = state.get("txt_idx", 0)
        text_overlay = TEXT_OVERLAYS[txt_idx % len(TEXT_OVERLAYS)]
        log(f"Text overlay: {text_overlay[0]}")
        log("Preparation reel (video + voiceover + musique)...")
        hosted_url = build_reel_url(raw_video_url, music_idx, vo_idx, text_overlay=text_overlay)
        if not hosted_url:
            log("ERREUR: echec preparation reel")
            sys.exit(1)

        sc, resp = ig_create_reel(hosted_url, caption)
        if sc not in (200, 201) or "id" not in resp:
            log(f"ERREUR container reel: {sc} {resp}")
            sys.exit(1)
        container_id = resp["id"]
        log(f"Reel container: {container_id} - processing...")

        if not ig_wait_ready(container_id, max_sec=360):
            log("ERREUR: container reel non pret")
            sys.exit(1)

        sc2, resp2 = ig_publish(container_id)
        if sc2 not in (200, 201) or "id" not in resp2:
            log(f"ERREUR publication reel: {sc2} {resp2}")
            sys.exit(1)
        media_id = resp2["id"]
        log(f"OK reel publie: {media_id}")

        state["reel_idx"]  = (idx + 1) % len(reels)
        state["reel_kw"]   = (kw_idx + 1) % len(REEL_KEYWORDS)
        state["music_idx"] = (music_idx + 1) % len(MUSIC_FILES)
        state["vo_idx"]    = (vo_idx + 1) % len(VOICEOVER_SCRIPTS)
        state["txt_idx"]   = (txt_idx + 1) % len(TEXT_OVERLAYS)

    state["published"].append({
        "slot":     slot_key,
        "type":     slot_type,
        "media_id": media_id,
        "at":       now_utc.isoformat(),
    })
    save_state(state)
    log(f"=== Termine {slot_key} -> {media_id} ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(f"EXCEPTION:\n{traceback.format_exc()}")
        sys.exit(1)
