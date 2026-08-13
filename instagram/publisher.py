"""
publisher.py — Instagram auto-publisher (GitHub Actions)
8 reels/jour, espaces reguliers
Tunisia UTC+1 : 07h 08h30 10h 11h30 13h 15h30 17h 19h
Reels: Pexels video (blurred bg) + recipe card overlay (Pillow) + voiceover + music
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
FONT_CACHE  = "/tmp/recipe_font.ttf"

TZ_TUNIS = timezone(timedelta(hours=1))

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

MUSIC_DIR   = os.path.join(BASE_DIR, "music")
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

# ── Recipe cards — the core save-worthy content ──────────────────────────────
RECIPE_CARDS = [
    {
        "title": "THE CORTISOL SMOOTHIE",
        "ingredients": [
            "* 1 cup baby spinach",
            "* 1/2 cup frozen blueberries",
            "* 1 tsp ground flaxseed",
            "* 1 tsp cinnamon",
            "* 1 scoop collagen peptides",
            "* 1 cup unsweetened almond milk",
        ],
        "instruction": "Blend 30 sec. Drink before 9am.",
        "benefit": "Lowers cortisol + melts belly fat",
    },
    {
        "title": "HORMONE RESET SMOOTHIE",
        "ingredients": [
            "* 1 cup kale (or spinach)",
            "* 1/2 frozen banana",
            "* 1 tbsp almond butter",
            "* 1 tsp maca powder",
            "* 1/2 tsp turmeric",
            "* 1 cup oat milk",
        ],
        "instruction": "Blend until smooth. Best on empty stomach.",
        "benefit": "Balances estrogen + boosts energy",
    },
    {
        "title": "BELLY FAT BURNER",
        "ingredients": [
            "* 1 cup frozen mango",
            "* 1/2 cup pineapple",
            "* 1 tsp ginger (fresh or powder)",
            "* 1 tsp apple cider vinegar",
            "* 1 tbsp chia seeds",
            "* 1 cup coconut water",
        ],
        "instruction": "Blend 45 sec. Drink within 10 min.",
        "benefit": "Reduces bloat + ignites metabolism",
    },
    {
        "title": "ANTI-INFLAMMATORY BLEND",
        "ingredients": [
            "* 1 cup frozen cherries",
            "* 1/2 cup spinach",
            "* 1 tsp turmeric",
            "* 1/2 tsp black pepper",
            "* 1 tbsp ground flaxseed",
            "* 1 cup almond milk",
        ],
        "instruction": "Blend 30 sec. Add ice if desired.",
        "benefit": "Fights inflammation + reduces fat",
    },
    {
        "title": "MORNING METABOLISM BOOST",
        "ingredients": [
            "* 1 cup cold green tea",
            "* 1/2 cup frozen strawberries",
            "* 1 scoop vanilla protein powder",
            "* 1 tsp cinnamon",
            "* 1 tbsp hemp seeds",
            "* Handful of spinach",
        ],
        "instruction": "Blend smooth. Drink before breakfast.",
        "benefit": "Jumpstarts metabolism + kills cravings",
    },
    {
        "title": "PERIMENOPAUSE SMOOTHIE",
        "ingredients": [
            "* 1/2 cup frozen raspberries",
            "* 1/2 cup blueberries",
            "* 1 tbsp ground flaxseed",
            "* 1 tsp maca powder",
            "* 1 scoop collagen",
            "* 1 cup coconut milk",
        ],
        "instruction": "Blend until creamy. Drink daily.",
        "benefit": "Relieves symptoms + melts belly fat",
    },
    {
        "title": "DETOX GREEN SMOOTHIE",
        "ingredients": [
            "* 2 cups spinach",
            "* 1 green apple (cored)",
            "* 1/2 lemon (juiced)",
            "* 1 tsp grated ginger",
            "* 1/2 cucumber (sliced)",
            "* 1 cup water + ice",
        ],
        "instruction": "Blend 60 sec. Drink on empty stomach.",
        "benefit": "Flushes toxins + reduces water weight",
    },
    {
        "title": "SLEEP + SLIM SMOOTHIE",
        "ingredients": [
            "* 1 cup tart cherry juice",
            "* 1/2 frozen banana",
            "* 1 tsp honey",
            "* 1/4 tsp nutmeg",
            "* 1 scoop magnesium powder",
            "* 1/2 cup almond milk",
        ],
        "instruction": "Drink 1 hour before bed.",
        "benefit": "Improves sleep + activates fat burning",
    },
    {
        "title": "HIGH PROTEIN FAT BURNER",
        "ingredients": [
            "* 1 scoop vanilla whey protein",
            "* 1 cup frozen mixed berries",
            "* 1 tbsp almond butter",
            "* 1 tbsp chia seeds",
            "* 1 cup unsweetened almond milk",
            "* 5 ice cubes",
        ],
        "instruction": "Blend thick. Can replace breakfast.",
        "benefit": "Builds lean muscle + melts fat",
    },
    {
        "title": "ESTROGEN BALANCE SMOOTHIE",
        "ingredients": [
            "* 1 cup frozen peaches",
            "* 1 tbsp ground flaxseed",
            "* 1 tbsp pumpkin seeds",
            "* 1 tsp vanilla extract",
            "* 1 cup plain kefir",
            "* Pinch of cinnamon",
        ],
        "instruction": "Blend smooth. Best in the morning.",
        "benefit": "Balances estrogen + reduces cravings",
    },
    {
        "title": "BLOAT BUSTER SMOOTHIE",
        "ingredients": [
            "* 1 cup frozen pineapple",
            "* 1/2 cup cucumber",
            "* 1 tsp fresh ginger",
            "* 1 tbsp lemon juice",
            "* 1 tsp apple cider vinegar",
            "* 1 cup coconut water",
        ],
        "instruction": "Blend 30 sec. Drink immediately.",
        "benefit": "Eliminates bloat in 24 hours",
    },
    {
        "title": "CHOCOLATE FAT BURNER",
        "ingredients": [
            "* 1 tbsp raw cacao powder",
            "* 1/2 frozen banana",
            "* 1 scoop chocolate protein",
            "* 1 tbsp almond butter",
            "* 1 tsp cinnamon",
            "* 1.5 cups almond milk",
        ],
        "instruction": "Blend creamy. Kills chocolate cravings.",
        "benefit": "Stops cravings + melts belly fat",
    },
    {
        "title": "THYROID SUPPORT SMOOTHIE",
        "ingredients": [
            "* 1 cup frozen blueberries",
            "* 2-3 Brazil nuts",
            "* 1 tsp kelp powder",
            "* 1 tbsp ground flaxseed",
            "* 1 tsp virgin coconut oil",
            "* 1 cup almond milk",
        ],
        "instruction": "Blend smooth. Take with breakfast.",
        "benefit": "Supports thyroid + boosts metabolism",
    },
    {
        "title": "STRESS BELLY FAT FIX",
        "ingredients": [
            "* 1 cup frozen mango",
            "* 1 tbsp ashwagandha powder",
            "* 1 tsp cacao powder",
            "* 1 tbsp hemp seeds",
            "* 1 tsp honey",
            "* 1 cup oat milk",
        ],
        "instruction": "Blend thick. Drink mid-morning.",
        "benefit": "Lowers stress hormones + melts fat",
    },
    {
        "title": "COLLAGEN GLOW SMOOTHIE",
        "ingredients": [
            "* 1 cup frozen strawberries",
            "* 1 scoop collagen peptides",
            "* 1 tbsp coconut cream",
            "* 1/2 cup Greek yogurt",
            "* 1 tsp vanilla extract",
            "* 1/2 cup almond milk",
        ],
        "instruction": "Blend until creamy. Drink daily.",
        "benefit": "Tightens skin + reduces fat",
    },
    {
        "title": "INSULIN RESET SMOOTHIE",
        "ingredients": [
            "* 1 cup frozen blackberries",
            "* 1/2 cup spinach",
            "* 1 tbsp apple cider vinegar",
            "* 1 tsp cinnamon",
            "* 1 tbsp chia seeds",
            "* 1 cup unsweetened almond milk",
        ],
        "instruction": "Blend smooth. Drink before meals.",
        "benefit": "Stabilizes blood sugar + stops fat storage",
    },
    {
        "title": "ENERGY WITHOUT CAFFEINE",
        "ingredients": [
            "* 1 cup frozen mixed berries",
            "* 1 tbsp maca powder",
            "* 1 scoop vanilla protein",
            "* 1 tsp cinnamon",
            "* 1 tbsp almond butter",
            "* 1 cup coconut water",
        ],
        "instruction": "Blend thick. Replace your coffee.",
        "benefit": "Sustained energy + no belly fat spike",
    },
    {
        "title": "LEAN BODY SMOOTHIE",
        "ingredients": [
            "* 1 cup frozen watermelon",
            "* 1/2 cup cucumber",
            "* 1 tbsp lemon juice",
            "* 1 tsp ginger powder",
            "* 1 tbsp chia seeds",
            "* 1 cup coconut water",
        ],
        "instruction": "Blend 30 sec. Best pre-workout.",
        "benefit": "Reduces water retention + tones body",
    },
    {
        "title": "IMMUNITY + SLIM SMOOTHIE",
        "ingredients": [
            "* 1 orange (peeled)",
            "* 1 carrot (chopped)",
            "* 1 tsp turmeric",
            "* 1 tsp ginger",
            "* 1 tbsp honey",
            "* 1 cup water + ice",
        ],
        "instruction": "Blend until smooth. Drink daily.",
        "benefit": "Strengthens immunity + reduces fat",
    },
    {
        "title": "21-DAY KICKSTART SMOOTHIE",
        "ingredients": [
            "* 1 cup spinach",
            "* 1/2 cup frozen blueberries",
            "* 1 frozen banana",
            "* 1 scoop collagen",
            "* 1 tsp flaxseed",
            "* 1 cup almond milk",
        ],
        "instruction": "Blend every morning for 21 days.",
        "benefit": "The original Smoothie Diet formula",
    },
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
                "music_idx": 0, "vo_idx": 0, "recipe_idx": 0, "published": []}
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


def _ensure_font():
    """Download Roboto Bold font if not cached."""
    if os.path.exists(FONT_CACHE) and os.path.getsize(FONT_CACHE) > 10000:
        return FONT_CACHE
    import urllib.request
    try:
        urllib.request.urlretrieve(
            "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf",
            FONT_CACHE
        )
        log(f"  Font downloaded: {os.path.getsize(FONT_CACHE)//1024}KB")
        return FONT_CACHE
    except Exception as e:
        log(f"  Font download erreur: {e}")
        return None


def generate_recipe_overlay(recipe, output_path):
    """Generate a 1080x1920 recipe card PNG overlay using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log("  Pillow non disponible - fallback text overlay")
        return False

    try:
        font_path = _ensure_font()

        W, H = 1080, 1920
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Dark semi-transparent panel
        pad = 45
        draw.rounded_rectangle(
            [pad, 100, W - pad, H - 100],
            radius=32,
            fill=(0, 0, 0, 205)
        )

        # Load fonts with fallbacks
        def fnt(size):
            if font_path:
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception:
                    pass
            try:
                return ImageFont.load_default(size=size)
            except Exception:
                return ImageFont.load_default()

        def cx(text, y, font, color):
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, y), text, font=font, fill=color)

        def lx(text, x, y, font, color):
            draw.text((x, y), text, font=font, fill=color)

        YELLOW  = (255, 215, 0, 255)
        WHITE   = (255, 255, 255, 255)
        GREEN   = (160, 255, 160, 255)
        ORANGE  = (255, 185, 60, 255)
        BLACK   = (0, 0, 0, 255)
        DIVIDER = (255, 255, 255, 70)

        y = 145

        # Header: SAVE THIS RECIPE
        cx("SAVE THIS RECIPE", y, fnt(76), YELLOW)
        y += 92

        draw.line([(pad + 50, y), (W - pad - 50, y)], fill=YELLOW, width=3)
        y += 22

        # Recipe title
        cx(recipe.get("title", ""), y, fnt(56), WHITE)
        y += 76

        draw.line([(pad + 80, y), (W - pad - 80, y)], fill=DIVIDER, width=2)
        y += 24

        # Ingredients
        for ing in recipe.get("ingredients", [])[:6]:
            lx(ing, pad + 70, y, fnt(46), GREEN)
            y += 66

        y += 10
        draw.line([(pad + 80, y), (W - pad - 80, y)], fill=DIVIDER, width=2)
        y += 26

        # Instruction
        cx(recipe.get("instruction", ""), y, fnt(44), ORANGE)
        y += 62

        # Benefit
        cx(recipe.get("benefit", ""), y, fnt(44), GREEN)
        y += 70

        # CTA button
        btn_y = H - 200
        draw.rounded_rectangle(
            [pad + 50, btn_y, W - pad - 50, btn_y + 80],
            radius=18,
            fill=(255, 195, 0, 230)
        )
        cx("FREE 21-DAY PLAN  ->  LINK IN BIO", btn_y + 16, fnt(44), BLACK)

        img.save(output_path, "PNG")
        log(f"  Recipe overlay OK ({recipe.get('title','?')}): {os.path.getsize(output_path)//1024}KB")
        return True

    except Exception as e:
        log(f"  generate_recipe_overlay erreur: {e}")
        return False


def merge_recipe_card_video(video_path, overlay_path, voiceover_path, music_path, output_path, max_sec=30):
    """Blur Pexels video as background, composite recipe card overlay, mix audio."""
    has_vo = voiceover_path and os.path.exists(voiceover_path) and os.path.getsize(voiceover_path) > 1000

    inputs = ["-i", video_path, "-i", overlay_path, "-stream_loop", "-1", "-i", music_path]

    if has_vo:
        inputs += ["-i", voiceover_path]
        audio_f = (
            f"[2:a]atrim=end={max_sec},volume=-20dB[bgm];"
            f"[3:a]volume=1.2[vo];"
            f"[bgm][vo]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
        audio_f = f"[2:a]atrim=end={max_sec},volume=-15dB[aout]"

    filter_complex = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,boxblur=10:3[bg];"
        f"[bg][1:v]overlay=0:0[vout];"
        f"{audio_f}"
    )

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-t", str(max_sec), "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            log(f"  Recipe card video OK: {os.path.getsize(output_path)/1024/1024:.1f}MB")
            return True
        log(f"  ffmpeg recipe erreur: {result.stderr[-300:]}")
        return False
    except subprocess.TimeoutExpired:
        log("  ffmpeg timeout")
        return False


def merge_video_audio(video_path, audio_path, output_path):
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", audio_path,
        "-i", video_path,
        "-map", "1:v:0", "-map", "0:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-af", "volume=-18dB",
        "-shortest", "-movflags", "+faststart",
        output_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            log(f"  ffmpeg merge OK: {os.path.getsize(output_path)/1024/1024:.1f}MB")
            return True
        log(f"  ffmpeg erreur: {result.stderr[-300:]}")
        return False
    except subprocess.TimeoutExpired:
        log("  ffmpeg timeout")
        return False


def merge_video_voiceover_music(video_path, voiceover_path, music_path, output_path, max_sec=30, text_overlay=None):
    def esc_text(t):
        return t.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")

    if text_overlay:
        headline, subline = text_overlay
        vf_filter = (
            f"drawtext=text=\'{esc_text(headline)}\':"
            f"fontcolor=white:fontsize=54:x=(w-text_w)/2:y=70:"
            f"box=1:boxcolor=black@0.55:boxborderw=14,"
            f"drawtext=text=\'{esc_text(subline)}\':"
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
            log(f"  ffmpeg 3-track OK: {os.path.getsize(output_path)/1024/1024:.1f}MB")
            return True
        log(f"  ffmpeg erreur: {result.stderr[-300:]}")
        return False
    except subprocess.TimeoutExpired:
        log("  ffmpeg timeout")
        return False


def upload_to_host(file_path):
    hosters = [
        ("uguu.se",            _upload_uguu),
        ("0x0.st",             _upload_0x0),
        ("oshi.at",            _upload_oshi),
        ("litterbox.catbox.moe", _upload_litterbox),
        ("tmpfiles.org",       _upload_tmpfiles),
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
            r = requests.post("https://0x0.st", files={"file": ("reel.mp4", f, "video/mp4")}, timeout=120)
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
                files={"fileToUpload": ("reel.mp4", f, "video/mp4")}, timeout=300
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
            r = requests.post("https://uguu.se/upload", files={"files[]": ("reel.mp4", f, "video/mp4")}, timeout=300)
        if r.status_code == 200:
            files = r.json().get("files", [])
            if files and files[0].get("url"):
                return files[0]["url"]
        log(f"  uguu.se: {r.status_code} {r.text[:100]}")
    except Exception as e:
        log(f"  uguu.se exception: {e}")
    return None


def _upload_oshi(file_path):
    try:
        with open(file_path, "rb") as f:
            r = requests.post("https://oshi.at",
                files={"f": ("reel.mp4", f, "video/mp4")},
                data={"expire": "1440"}, timeout=120, verify=False)
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
            r = requests.post("https://tmpfiles.org/api/v1/upload",
                files={"file": ("reel.mp4", f, "video/mp4")}, timeout=300)
        if r.status_code == 200:
            url = r.json().get("data", {}).get("url", "")
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
        r = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=30)
        if r.status_code == 200:
            photos = r.json().get("photos", [])
            if photos:
                return random.choice(photos[:10])["src"]["large2x"]
        log(f"  Pexels image HTTP {r.status_code}")
    except Exception as e:
        log(f"  pexels_image erreur: {e}")
    return None


def pexels_video_url(keyword):
    headers = {"Authorization": PEXELS_KEY}
    params  = {"query": keyword, "per_page": 15, "orientation": "portrait", "size": "medium"}
    try:
        r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=30)
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
            for vf in files:
                link = vf.get("link", "")
                h = vf.get("height", 0)
                w = vf.get("width", 1)
                if (vf.get("file_type") == "video/mp4"
                        and "videos.pexels.com" in link
                        and h >= w and h >= 1280 and w >= 720):
                    return link
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


def build_reel_url(pexels_video_url_str, music_idx, vo_idx, recipe=None, text_overlay=None):
    """Download Pexels video, generate recipe card overlay, merge, upload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path   = os.path.join(tmpdir, "video.mp4")
        vo_path      = os.path.join(tmpdir, "voiceover.mp3")
        overlay_path = os.path.join(tmpdir, "overlay.png")
        output_path  = os.path.join(tmpdir, "reel.mp4")

        log("  Download video Pexels...")
        if not download_file(pexels_video_url_str, video_path, "video"):
            return None

        audio_path = os.path.join(MUSIC_DIR, MUSIC_FILES[music_idx % len(MUSIC_FILES)])
        if not os.path.exists(audio_path):
            log(f"  ERREUR: musique introuvable: {audio_path}")
            return None

        vo_text = VOICEOVER_SCRIPTS[vo_idx % len(VOICEOVER_SCRIPTS)]
        log(f"  Voiceover: {vo_text[:60]}...")
        vo_ok = generate_voiceover(vo_text, vo_path)

        # Recipe card overlay (primary path)
        if recipe:
            overlay_ok = generate_recipe_overlay(recipe, overlay_path)
            if overlay_ok:
                if merge_recipe_card_video(
                    video_path, overlay_path,
                    vo_path if vo_ok else None,
                    audio_path, output_path
                ):
                    return upload_to_host(output_path)
                log("  Recipe card merge echec — fallback standard")

        # Fallback: standard text overlay
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
        "media_type": "REELS", "video_url": video_url,
        "caption": caption, "share_to_feed": "true", "access_token": IG_TOKEN,
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

    force = os.environ.get("FORCE_SLOT", "").strip()
    if force:
        parts     = force.split(":")
        slot_key  = parts[0]
        slot_type = parts[1]
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
            log(f"Les 8 slots de {slot_date} sont deja publies - skip")
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
        recipe_idx = state.get("recipe_idx", 0)
        recipe     = RECIPE_CARDS[recipe_idx % len(RECIPE_CARDS)]

        log(f"Recipe card: {recipe['title']}")
        log(f"Recherche video Pexels: {keyword}")
        raw_video_url = get_with_fallback(keyword, REEL_KEYWORDS, pexels_video_url)
        if not raw_video_url:
            log("ERREUR: aucune video Pexels disponible")
            sys.exit(1)

        txt_idx      = state.get("txt_idx", 0)
        text_overlay = TEXT_OVERLAYS[txt_idx % len(TEXT_OVERLAYS)]
        log(f"Preparation reel (recipe card + voiceover + musique)...")
        hosted_url = build_reel_url(raw_video_url, music_idx, vo_idx, recipe=recipe, text_overlay=text_overlay)
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

        state["reel_idx"]    = (idx + 1) % len(reels)
        state["reel_kw"]     = (kw_idx + 1) % len(REEL_KEYWORDS)
        state["music_idx"]   = (music_idx + 1) % len(MUSIC_FILES)
        state["vo_idx"]      = (vo_idx + 1) % len(VOICEOVER_SCRIPTS)
        state["txt_idx"]     = (txt_idx + 1) % len(TEXT_OVERLAYS)
        state["recipe_idx"]  = (recipe_idx + 1) % len(RECIPE_CARDS)

    state["published"].append({
        "slot": slot_key, "type": slot_type,
        "media_id": media_id, "at": now_utc.isoformat(),
    })
    save_state(state)
    log(f"=== Termine {slot_key} -> {media_id} ===")


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

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(f"EXCEPTION:\n{traceback.format_exc()}")
        sys.exit(1)
