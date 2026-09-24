"""
publisher.py — Instagram auto-publisher (GitHub Actions)
3 reels/jour, ciblage audience US PST
PST: 8h matin / 12h midi / 18h soir  (UTC: 16h / 20h / 02h)
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
    ("08h_pst", "reel"),   # 8 AM PST  = 16:00 UTC
    ("12h_pst", "reel"),   # 12 PM PST = 20:00 UTC
    ("18h_pst", "reel"),   # 6 PM PST  = 02:00 UTC
]

IMAGE_KEYWORDS = [
    "woman drinking coffee morning light",
    "mature woman coffee cup smiling",
    "women wellness morning coffee routine",
    "woman holding coffee mug cozy",
    "healthy woman morning coffee kitchen",
    "women over 40 coffee lifestyle",
    "woman flat belly fitness confident",
    "morning coffee ritual woman happy",
    "mature woman glowing energy healthy",
    "women fitness over 40 strong",
]

REEL_KEYWORDS = [
    "woman drinking coffee morning light happy",
    "mature woman coffee cup smiling confident",
    "woman morning routine coffee kitchen calm",
    "woman transformation happy healthy confident",
    "mature woman glowing skin healthy lifestyle",
    "woman fitness over 40 strong confident",
    "woman laughing healthy vibrant energy",
    "woman flat belly fitness healthy",
    "woman running outdoors happy morning",
    "mature woman healthy breakfast beautiful",
    "woman wellness spa healthy glow",
    "woman hiking nature active lifestyle",
    "woman dancing happy carefree wellness",
    "woman meditation morning routine calm",
    "woman coffee shop relaxed beautiful morning",
]

MUSIC_DIR   = os.path.join(BASE_DIR, "music")
MUSIC_FILES = ["track_01.mp3", "track_02.mp3", "track_03.mp3"]

VOICEOVER_SCRIPTS = [
    "She cried when her jeans fit again at 54. Three weeks of this coffee ritual. No smoothies. No gym. Just her morning cup done right. Your turn. Free guide in bio.",
    "My sister turned 49 last month. She texted me a photo in her old jeans. She hadn't worn them in six years. This coffee ritual. Three weeks. That's it. Free plan in bio.",
    "Her husband came home from a business trip and didn't recognize her from behind. She was 52. She had added this to her morning coffee for 28 days. Free ritual in bio.",
    "She almost didn't go to her daughter's graduation. She didn't fit in anything. Then she tried this for 21 days. She wore a dress she bought twelve years ago. Free guide in bio.",
    "I'm 51. I stopped weighing myself in April. Then I added this to my coffee every morning. By June my doctor asked what I had changed. Free ritual in bio.",
    "She gave away her scale at 53 because it only made her cry. Then she found this coffee ritual. She bought a new scale four weeks later. Free plan in bio.",
    "My mom called me crying at 58. Not because she was sad. Because she had just put on a pair of jeans she bought before I was born. Three weeks of this morning coffee ritual. Free in bio.",
    "What if I told you the coffee you drink every morning is keeping you stuck. One tasteless addition changes everything in 21 days. Free plan in bio.",
    "Close this video if you already have a flat stomach after 40. Still here? Good. Your morning coffee is the problem and the solution. Free ritual in bio.",
    "Don't skip the next 30 seconds if you've tried everything for belly fat and nothing has worked. This is the thing you missed. Free guide in bio.",
    "Not a diet. Not a gym plan. One thing added to your morning coffee. Women over 40 are calling it the only thing that finally worked. Free ritual in bio.",
    "The thing you are drinking every single morning is either storing your belly fat or burning it. Most women over 40 have no idea which. Free plan in bio.",
    "There is a reason some women lose belly fat after 40 without trying and others don't. It is their morning coffee ritual. This is the difference. Free in bio.",
    "Warning. Once you fix your morning coffee ritual you will not be able to stop losing weight. 47,000 women warned you. Free 21-day plan in bio.",
    "Your morning coffee is spiking cortisol at the worst possible time. Here is what to add to it instead. 10 seconds. Free ritual in bio.",
    "Stop. Your morning coffee is storing belly fat right now. Not because of caffeine. Because of when you drink it and what is missing from it. This addition changes that. Free plan in bio.",
    "If nothing has worked for your belly fat after 40, cortisol is the problem and your morning coffee is making it worse. This addition targets it specifically. Free guide in bio.",
    "The reason calorie cutting makes belly fat worse after 40. Your cortisol rises. Your coffee amplifies it. This one addition stops that loop. Free in bio.",
    "Doctors don't tell you this: your morning coffee spikes cortisol in women over 40, which directly stores belly fat. One ingredient added to your cup reverses this. Free ritual in bio.",
    "I need you to hear something. You are not lazy. You are not broken. Your hormones shifted and your morning coffee is making it worse without you knowing. This fixes it. Free in bio.",
    "Stop blaming yourself for the belly fat. After 40 it's biological. Your estrogen dropped. Your cortisol rose. Your morning coffee is amplifying it. This fixes it. Free link in bio.",
    "You are not failing at weight loss. The diet rules you were given do not apply to your body after 40. Your morning coffee, done right, is the real fix. Free plan in bio.",
    "For every woman over 40 who has tried everything and thinks it is her fault — it is not your fault. Your hormones changed. Here is what to add to your morning coffee. Free in bio.",
    "My doctor said I had to take medication for my belly fat. I added this to my morning coffee for 3 weeks first. I never needed the medication. Free ritual is in my bio.",
    "My nutritionist told me to cut carbs. I tried for four months. Nothing worked. Then she told me what my morning coffee was doing to my cortisol. This changed everything. Free in bio.",
    "She was told weight gain at 50 was just aging. Three doctors said so. Then she found this morning coffee ritual. Twelve weeks later she called them back. Free plan in bio.",
    "My gynecologist finally said it. Belly fat after 40 is a cortisol and estrogen problem, not a calorie problem. And your morning coffee is either helping or making it much worse. Free in bio.",
    "What happens to your belly fat when you add this to your morning coffee for 21 days. The answer surprised 214,000 women. Free plan in bio.",
    "There is one thing your morning coffee is missing. Women over 40 who found it stopped losing sleep over their weight. Free guide in bio.",
    "The reason your belly fat responds differently than it did at 35. And the morning coffee adjustment that accounts for that difference. Free plan in bio.",
    "What if belly fat after 40 was never about how much you ate. Women who discovered this morning coffee ritual would agree with you now. Free plan in bio.",
    "The moment you understand that belly fat after 40 is a hormone problem, not a calorie problem, everything changes. And your morning coffee is the easiest fix. Free in bio.",
    "This is for the woman who has been dieting since January and is still in the same body. Not your fault. Your morning coffee is working against you. Here is the fix. Free in bio.",
    "If you are over 40 and frustrated that nothing is working for your belly fat, this message is for you. Your cortisol is spiking every morning and this addition stops it. Free plan in bio.",
    "For the woman who gave up. Who decided this is just what my body looks like now. Please try this first. One thing added to your morning coffee. 21 days. Free guide in bio.",
    "I see you skipping meals, over-exercising, cutting carbs, feeling exhausted. I did all of that. Then I fixed my morning coffee instead. Free plan in bio.",
    "I added this to my morning coffee every day for 21 days and lost my belly fat without trying. Real results at 47. Free 21-day plan in bio.",
    "48 years old. 22 pounds gone in 8 weeks. One change to my morning coffee. No diet. No gym. Just the thing I had been missing. Free ritual in bio.",
    "Before this coffee ritual I was stuck at 178 pounds for two years. After three weeks I was 163. I had not changed a single meal. Free ritual in bio.",
    "My mom called me after five weeks. She said she had to share a photo with me. She was 58 and had lost 19 pounds just by changing her morning coffee ritual. Free plan in bio.",
    "She wore a bikini at 55 for the first time in 14 years. Not because she dieted. Because she changed what she added to her morning coffee every day. Free plan in bio.",
    "Stop starving yourself. Stop over-exercising. Start fixing your morning coffee. 21 days. This tasteless powder does the rest. Free plan in bio.",
    "You have permission to stop dieting. After 40 the old rules do not apply. The new rule is this morning coffee ritual. 21 days. Free plan in bio.",
    "Eat the pasta. Skip the 5am run. Just add this to your morning coffee instead. Women over 40 are losing more weight doing this than they ever did dieting. Free plan in bio.",
    "She stopped trying to lose weight. She just started fixing her morning coffee. The weight came off without her chasing it. Free ritual in bio.",
    "The first 90 minutes after you wake up determine how your body stores or burns fat for the rest of the day. Your morning coffee changes everything during that window. Free plan in bio.",
    "Cortisol peaks within 30 minutes of waking. Adding this to your morning coffee during that window changes everything that happens to your belly fat that day. Free plan in bio.",
    "Your body has a metabolic window every morning between 6am and 9am. This addition to your morning coffee activates it. Women over 40 are finally losing stubborn fat because of this. Free plan in bio.",
    "Every morning you have a 21-minute window when your cortisol is highest. This one addition to your coffee during that window makes fat burning possible for the rest of the day. Free in bio.",
    "The morning coffee ritual that 47,000 women are using to lose hormonal belly fat after 40. No gym. No starvation. Just your coffee, done differently. Free ritual — tap the link in my bio.",
    "Here is what nobody tells you about coffee and weight loss after 40. Your cortisol peaks in the morning. Coffee amplifies it. This one addition blocks that response. Free in bio.",
]

# ── Coffee ritual cards — the core save-worthy content ───────────────────────
RECIPE_CARDS = [
    {
        "title": "THE CORTISOL COFFEE RITUAL",
        "ingredients": [
            "* 1 cup hot black coffee",
            "* 1 packet Java Burn (tasteless)",
            "* Optional: splash of almond milk",
            "* Drink before 9am",
            "* Do this every morning",
        ],
        "instruction": "Stir Java Burn into your coffee. 10 seconds.",
        "benefit": "Blocks cortisol spike + melts belly fat",
    },
    {
        "title": "HORMONE RESET COFFEE",
        "ingredients": [
            "* 1 cup morning coffee",
            "* 1 packet Java Burn",
            "* 1/2 tsp cinnamon (optional)",
            "* Drink on empty stomach",
            "* Best before 8am",
        ],
        "instruction": "Add to your first coffee of the day.",
        "benefit": "Balances estrogen + ignites metabolism",
    },
    {
        "title": "BELLY FAT COFFEE RITUAL",
        "ingredients": [
            "* 1 cup black coffee",
            "* 1 packet Java Burn",
            "* Do NOT add sugar",
            "* Drink within 10 min of waking",
            "* Repeat daily for 21 days",
        ],
        "instruction": "Stir and drink. Takes 10 seconds.",
        "benefit": "Targets hormonal belly fat at the root",
    },
    {
        "title": "ANTI-INFLAMMATORY COFFEE",
        "ingredients": [
            "* 1 cup hot coffee",
            "* 1 packet Java Burn",
            "* 1/4 tsp turmeric (optional)",
            "* Pinch of black pepper",
            "* Drink before breakfast",
        ],
        "instruction": "Mix well. Drink hot or iced.",
        "benefit": "Fights inflammation + reduces fat",
    },
    {
        "title": "METABOLISM MORNING COFFEE",
        "ingredients": [
            "* 1 cup strong black coffee",
            "* 1 packet Java Burn",
            "* Drink before 9am",
            "* No sugar, no creamer",
            "* Best results: drink daily",
        ],
        "instruction": "Stir packet into your morning coffee.",
        "benefit": "Jumpstarts metabolism + kills cravings",
    },
    {
        "title": "PERIMENOPAUSE COFFEE FIX",
        "ingredients": [
            "* 1 cup morning coffee",
            "* 1 packet Java Burn",
            "* Optional: coconut milk",
            "* Drink every morning",
            "* 21 days for full results",
        ],
        "instruction": "Add Java Burn. Stir. Drink. Done.",
        "benefit": "Relieves hormone symptoms + melts belly fat",
    },
    {
        "title": "DETOX COFFEE RITUAL",
        "ingredients": [
            "* 1 cup black coffee",
            "* 1 packet Java Burn",
            "* Juice of 1/4 lemon (optional)",
            "* Drink on empty stomach",
            "* Before 9am daily",
        ],
        "instruction": "Stir well. Drink before eating anything.",
        "benefit": "Flushes toxins + activates fat burning",
    },
    {
        "title": "SLEEP + SLIM COFFEE TRICK",
        "ingredients": [
            "* 1 cup decaf coffee (PM ritual)",
            "* 1 packet Java Burn",
            "* 1 tsp honey (optional)",
            "* Drink 2 hours before bed",
            "* Works overnight too",
        ],
        "instruction": "Java Burn works in decaf too.",
        "benefit": "Improves sleep + overnight fat burning",
    },
    {
        "title": "HIGH ENERGY FAT BURNER",
        "ingredients": [
            "* 1 cup strong coffee",
            "* 1 packet Java Burn",
            "* No sugar needed",
            "* Drink before 10am",
            "* Replace breakfast if desired",
        ],
        "instruction": "Stir and drink. Energy in 20 minutes.",
        "benefit": "Boosts energy + melts stubborn fat",
    },
    {
        "title": "ESTROGEN BALANCE COFFEE",
        "ingredients": [
            "* 1 cup morning coffee",
            "* 1 packet Java Burn",
            "* Pinch of cinnamon",
            "* Drink at sunrise if possible",
            "* Daily habit = daily results",
        ],
        "instruction": "Stir Java Burn in. Sip slowly.",
        "benefit": "Balances estrogen + reduces cravings",
    },
    {
        "title": "BLOAT BUSTER COFFEE",
        "ingredients": [
            "* 1 cup black coffee",
            "* 1 packet Java Burn",
            "* Drink hot, first thing",
            "* No dairy creamer",
            "* Works in 24 hours",
        ],
        "instruction": "Stir and drink on empty stomach.",
        "benefit": "Eliminates bloat + ignites metabolism",
    },
    {
        "title": "DARK CHOCOLATE COFFEE RITUAL",
        "ingredients": [
            "* 1 cup hot coffee",
            "* 1 packet Java Burn",
            "* 1 tsp raw cacao powder",
            "* Pinch of cinnamon",
            "* Drink before 9am",
        ],
        "instruction": "Blend or stir well. Tastes like mocha.",
        "benefit": "Stops cravings + melts belly fat",
    },
    {
        "title": "THYROID SUPPORT COFFEE",
        "ingredients": [
            "* 1 cup black coffee",
            "* 1 packet Java Burn",
            "* Drink in the morning",
            "* Avoid fluoride water",
            "* Daily for best thyroid support",
        ],
        "instruction": "Simple. Add packet. Stir. Drink.",
        "benefit": "Supports thyroid + boosts metabolism",
    },
    {
        "title": "STRESS BELLY FIX COFFEE",
        "ingredients": [
            "* 1 cup morning coffee",
            "* 1 packet Java Burn",
            "* 1/2 tsp ashwagandha (optional)",
            "* Drink mid-morning if stressed",
            "* 21 days to see full results",
        ],
        "instruction": "Stir everything in. Drink warm.",
        "benefit": "Lowers cortisol + melts stress belly fat",
    },
    {
        "title": "COLLAGEN GLOW COFFEE",
        "ingredients": [
            "* 1 cup hot coffee",
            "* 1 packet Java Burn",
            "* 1 scoop collagen peptides",
            "* Splash of coconut milk",
            "* Drink daily for skin + fat",
        ],
        "instruction": "Stir until fully dissolved.",
        "benefit": "Tightens skin + reduces fat",
    },
    {
        "title": "INSULIN RESET COFFEE",
        "ingredients": [
            "* 1 cup black coffee",
            "* 1 packet Java Burn",
            "* NO sugar, no creamer",
            "* Drink before eating",
            "* Key: drink it first thing",
        ],
        "instruction": "First thing in the morning. Non-negotiable.",
        "benefit": "Stabilizes blood sugar + stops fat storage",
    },
    {
        "title": "ALL-DAY ENERGY COFFEE",
        "ingredients": [
            "* 1 cup morning coffee",
            "* 1 packet Java Burn",
            "* Drink before 10am",
            "* Works with any coffee brand",
            "* Tasteless — no flavor change",
        ],
        "instruction": "Stir packet in. Drink as normal.",
        "benefit": "All-day energy + zero belly fat spike",
    },
    {
        "title": "LEAN BODY COFFEE RITUAL",
        "ingredients": [
            "* 1 cup strong coffee",
            "* 1 packet Java Burn",
            "* Drink iced or hot",
            "* Best on empty stomach",
            "* 5 days/week minimum",
        ],
        "instruction": "Add Java Burn. Mix. Done in 10 seconds.",
        "benefit": "Reduces water retention + tones body",
    },
    {
        "title": "IMMUNITY + SLIM COFFEE",
        "ingredients": [
            "* 1 cup hot coffee",
            "* 1 packet Java Burn",
            "* 1 tsp raw honey (optional)",
            "* 1/4 tsp ginger powder",
            "* Drink first thing daily",
        ],
        "instruction": "Stir all in. Sip while hot.",
        "benefit": "Strengthens immunity + reduces fat",
    },
    {
        "title": "21-DAY COFFEE RITUAL",
        "ingredients": [
            "* 1 cup morning coffee",
            "* 1 packet Java Burn (daily)",
            "* Any coffee — hot or iced",
            "* No diet changes needed",
            "* 21 days for full transformation",
        ],
        "instruction": "Add Java Burn every morning for 21 days.",
        "benefit": "The Java Burn protocol for women 40+",
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
            log(f"Les 3 slots de {slot_date} sont deja publies - skip")
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

