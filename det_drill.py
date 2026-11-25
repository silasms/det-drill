#!/usr/bin/env python3
"""
DET Drill Pro - Duolingo English Test Complete Training Suite
Pedagogically Engineered for UFRJ B2/C1 Score (95-115+)
Integrated with AnkiConnect, Speech Engine, Microphone Capture & Google Gemini AI

Core Features:
1. Native Audio Generation (TTS) with Automatic MP3 in Anki Cards
2. Real Microphone Audio Capture (WAV) with Gemini Multimodal Speaking Analysis
3. Dynamic C-Test Engine (AI-generated scientific texts formatted to DET specs)
4. Comprehensive 4-Subscore Tracking (Literacy, Comprehension, Conversation, Production)
5. Full coverage of all Duolingo English Test Skills
"""

import os
import sys
import time
import json
import random
import re
import signal
import hashlib
import shutil
import difflib
import threading
import queue
import tempfile
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from datetime import date, datetime

IS_MACOS = (sys.platform == "darwin")
IS_WINDOWS = (os.name == "nt" or sys.platform.startswith("win"))
if IS_WINDOWS:
    os.system("")  # Enable ANSI color codes on Windows 10/11 PowerShell & CMD

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.expanduser("~/.config/det-drill")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
PENDING_CARDS_FILE = os.path.join(DATA_DIR, "pending_anki_cards.json")
GEMINI_KEY_FILE = os.path.join(DATA_DIR, "gemini_key.txt")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
PHOTO_CATALOG_FILE = os.path.join(DATA_DIR, "photo_catalog.json")
C_TEST_ARCHIVE_FILE = os.path.join(DATA_DIR, "c_test_archive.json")
INTERACTIVE_READING_ARCHIVE_FILE = os.path.join(DATA_DIR, "interactive_reading_archive.json")
READ_SELECT_ARCHIVE_FILE = os.path.join(DATA_DIR, "read_select_archive.json")
LISTEN_TYPE_ARCHIVE_FILE = os.path.join(DATA_DIR, "listen_type_archive.json")
VOCAB_DRILL_ARCHIVE_FILE = os.path.join(DATA_DIR, "vocab_drill_archive.json")
WRITING_PROMPTS_ARCHIVE_FILE = os.path.join(DATA_DIR, "writing_prompts_archive.json")
SPEAKING_PROMPTS_ARCHIVE_FILE = os.path.join(DATA_DIR, "speaking_prompts_archive.json")
INTERACTIVE_LISTENING_ARCHIVE_FILE = os.path.join(DATA_DIR, "interactive_listening_archive.json")
SEEN_HISTORY_FILE = os.path.join(DATA_DIR, "seen_history.json")
TTS_CACHE_DIR = os.path.join(tempfile.gettempdir(), "det_tts_cache")

if IS_MACOS:
    ANKI_MEDIA_DIR = os.path.expanduser("~/Library/Application Support/Anki2/User 1/collection.media")
elif IS_WINDOWS:
    _appdata = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
    ANKI_MEDIA_DIR = os.path.join(_appdata, "Anki2", "User 1", "collection.media")
else:
    ANKI_MEDIA_DIR = os.path.expanduser("~/.local/share/Anki2/User 1/collection.media")
ANKI_URL = "http://127.0.0.1:8765"

# ANSI Colors
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
UNDERLINE = "\033[4m"
BG_BLUE = "\033[44m"
BG_YELLOW = "\033[43m\033[30m"
RESET = "\033[0m"

# ==============================================================================
# SEEN HISTORY & ADAPTIVE WEAK WORDS ENGINE
# ==============================================================================
_SEEN_LOCK = threading.Lock()

def load_seen_history():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(SEEN_HISTORY_FILE):
        try:
            with open(SEEN_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"seen": {}, "weak_words": []}

def save_seen_history(data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SEEN_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def make_item_id(val):
    if isinstance(val, dict):
        raw = val.get("title") or val.get("audio") or val.get("question") or val.get("word") or json.dumps(val, sort_keys=True)
    else:
        raw = str(val)
    return hashlib.md5(raw.strip().lower().encode("utf-8")).hexdigest()[:12]

def is_item_seen(category, item):
    with _SEEN_LOCK:
        data = load_seen_history()
        seen_list = data.get("seen", {}).get(category, [])
        return make_item_id(item) in seen_list

def mark_item_seen(category, item):
    with _SEEN_LOCK:
        data = load_seen_history()
        seen_map = data.setdefault("seen", {})
        cat_list = seen_map.setdefault(category, [])
        iid = make_item_id(item)
        if iid not in cat_list:
            cat_list.append(iid)
            if len(cat_list) > 500:
                seen_map[category] = cat_list[-500:]
            save_seen_history(data)

def record_weak_word(word):
    w = re.sub(r"[^a-zA-Z\-]", "", str(word)).lower().strip()
    if len(w) < 3:
        return
    with _SEEN_LOCK:
        data = load_seen_history()
        weak = data.setdefault("weak_words", [])
        if w in weak:
            weak.remove(w)
        weak.append(w)
        if len(weak) > 20:
            data["weak_words"] = weak[-20:]
        save_seen_history(data)

def get_weak_words_hint(limit=3):
    with _SEEN_LOCK:
        data = load_seen_history()
        weak = data.get("weak_words", [])
    if not weak:
        return ""
    sample = random.sample(weak, min(limit, len(weak)))
    return (
        f"\nAdaptive Spaced-Repetition Requirement: If contextually natural, incorporate 1 or 2 of these words "
        f"the student recently missed: {', '.join(sample)}."
    )

# ==============================================================================
# C1 LEXICAL ACTIVATION MISSION & LOCAL ANTI-CLICHÉ RADAR (0ms / 0 API COST)
# ==============================================================================
C1_POWER_ARSENAL = [
    ("mitigate", "atenuar / reduzir impactos"),
    ("consequently", "consequentemente"),
    ("notwithstanding", "não obstante / apesar de"),
    ("substantiate", "comprovar com evidências"),
    ("pivotal", "fundamental / crucial"),
    ("conversely", "por outro lado / inversamente"),
    ("exacerbate", "agravar / intensificar"),
    ("ubiquitous", "onipresente"),
    ("foster", "fomentar / promover"),
    ("imperative", "imperativo / essencial"),
    ("albeit", "embora / ainda que"),
    ("undermine", "minar / enfraquecer"),
    ("paradigm", "paradigma / modelo"),
    ("detrimental", "prejudicial / nocivo"),
    ("corroborate", "corroborar / confirmar")
]

CLICHE_UPGRADES = [
    (r"\bvery important\b", "very important", "crucial / imperative / paramount"),
    (r"\bvery good\b", "very good", "remarkably effective / advantageous / exemplary"),
    (r"\bvery bad\b", "very bad", "detrimental / counterproductive / severe"),
    (r"\bvery big\b", "very big", "substantial / considerable / extensive"),
    (r"\ba lot of\b", "a lot of", "a substantial amount of / numerous / a plethora of"),
    (r"\bi think\b", "I think", "I contend that / From an analytical standpoint"),
    (r"\bi believe\b", "I believe", "It is evident that / Empirical evidence suggests"),
    (r"\bgood\b", "good", "beneficial / favorable / robust"),
    (r"\bbad\b", "bad", "adverse / deleterious / problematic"),
    (r"\bthings?\b", "thing(s)", "factor(s) / aspect(s) / phenomenon / element(s)"),
    (r"\bpeople\b", "people", "individuals / citizens / stakeholders / researchers"),
    (r"\bmake better\b", "make better", "enhance / optimize / ameliorate")
]

def get_c1_lexical_mission(count=3):
    """Selects 3 target C1 terms (combining student's recent weak words + C1 Power Arsenal)."""
    with _SEEN_LOCK:
        data = load_seen_history()
        weak = list(data.get("weak_words", []))
    arsenal_map = dict(C1_POWER_ARSENAL)
    mission = []
    if weak:
        picked_weak = random.sample(weak, min(1, len(weak)))
        for w in picked_weak:
            meaning = arsenal_map.get(w) or WORD_DEFINITIONS.get(w, "seu ponto fraco recente").split(" — ")[0]
            mission.append((w, meaning))
    remaining_candidates = [item for item in C1_POWER_ARSENAL if item[0] not in {m[0] for m in mission}]
    mission.extend(random.sample(remaining_candidates, min(count - len(mission), len(remaining_candidates))))
    return mission

def print_c1_mission_banner(mission):
    """Displays the C1 Lexical Activation Challenge before a production task."""
    terms_str = "  |  ".join([f"{BOLD}{CYAN}{w}{RESET} {DIM}({m}){RESET}" for w, m in mission])
    print(f"{MAGENTA}┌─────────────────────────────────────────────────────────────────────────────┐{RESET}")
    print(f"{MAGENTA}│{RESET} 🎯 {BOLD}MISSÃO DE ATIVAÇÃO C1 (Destrave seu Vocabulário Ativo):{RESET}                  {MAGENTA}│{RESET}")
    print(f"{MAGENTA}│{RESET} Tente encaixar pelo menos {BOLD}1 ou 2{RESET} destes termos na sua resposta:             {MAGENTA}│{RESET}")
    print(f"{MAGENTA}└─────────────────────────────────────────────────────────────────────────────┘{RESET}")
    print(f"  👉 {terms_str}\n")

def evaluate_c1_mission_and_cliches(text, mission):
    """Evaluates C1 mission hits and detects A1/A2 clichés 100% locally in 0ms."""
    if not text or not text.strip():
        return
    lower_t = text.lower()
    hits = [w for w, _ in mission if w.lower() in lower_t]
    if hits:
        print(f"• 🏆 {GREEN}{BOLD}Missão C1 Cumprida!{RESET} Você ativou com sucesso: {GREEN}{BOLD}{', '.join(hits)}{RESET}")
    else:
        missed_m = ", ".join([w for w, _ in mission])
        print(f"• 🎯 {YELLOW}Missão C1:{RESET} Nenhum dos termos-alvo ({missed_m}) foi usado nesta rodada.")

    detected_cliches = []
    for pattern, label, upgrade in CLICHE_UPGRADES:
        if re.search(pattern, lower_t):
            detected_cliches.append((label, upgrade))

    if detected_cliches:
        print(f"\n{YELLOW}{BOLD}⚡ RADAR LOCAL ANTI-CLICHÊ (Substitua termos básicos A2 por C1):{RESET}")
        for label, upgrade in detected_cliches[:4]:
            print(f"  ⚠️  Evite {RED}'{label}'{RESET} ➔ Prefira {GREEN}{BOLD}{upgrade}{RESET}")

# ==============================================================================
# AUDIO ENGINE (High-Quality Cached TTS & Cross-Platform Linux/macOS Playback)
# ==============================================================================
def get_cached_tts_mp3(text):
    """Fetches high-quality Google TTS MP3 and caches it locally by hash for 0ms replay & Anki copy."""
    if not text or not text.strip():
        return None
    os.makedirs(TTS_CACHE_DIR, exist_ok=True)
    h = hashlib.md5(text.strip().encode("utf-8")).hexdigest()[:16]
    cached_path = os.path.join(TTS_CACHE_DIR, f"tts_{h}.mp3")
    if os.path.exists(cached_path) and os.path.getsize(cached_path) > 500:
        return cached_path
    try:
        q = urllib.parse.quote(text.strip()[:200])
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en-US&client=tw-ob&q={q}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            audio_data = resp.read()
            if len(audio_data) > 500:
                with open(cached_path, "wb") as f:
                    f.write(audio_data)
                return cached_path
    except Exception:
        pass
    return None

def speak_text(text):
    """Plays natural human-like English TTS audio across Linux, macOS, and Windows."""
    try:
        # 1. Try playing high-quality cached Google TTS MP3
        mp3_path = get_cached_tts_mp3(text)
        if mp3_path:
            if IS_MACOS and shutil.which("afplay"):
                subprocess.run(["afplay", mp3_path], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            elif shutil.which("ffplay"):
                subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", mp3_path],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            elif shutil.which("mpv"):
                subprocess.run(["mpv", "--no-video", "--really-quiet", mp3_path],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True

        # 2. Fallback to native OS speech synthesizer
        if IS_MACOS and shutil.which("say"):
            subprocess.run(["say", "-v", "Samantha", "-r", "175", text], check=False)
            return True
        elif IS_WINDOWS:
            safe_txt = text.replace("'", "''")
            ps_cmd = f"Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 0; $s.Speak('{safe_txt}')"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        elif shutil.which("spd-say"):
            subprocess.run(["spd-say", "-l", "en", "-r", "-10", "-p", "10", text], check=False)
            return True
        elif shutil.which("espeak-ng"):
            subprocess.run(["espeak-ng", "-v", "en-us", "-s", "145", text], check=False)
            return True
    except Exception:
        pass
    return False

def generate_anki_audio(text, base_name):
    """Generates an MP3 audio file and copies it to Anki's collection.media (reuses TTS cache if present)."""
    os.makedirs(ANKI_MEDIA_DIR, exist_ok=True)
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '', base_name.lower().replace(" ", "_"))[:30]
    h = hashlib.md5(text.strip().encode("utf-8")).hexdigest()[:8]
    filename = f"det_{clean_name}_{h}.mp3"
    target_path = os.path.join(ANKI_MEDIA_DIR, filename)

    if os.path.exists(target_path) and os.path.getsize(target_path) > 500:
        return filename

    # 1. Reuse already downloaded TTS cache (0ms network cost!)
    cached_mp3 = get_cached_tts_mp3(text)
    if cached_mp3 and os.path.exists(cached_mp3):
        try:
            shutil.copy2(cached_mp3, target_path)
            return filename
        except Exception:
            pass

    # 2. Fallback to local macOS say / Windows SAPI / Linux espeak-ng + ffmpeg
    try:
        wav_tmp = os.path.join(tempfile.gettempdir(), f"{filename}.wav")
        if IS_MACOS and shutil.which("say"):
            subprocess.run(["say", "-v", "Samantha", "-o", wav_tmp, "--data-format=LEI16@22050", text],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif IS_WINDOWS:
            safe_txt = text.replace("'", "''")
            ps_cmd = (
                f"Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.SetOutputToWaveFile('{wav_tmp}'); $s.Speak('{safe_txt}'); $s.Dispose()"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("espeak-ng"):
            subprocess.run(["espeak-ng", "-v", "en-us", "-s", "140", "-w", wav_tmp, text],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(wav_tmp):
            subprocess.run(["ffmpeg", "-y", "-i", wav_tmp, "-codec:a", "libmp3lame", "-qscale:a", "4", target_path],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.remove(wav_tmp)
            if os.path.exists(target_path):
                return filename
    except Exception:
        pass

    return None

# ==============================================================================
# ANKI CONNECT INTEGRATION (With 30s Status Cache & Async Background Worker)
# ==============================================================================
_ANKI_STATUS_CACHE = {"online": False, "ts": 0.0}
_ANKI_QUEUE = queue.Queue()

def anki_invoke(action, **params):
    """Executes an action via AnkiConnect API."""
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(ANKI_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("error"):
                return {"success": False, "error": data["error"]}
            return {"success": True, "result": data.get("result")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def is_anki_online(force=False):
    """Checks if AnkiConnect is answering (cached for 30s to avoid redundant HTTP calls on redraws)."""
    now = time.time()
    if not force and (now - _ANKI_STATUS_CACHE["ts"] < 30.0):
        return _ANKI_STATUS_CACHE["online"]
    res = anki_invoke("version")
    online = res.get("success", False)
    _ANKI_STATUS_CACHE["online"] = online
    _ANKI_STATUS_CACHE["ts"] = now
    return online

def ensure_anki_running():
    """Starts Anki in background if not open."""
    if is_anki_online(force=True):
        return True
    try:
        if IS_MACOS:
            subprocess.Popen(["open", "-a", "Anki"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["anki", "-p", "User 1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(10):
            time.sleep(0.5)
            if is_anki_online(force=True):
                return True
    except Exception:
        pass
    return is_anki_online(force=True)

def load_pending_cards():
    if os.path.exists(PENDING_CARDS_FILE):
        try:
            with open(PENDING_CARDS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_pending_cards(cards):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PENDING_CARDS_FILE, "w") as f:
        json.dump(cards, f, indent=2)

def flush_pending_cards():
    """Uploads offline cached cards to Anki."""
    cards = load_pending_cards()
    if not cards or not is_anki_online(force=True):
        return 0

    uploaded = 0
    remaining = []
    for card in cards:
        res = _push_to_anki_sync(card["deck"], card["front"], card["back"], card.get("tags"), audio_text=None, save_on_fail=False)
        if res:
            uploaded += 1
        else:
            remaining.append(card)
    save_pending_cards(remaining)
    return uploaded

def _push_to_anki_sync(subdeck_name, front_html, back_html, tags=None, audio_text=None, save_on_fail=True):
    """Synchronous worker implementation that generates MP3 and pushes flashcard to AnkiConnect."""
    full_deck = f"Duolingo English Test::{subdeck_name}"
    tags = tags or ["DET"]

    if audio_text:
        audio_file = generate_anki_audio(audio_text, subdeck_name)
        if audio_file:
            back_html += f"<br><br>[sound:{audio_file}]"

    if is_anki_online():
        anki_invoke("createDeck", deck=full_deck)
        note_payload = {
            "deckName": full_deck,
            "modelName": "Basic",
            "fields": {
                "Front": front_html,
                "Back": back_html
            },
            "options": {"allowDuplicate": False, "duplicateScope": "deck"},
            "tags": tags
        }
        res = anki_invoke("addNote", note=note_payload)
        if res.get("success"):
            nid = res.get("result")
            if nid:
                cards_res = anki_invoke("findCards", query=f"nid:{nid}")
                if cards_res.get("success") and cards_res.get("result"):
                    anki_invoke("changeDeck", cards=cards_res["result"], deck=full_deck)
            return True

    if save_on_fail:
        cards = load_pending_cards()
        cards.append({
            "deck": subdeck_name,
            "front": front_html,
            "back": back_html,
            "tags": tags,
            "created_at": datetime.now().isoformat()
        })
        save_pending_cards(cards)
        return True
    return False

def _anki_background_worker():
    while True:
        try:
            job = _ANKI_QUEUE.get()
            if job is None:
                _ANKI_QUEUE.task_done()
                break
            _push_to_anki_sync(*job)
            _ANKI_QUEUE.task_done()
        except Exception:
            try:
                _ANKI_QUEUE.task_done()
            except Exception:
                pass

_ANKI_WORKER_THREAD = threading.Thread(target=_anki_background_worker, daemon=True)
_ANKI_WORKER_THREAD.start()

def push_to_anki(subdeck_name, front_html, back_html, tags=None, audio_text=None, save_on_fail=True):
    """Non-blocking instant enqueue of Anki card creation (0ms UI latency)."""
    _ANKI_QUEUE.put((subdeck_name, front_html, back_html, tags, audio_text, save_on_fail))
    return True

def wait_anki_queue(timeout=3.0):
    """Waits up to timeout seconds for background Anki uploads to finish on exit."""
    t0 = time.time()
    while not _ANKI_QUEUE.empty() and (time.time() - t0 < timeout):
        time.sleep(0.05)

# ==============================================================================
# GEMINI AI PRO INTEGRATION (Persistent Singleton Client & Native JSON Mode)
# ==============================================================================
_GEMINI_CLIENT = None
_GEMINI_CLIENT_KEY = None

def get_gemini_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ.get("GEMINI_API_KEY").strip()
    if os.path.exists(GEMINI_KEY_FILE):
        try:
            with open(GEMINI_KEY_FILE, "r") as f:
                k = f.read().strip()
                if k:
                    return k
        except Exception:
            pass
    return None

def set_gemini_key(key):
    global _GEMINI_CLIENT, _GEMINI_CLIENT_KEY
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(GEMINI_KEY_FILE, "w") as f:
        f.write(key.strip())
    _GEMINI_CLIENT = None
    _GEMINI_CLIENT_KEY = None

def get_gemini_client():
    """Returns a persistent singleton Gemini client (reuses HTTP Keep-Alive / TLS session)."""
    global _GEMINI_CLIENT, _GEMINI_CLIENT_KEY
    api_key = get_gemini_key()
    if not api_key:
        return None
    if _GEMINI_CLIENT is None or _GEMINI_CLIENT_KEY != api_key:
        from google import genai
        _GEMINI_CLIENT = genai.Client(api_key=api_key)
        _GEMINI_CLIENT_KEY = api_key
    return _GEMINI_CLIENT

def call_gemini(prompt, system_instruction=None, json_mode=False, max_tokens=None):
    """Calls Gemini using persistent client, native JSON mode, and low-latency flash-lite priority."""
    client = get_gemini_client()
    if not client:
        return None
    try:
        from google.genai import types
        contents = prompt
        if system_instruction:
            contents = f"{system_instruction}\n\nUser: {prompt}"

        cfg_kwargs = {}
        if json_mode:
            cfg_kwargs["response_mime_type"] = "application/json"
            cfg_kwargs["temperature"] = 0.25
        if max_tokens:
            cfg_kwargs["max_output_tokens"] = max_tokens
        config = types.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None

        for model_name in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )
                if response and response.text:
                    return response.text
            except Exception:
                continue
        return None
    except Exception as e:
        return f"[Erro Gemini: {e}]"

def analyze_image_with_gemini(image_path, prompt_text):
    """Analyzes a real photo file alongside the student's description via Gemini Multimodal API."""
    client = get_gemini_client()
    if not client or not os.path.exists(image_path):
        return call_gemini(prompt_text)
    try:
        from google.genai import types
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        ext = image_path.lower().rsplit(".", 1)[-1]
        mime = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")

        for model_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type=mime),
                        prompt_text
                    ]
                )
                if response and response.text:
                    return response.text
            except Exception:
                continue
        return call_gemini(prompt_text)
    except Exception:
        return call_gemini(prompt_text)

def analyze_audio_with_gemini(audio_path, prompt_text, image_path=None, custom_sys_inst=None):
    """Analyzes user's spoken audio (and optional photo) directly via Gemini Multimodal API with fallback."""
    client = get_gemini_client()
    if not client or not os.path.exists(audio_path):
        return None
    try:
        from google.genai import types
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        sys_inst = custom_sys_inst or (
            "Você é um Examinador Sênior Oficial do Duolingo English Test (DET). "
            "Avalie com rigor pedagógico e construtivo o áudio do candidato na questão de Speaking.\n\n"
            "Estruture sua resposta estritamente nas seguintes seções:\n"
            "1. 🎙️ TRANSCRIÇÃO EXATA:\n"
            "Transcreva palavra por palavra o que o candidato falou, indicando pausas longas e repetições.\n\n"
            "2. ⚡ FLUÊNCIA, ACÚSTICA & PRONÚNCIA:\n"
            "Avalie o ritmo (palavras por minuto estimadas), pausas silenciosas, hesitações e clareza da pronúncia (destaque palavras específicas pronunciadas incorretamente com dica fonética simples para brasileiros).\n\n"
            "3. 📝 GRAMÁTICA & VOCABULÁRIO:\n"
            "Destaque erros gramaticais e estruturas incompletas, apresentando as correções formais.\n\n"
            "4. 📊 NOTA ESTIMADA DET (Escala 10 a 160) & NÍVEL CEFR:\n"
            "Dê uma estimativa realista dos subscores Conversation e Production (ex: 85-95/160, Nível B2).\n\n"
            "5. ✨ MODELO REFINADO B2/C1 (Meta UFRJ 95-105+):\n"
            "Apresente como o candidato deveria responder à mesma pergunta em 3 blocos estruturados e fluidos.\n"
            "Coloque também a melhor frase-chave resumida sozinha em uma linha após o marcador EXATO 'SPEAK_MODEL: ' para treino de áudio/shadowing.\n\n"
            "IMPORTANTE: Ao final absoluto da sua mensagem, inclua obrigatoriamente a tag de pontuação no formato exato:\n"
            "[DET_EVAL: CONVERSATION=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )

        contents_list = []
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as img_f:
                img_bytes = img_f.read()
            ext = image_path.lower().rsplit(".", 1)[-1]
            mime = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
            contents_list.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))

        contents_list.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"))
        contents_list.append(f"{sys_inst}\n\nTask Prompt: {prompt_text}")

        for model_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents_list
                )
                if response and response.text:
                    return response.text
            except Exception:
                continue
        return None
    except Exception as e:
        return f"[Erro ao analisar áudio com Gemini: {e}]"


def analyze_multiple_audios_with_gemini(audio_paths, prompt_text, sys_inst):
    """Analyzes multiple sequential audio blocks (e.g., 3-block scaffolded speaking) in a single Gemini Multimodal call."""
    client = get_gemini_client()
    if not client:
        return None
    try:
        from google.genai import types
        contents_list = []
        for idx, ap in enumerate(audio_paths, 1):
            if ap and os.path.exists(ap) and os.path.getsize(ap) > 2000:
                with open(ap, "rb") as f:
                    ab = f.read()
                contents_list.append(f"--- AUDIO BLOCK {idx} ---")
                contents_list.append(types.Part.from_bytes(data=ab, mime_type="audio/wav"))
        if not contents_list:
            return None
        contents_list.append(f"{sys_inst}\n\nTask Prompt: {prompt_text}")

        for model_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents_list
                )
                if response and response.text:
                    return response.text
            except Exception:
                continue
        return None
    except Exception as e:
        return f"[Erro ao analisar blocos de áudio com Gemini: {e}]"


def print_speaking_coach_scorecard(conv_score, prod_score, mode_label="SPEAKING COACH"):
    """Displays a visual DET Speaking scorecard (10-160) with progress bars, UFRJ goal status, and session history."""
    overall = int(round((conv_score + prod_score) / 2.0 / 5.0) * 5)
    overall = max(10, min(160, overall))

    load_stats()
    speak_hist = STATS.setdefault("speaking_coach_scores", [])
    delta_str = ""
    if speak_hist:
        last_overall = speak_hist[-1].get("overall", overall)
        diff = overall - last_overall
        if diff > 0:
            delta_str = f" {GREEN}(▲ +{diff} pts vs. anterior){RESET}"
        elif diff < 0:
            delta_str = f" {YELLOW}(▼ {diff} pts vs. anterior){RESET}"
        else:
            delta_str = f" {DIM}(= manteve a nota anterior){RESET}"

    speak_hist.append({
        "date": date.today().isoformat(),
        "mode": mode_label,
        "overall": overall,
        "conversation": conv_score,
        "production": prod_score
    })
    if len(speak_hist) > 30:
        STATS["speaking_coach_scores"] = speak_hist[-30:]
    save_stats()

    def _bar(sc):
        pct = min(100, max(0, int((sc / 160.0) * 100)))
        filled = int(pct / 100.0 * 24)
        c = GREEN if sc >= 95 else (YELLOW if sc >= 80 else RED)
        return f"[{c}{'█' * filled}{'░' * (24 - filled)}{RESET}]"

    print(f"\n{BOLD}{MAGENTA}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{MAGENTA}║{RESET} 🎙️  {BOLD}PONTUAÇÃO DA SUA FALA — {mode_label:<39}{RESET} {BOLD}{MAGENTA}║{RESET}")
    print(f"{BOLD}{MAGENTA}╠══════════════════════════════════════════════════════════════════════╣{RESET}")
    print(f"{BOLD}{MAGENTA}║{RESET} 🏆 {BOLD}NOTA GERAL DE FALA:{RESET}   {BOLD}{overall}/160 pts{RESET}  [{_cefr_badge_for_score(overall)}]{delta_str}")
    print(f"{BOLD}{MAGENTA}║{RESET}    {_bar(overall)} (Meta UFRJ: 95-105 pts)")
    print(f"{BOLD}{MAGENTA}╟──────────────────────────────────────────────────────────────────────╢{RESET}")
    print(f"{BOLD}{MAGENTA}║{RESET} • {BOLD}Conversation (Fluência & Pronúncia):{RESET} {_bar(conv_score)} {BOLD}{conv_score}/160{RESET}")
    print(f"{BOLD}{MAGENTA}║{RESET} • {BOLD}Production   (Estrutura & Léxico C1):{RESET} {_bar(prod_score)} {BOLD}{prod_score}/160{RESET}")
    recent_scores = [str(x.get("overall", 0)) for x in STATS.get("speaking_coach_scores", [])[-5:]]
    if len(recent_scores) > 1:
        print(f"{BOLD}{MAGENTA}╟──────────────────────────────────────────────────────────────────────╢{RESET}")
        print(f"{BOLD}{MAGENTA}║{RESET} 📈 {BOLD}Evolução no Speaking Coach (últimos treinos):{RESET} {CYAN}{' ➔ '.join(recent_scores)} pts{RESET}")
    print(f"{BOLD}{MAGENTA}╚══════════════════════════════════════════════════════════════════════╝{RESET}")

def extract_eval_scores(feedback_text, default_conv=60, default_prod=55):
    """Extracts realistic Conversation and Production subscores from AI feedback."""
    if not feedback_text:
        return default_conv, default_prod
    m = re.search(r'\[DET_EVAL:\s*CONVERSATION=(\d+),\s*PRODUCTION=(\d+)\]', feedback_text, re.IGNORECASE)
    if m:
        return max(10, min(160, int(m.group(1)))), max(10, min(160, int(m.group(2))))
    conv = default_conv
    prod = default_prod
    m_c = re.search(r'Conversation[^\d\n]*(\d{2,3})', feedback_text, re.IGNORECASE)
    if m_c:
        try:
            conv = int(m_c.group(1))
        except ValueError:
            pass
    m_p = re.search(r'Production[^\d\n]*(\d{2,3})', feedback_text, re.IGNORECASE)
    if m_p:
        try:
            prod = int(m_p.group(1))
        except ValueError:
            pass
    return max(10, min(160, conv)), max(10, min(160, prod))

def extract_writing_scores(feedback_text, default_lit=85, default_prod=80):
    """Extracts realistic Literacy and Production subscores from AI writing feedback."""
    if not feedback_text:
        return default_lit, default_prod
    m = re.search(r'\[DET_EVAL:\s*LITERACY=(\d+),\s*PRODUCTION=(\d+)\]', feedback_text, re.IGNORECASE)
    if m:
        return max(10, min(160, int(m.group(1)))), max(10, min(160, int(m.group(2))))
    m_any = re.search(r'(\d{2,3})\s*(?:/\s*160|pts|pontos)', feedback_text, re.IGNORECASE)
    if m_any:
        val = max(10, min(160, int(m_any.group(1))))
        return val, val
    return default_lit, default_prod

def compute_local_writing_breakdown(text, mission=None, target_words=80):
    """Computes an objective local DET writing breakdown and fallback score (10-160)."""
    if not text or not text.strip():
        return {
            "word_count": 0, "target_words": target_words, "connectors": [],
            "mission_hits": [], "cliches": [], "pt_markers": 0,
            "local_lit": 55, "local_prod": 50
        }
    words = text.split()
    word_count = len(words)
    lower_t = text.lower()
    connectors = list(dict.fromkeys([c for c in ACADEMIC_CONNECTORS if c in lower_t]))
    mission_hits = [w for w, _ in (mission or []) if w.lower() in lower_t]
    cliches = []
    for pattern, label, _ in CLICHE_UPGRADES:
        if re.search(pattern, lower_t):
            cliches.append(label)

    # Detect rough Portuguese markers (accents or common PT stopwords when user mixes PT/EN)
    pt_accents = len(re.findall(r'[áàâãéêíóôõúç]', lower_t))
    pt_words = len(re.findall(r'\b(que|não|para|com|uma|porque|mas|como|mais|muito|também|isso|pelo|pela)\b', lower_t))
    pt_markers = pt_accents + pt_words

    # Base score calculation (10-160 DET scale, 95-105 = B2 Meta UFRJ)
    len_ratio = min(1.25, word_count / max(15, target_words))
    base = 65 + int(len_ratio * 25)
    conn_bonus = min(15, len(connectors) * 5)
    c1_bonus = min(15, len(mission_hits) * 6)
    cliche_pen = min(12, len(cliches) * 4)
    pt_pen = min(20, pt_markers * 4)

    local_lit = max(40, min(145, base + conn_bonus + c1_bonus - cliche_pen - pt_pen))
    local_prod = max(35, min(145, base + conn_bonus + int(c1_bonus * 1.2) - cliche_pen - int(pt_pen * 1.2)))
    return {
        "word_count": word_count,
        "target_words": target_words,
        "connectors": connectors,
        "mission_hits": mission_hits,
        "cliches": cliches,
        "pt_markers": pt_markers,
        "local_lit": (local_lit // 5) * 5,
        "local_prod": (local_prod // 5) * 5
    }

def _cefr_badge_for_score(score):
    if score >= 130:
        return f"{GREEN}{BOLD}C1+ (Excelência Acadêmica){RESET}"
    elif score >= 115:
        return f"{GREEN}{BOLD}C1 (Avançado){RESET}"
    elif score >= 95:
        return f"{GREEN}{BOLD}B2 (Meta UFRJ Atingida ✓){RESET}"
    elif score >= 80:
        return f"{YELLOW}{BOLD}B1+ (Quase na Meta UFRJ){RESET}"
    elif score >= 65:
        return f"{YELLOW}B1 (Intermediário){RESET}"
    else:
        return f"{RED}A2 (Em Construção){RESET}"

def print_writing_coach_scorecard(lit_score, prod_score, breakdown, mode_label="WRITING COACH"):
    """Displays a visual DET scorecard (10-160) with progress bars, UFRJ goal status, and session history."""
    overall = int(round((lit_score + prod_score) / 2.0 / 5.0) * 5)
    overall = max(10, min(160, overall))

    # Record inside STATS["coach_scores"]
    load_stats()
    coach_hist = STATS.setdefault("coach_scores", [])
    delta_str = ""
    if coach_hist:
        last_overall = coach_hist[-1].get("overall", overall)
        diff = overall - last_overall
        if diff > 0:
            delta_str = f" {GREEN}(▲ +{diff} pts vs. anterior){RESET}"
        elif diff < 0:
            delta_str = f" {YELLOW}(▼ {diff} pts vs. anterior){RESET}"
        else:
            delta_str = f" {DIM}(= manteve a nota anterior){RESET}"

    coach_hist.append({
        "date": date.today().isoformat(),
        "mode": mode_label,
        "overall": overall,
        "literacy": lit_score,
        "production": prod_score
    })
    if len(coach_hist) > 30:
        STATS["coach_scores"] = coach_hist[-30:]
    save_stats()

    def _bar(sc):
        pct = min(100, max(0, int((sc / 160.0) * 100)))
        filled = int(pct / 100.0 * 24)
        c = GREEN if sc >= 95 else (YELLOW if sc >= 80 else RED)
        return f"[{c}{'█' * filled}{'░' * (24 - filled)}{RESET}]"

    wc = breakdown.get("word_count", 0)
    tw = breakdown.get("target_words", 80)
    conns = breakdown.get("connectors", [])
    hits = breakdown.get("mission_hits", [])
    pt_m = breakdown.get("pt_markers", 0)

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║{RESET} 📊 {BOLD}PONTUAÇÃO DO SEU RASCUNHO — {mode_label:<36}{RESET} {BOLD}{CYAN}║{RESET}")
    print(f"{BOLD}{CYAN}╠══════════════════════════════════════════════════════════════════════╣{RESET}")
    print(f"{BOLD}{CYAN}║{RESET} 🏆 {BOLD}NOTA GERAL DO TREINO:{RESET} {BOLD}{overall}/160 pts{RESET}  [{_cefr_badge_for_score(overall)}]{delta_str}")
    print(f"{BOLD}{CYAN}║{RESET}    {_bar(overall)} (Meta UFRJ: 95-105 pts)")
    print(f"{BOLD}{CYAN}╟──────────────────────────────────────────────────────────────────────╢{RESET}")
    print(f"{BOLD}{CYAN}║{RESET} • {BOLD}Literacy   (Estrutura & Gramática):{RESET} {_bar(lit_score)} {BOLD}{lit_score}/160{RESET}")
    print(f"{BOLD}{CYAN}║{RESET} • {BOLD}Production (Léxico & Complexidade):{RESET} {_bar(prod_score)} {BOLD}{prod_score}/160{RESET}")
    print(f"{BOLD}{CYAN}╟──────────────────────────────────────────────────────────────────────╢{RESET}")
    print(f"{BOLD}{CYAN}║{RESET} 🔍 {BOLD}RAIO-X DE DESEMPENHO:{RESET}")
    len_color = GREEN if wc >= tw else YELLOW
    print(f"{BOLD}{CYAN}║{RESET}   • Extensão: {len_color}{BOLD}{wc} palavras{RESET} (referência ideal: ~{tw}+ palavras)")
    conn_str = f"{GREEN}{', '.join(conns[:4])}{RESET}" if conns else f"{YELLOW}Nenhum detectado (use: although, furthermore, consequently){RESET}"
    print(f"{BOLD}{CYAN}║{RESET}   • Conectivos Acadêmicos ({len(conns)}): {conn_str}")
    if hits:
        print(f"{BOLD}{CYAN}║{RESET}   • Missão C1 Ativada: {GREEN}{BOLD}+{len(hits)} termo(s) ({', '.join(hits)}){RESET}")
    if pt_m > 0:
        print(f"{BOLD}{CYAN}║{RESET}   • Trechos em Português no rascunho: {YELLOW}Detectados (ótimo para destravar! Veja a versão C1){RESET}")
    else:
        print(f"{BOLD}{CYAN}║{RESET}   • Idioma do Rascunho: {GREEN}100% em Inglês ✓{RESET}")

    recent_scores = [str(x.get("overall", 0)) for x in STATS.get("coach_scores", [])[-5:]]
    if len(recent_scores) > 1:
        print(f"{BOLD}{CYAN}║{RESET} 📈 {BOLD}Evolução no Writing Coach (últimos treinos):{RESET} {CYAN}{' ➔ '.join(recent_scores)} pts{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════╝{RESET}")

# ==============================================================================
# STATS & 4 SUBSCORES TRACKER
# ==============================================================================
STATS = {}

def load_stats():
    global STATS
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                STATS = json.load(f)
                return STATS
        except Exception:
            pass
    STATS = {
        "streak": 0,
        "last_date": "",
        "drills_completed": 0,
        "skills": {
            "literacy": {"attempts": 0, "correct": 0},
            "comprehension": {"attempts": 0, "correct": 0},
            "conversation": {"attempts": 0, "correct": 0},
            "production": {"attempts": 0, "correct": 0}
        }
    }
    return STATS

def save_stats():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATS_FILE, "w") as f:
        json.dump(STATS, f, indent=2)

def record_skill_progress(skill_names, correct, total):
    """Updates subscore tracking accurately."""
    load_stats()
    skills = STATS.setdefault("skills", {
        "literacy": {"attempts": 0, "correct": 0},
        "comprehension": {"attempts": 0, "correct": 0},
        "conversation": {"attempts": 0, "correct": 0},
        "production": {"attempts": 0, "correct": 0}
    })
    for s in skill_names:
        if s in skills:
            skills[s]["attempts"] += total
            skills[s]["correct"] += correct
    save_stats()

def record_skill_score(skill_name, score):
    """Records an explicit AI evaluated score (10-160) for a subscore."""
    load_stats()
    skills = STATS.setdefault("skills", {
        "literacy": {"attempts": 0, "correct": 0},
        "comprehension": {"attempts": 0, "correct": 0},
        "conversation": {"attempts": 0, "correct": 0},
        "production": {"attempts": 0, "correct": 0}
    })
    sk = skills.setdefault(skill_name, {"attempts": 0, "correct": 0})
    sk["attempts"] += 1
    pct = max(0.0, min(1.0, (score - 60) / 95.0))
    sk["correct"] = round(sk.get("correct", 0) + pct, 2)
    scores = sk.setdefault("scores", [])
    scores.append(int(score))
    if len(scores) > 20:
        sk["scores"] = scores[-20:]
    save_stats()

def update_streak():
    load_stats()
    today_str = date.today().isoformat()
    last = STATS.get("last_date", "")
    if last != today_str:
        if last:
            try:
                diff = (date.today() - date.fromisoformat(last)).days
                if diff == 1:
                    STATS["streak"] += 1
                elif diff > 1:
                    STATS["streak"] = 1
            except Exception:
                STATS["streak"] = 1
        else:
            STATS["streak"] = 1
        STATS["last_date"] = today_str
    STATS["drills_completed"] = STATS.get("drills_completed", 0) + 1
    save_stats()

# ==============================================================================
# C-TEST ENGINE & BANKS
# ==============================================================================
WORD_DEFINITIONS = {
    "brain": "Cérebro — Órgão central do sistema nervoso responsável pelo pensamento e memória.",
    "increased": "Aumentou, elevado — Que se tornou maior em quantidade ou intensidade.",
    "efficiency": "Eficiência — Capacidade de produzir com o mínimo de desperdício.",
    "improved": "Melhorou, aprimorado — Que passou a ter melhor qualidade.",
    "storage": "Armazenamento — Ato ou espaço destinado a guardar recursos ou energia.",
    "communities": "Comunidades — Grupos de pessoas compartilhando espaço ou interesses.",
    "rely": "Depender, confiar — Depositar confiança ou depender de algo (rely on).",
    "even": "Até mesmo, inclusive — Usado para enfatizar algo surpreendente.",
    "not": "Não — Palavra de negação.",
    "shining": "Brilhando, reluzente — Emitindo ou refletindo luz.",
    "advanced": "Avançado, de ponta — Muito desenvolvido ou sofisticado.",
    "safety": "Segurança — Proteção contra riscos, perigos ou acidentes.",
    "commutes": "Trajetos, deslocamentos — Deslocamentos diários de ida e volta.",
    "fleets": "Frotas — Conjunto organizado de veículos operando juntos.",
    "valuable": "Valioso, de grande valor — De grande importância ou utilidade.",
    "spaces": "Espaços, vagas — Áreas livres e disponíveis para ocupação.",
    "deep": "Profundo — De grande extensão para baixo ou interior.",
    "cleanses": "Limpa, purifica — Remove impurezas ou resíduos.",
    "metabolic": "Metabólico — Relativo às reações químicas do organismo.",
    "products": "Produtos, substâncias resultantes — Resultados de processos biológicos.",
    "accumulate": "Acumular — Juntar ou reunir gradualmente.",
    "waking": "Vigília — Estado de estar acordado.",
    "memory": "Memória — Capacidade do cérebro de armazenar informações.",
    "critical": "Crítico, crucial — De importância decisiva ou vital.",
    "individuals": "Indivíduos — Pessoas consideradas individualmente.",
    "suffer": "Sofrer — Passar por dor, perda ou dificuldades.",
    "slow": "Lento — De baixa velocidade ou reação demorada.",
    "panel": "Painel — Estrutura fotovoltaica que capta luz solar.",
    "systems": "Sistemas — Conjuntos interconectados de elementos.",
    "enable": "Capacitar, viabilizar — Tornar algo possível.",
    "modern": "Moderno — Relativo à época atual; inovador.",
    "solar": "Solar — Relativo ao Sol ou à sua energia.",
    "sun": "Sol — A estrela central do sistema solar.",
    "algorithms": "Algoritmos — Sequências lógicas de instruções computacionais.",
    "analyze": "Analisar — Examinar minuciosamente dados ou fatos.",
    "images": "Imagens — Representações visuais.",
    "precision": "Precisão — Exatidão ou rigor metodológico.",
    "anomalies": "Anomalias — Desvios do que é normal ou esperado.",
    "doctors": "Médicos — Profissionais de saúde clínica.",
    "physicians": "Médicos especialistas — Doutores em prática médica.",
    "outcomes": "Resultados, desfechos — Consequências finais de um tratamento ou ação.",
    "vehicles": "Veículos — Meios de transporte motorizados.",
    "traffic": "Tráfego, trânsito — Movimentação de veículos e pedestres.",
    "pollution": "Poluição — Degradação ambiental por contaminantes.",
    "solution": "Solução — Resposta eficaz para resolver um problema.",
    "residents": "Moradores, residentes — Pessoas que habitam uma determinada área."
}

def get_word_definition(word, context=""):
    w_clean = re.sub(r'[^a-zA-Z]', '', word).lower().strip()
    if w_clean in WORD_DEFINITIONS:
        return WORD_DEFINITIONS[w_clean]
    try:
        api_key = get_gemini_key()
        if api_key:
            prompt = (
                f"Defina a palavra em inglês '{word}' (contexto da frase: '{context}'). "
                "Responda em UMA única linha em português no formato: "
                "'Tradução — Breve explicação prática (máximo 12 palavras)'."
            )
            raw = call_gemini(prompt)
            if raw and not raw.startswith("[Erro"):
                clean = raw.strip().replace("\n", " ")
                WORD_DEFINITIONS[w_clean] = clean
                return clean
    except Exception:
        pass
    return f"Termo acadêmico em inglês: {word}"

WORD_RATIONALES = {
    "brain": "<b>Pista Gramatical e Semântica:</b> A frase exige o sujeito que realiza a ação de limpeza metabólica (<i>cleanses metabolic waste</i>) durante o sono profundo. O contexto neurológico e o prefixo <i>bra-</i> apontam diretamente para <b>brain</b> (cérebro).",
    "increased": "<b>Pista Sintática (Present Perfect):</b> A estrutura <i>have significantly [verbo]</i> exige o particípio passado. O avanço tecnológico gera a elevação da capacidade dos painéis, logo o particípio é <b>increased</b>.",
    "efficiency": "<b>Pista de Colocação Técnica:</b> Em engenharia solar, o termo padrão pós-<i>panel</i> é <b>panel efficiency</b> (eficiência do painel). O sufixo nominal abstrato <i>-cy</i> fecha a palavra.",
    "improved": "<b>Pista de Particípio Adjetival:</b> Antes do substantivo <i>energy storage systems</i>, é necessário um adjetivo descritivo para sistemas modernos. O particípio <b>improved</b> (aprimorados/melhorados) qualifica a evolução técnica.",
    "storage": "<b>Pista de Colocação Fixa:</b> A expressão técnica universal para guardar energia em baterias é <b>energy storage</b> (armazenamento de energia). O sufixo <i>-age</i> deriva o substantivo de <i>store</i>.",
    "communities": "<b>Pista Sintática do Verbo Enable:</b> A regência é <i>enable [entidade] to [ação]</i>. A palavra iniciada por <i>commu-</i> no plural que representa grupos de pessoas/populações é <b>communities</b> (comunidades).",
    "rely": "<b>Pista de Preposição Regente (Collocation):</b> A preposição seguinte <b>on</b> é a chave: o verbo com prefixo <i>re-</i> que significa \"depender de / confiar em\" regido por <i>on</i> é exclusivamente <b>rely</b> (<i>rely on</i>).",
    "even": "<b>Pista de Conjunção Concessiva:</b> Para introduzir um cenário surpreendente ou adverso (funcionar até na ausência de sol), a língua inglesa utiliza a locução enfática <b>even when</b> (mesmo quando / até mesmo quando).",
    "not": "<b>Pista Gramatical de Negação:</b> Na oração contínua <i>is ... shining</i>, o advérbio que se interpõe entre o verbo auxiliar <i>is</i> e o gerúndio para formar a negação é a partícula <b>not</b>.",
    "shining": "<b>Pista Semântica e Sintática:</b> O sujeito é <i>the sun</i> (o sol). O verbo característico da ação do sol em tempo contínuo (<i>is not ...</i>) é <b>shining</b> (brilhando).",
    "advanced": "<b>Pista de Colocação Tecnológica:</b> Antes do substantivo <i>sensors</i> (sensores), busca-se um adjetivo de alta tecnologia. O termo acadêmico consagrado em robótica e IA é <b>advanced sensors</b> (sensores avançados).",
    "safety": "<b>Pista de Substantivo Composto:</b> O termo fixo internacional para segurança viária e no trânsito é <b>road safety</b>, que complementa o verbo <i>increase</i> (aumentar a segurança nas pistas).",
    "commutes": "<b>Pista Semântica de Mobilidade Urbana:</b> Após o adjetivo <i>daily</i> (diários), o substantivo que designa o trajeto rotineiro de ida e volta ao trabalho/estudo é <b>commutes</b> (deslocamentos rotineiros).",
    "fleets": "<b>Pista de Substantivo Coletivo:</b> O termo coletivo padrão em inglês para um conjunto operacional de veículos (<i>of autonomous cars</i>) é <b>fleets</b> (frotas).",
    "valuable": "<b>Pista de Adjetivo Qualificativo:</b> Antes de <i>urban spaces</i> (espaços urbanos antes ocupados por vagas de carro), o adjetivo que expressa o alto valor e utilidade pública recuperada é <b>valuable</b> (valiosos).",
    "spaces": "<b>Pista de Urbanismo:</b> A expressão consagrada em planejamento urbano para designar áreas públicas de convivência é <b>urban spaces</b> (espaços urbanos)."
}

def get_word_rationale(word, full_sentence="", topic=""):
    w_clean = re.sub(r'[^a-zA-Z]', '', word).lower().strip()
    if w_clean in WORD_RATIONALES:
        return WORD_RATIONALES[w_clean]
    try:
        api_key = get_gemini_key()
        if api_key:
            prompt = (
                f"Para a palavra em inglês '{word}' inserida na frase '{full_sentence}' (tópico: {topic}), "
                "explique em 1-2 frases concisas em português COMO DEDUZIR essa palavra no teste C-Test: "
                "aponte a pista gramatical (tempo verbal/sintaxe), a regência/collocation (preposição que acompanha) "
                "ou a lógica contextual. Retorne APENAS o texto explicativo direto."
            )
            raw = call_gemini(prompt)
            if raw and not raw.startswith("[Erro"):
                clean = raw.strip().replace("\n", " ")
                WORD_RATIONALES[w_clean] = clean
                return clean
    except Exception:
        pass
    return f"Pista contextual: Palavra de alta frequência acadêmica associada ao tema '{topic}'."
C_TEST_BANK = [
    {
        "title": "Sleep and Cognitive Function",
        "intro": "Adequate sleep is essential for mental health and brain plasticity.",
        "tokens": [
            ("During", None, ""), ("de", "ep", ""), ("sleep,", None, ""), ("the", None, ""),
            ("bra", "in", ""), ("cleanses", None, ""), ("metab", "olic", ""), ("waste", None, ""),
            ("prod", "ucts", ""), ("that", None, ""), ("accum", "ulate", ""), ("dur", "ing", ""),
            ("wak", "ing", ""), ("hours.", None, ""), ("Mem", "ory", ""), ("consolidation", None, ""),
            ("al", "so", ""), ("occurs", None, ""), ("dur", "ing", ""), ("this", None, ""),
            ("crit", "ical", ""), ("period.", None, ""), ("With", "out", ""), ("enough", None, ""),
            ("qual", "ity", ""), ("rest,", None, ""), ("individ", "uals", ""), ("may", None, ""),
            ("suff", "er", ""), ("from", None, ""), ("decre", "ased", ""), ("focus", None, ""),
            ("and", None, ""), ("sl", "ow", ""), ("reaction", None, ""), ("tim", "es", ".")
        ]
    },
    {
        "title": "Renewable Energy and Innovation",
        "intro": "Solar power has become one of the cheapest sources of electricity worldwide.",
        "tokens": [
            ("Recent", None, ""), ("adva", "nces", ""), ("in", None, ""), ("photovolta", "ic", ""),
            ("technology", None, ""), ("ha", "ve", ""), ("significantly", None, ""), ("incre", "ased", ""),
            ("panel", None, ""), ("efficie", "ncy", "."), ("Furthermore,", None, ""), ("impr", "oved", ""),
            ("energy", None, ""), ("stor", "age", ""), ("systems", None, ""), ("enab", "le", ""),
            ("modern", None, ""), ("commu", "nities", ""), ("to", None, ""), ("re", "ly", ""),
            ("on", None, ""), ("so", "lar", ""), ("power", None, ""), ("ev", "en", ""),
            ("when", None, ""), ("the", None, ""), ("s", "un", ""), ("is", None, ""),
            ("n", "ot", ""), ("shin", "ing", ".")
        ]
    },
    {
        "title": "Artificial Intelligence in Healthcare",
        "intro": "Machine learning is revolutionizing diagnostics in clinical medicine.",
        "tokens": [
            ("Algorithms", None, ""), ("can", None, ""), ("anal", "yze", ""), ("medical", None, ""),
            ("imag", "es", ""), ("with", None, ""), ("remark", "able", ""), ("precision,", None, ""),
            ("oft", "en", ""), ("detecting", None, ""), ("anomal", "ies", ""), ("faster", None, ""),
            ("th", "an", ""), ("human", None, ""), ("doct", "ors", "."), ("This", None, ""),
            ("techn", "ology", ""), ("assists", None, ""), ("physic", "ians", ""), ("in", None, ""),
            ("mak", "ing", ""), ("more", None, ""), ("accur", "ate", ""), ("decisions,", None, ""),
            ("ther", "eby", ""), ("reducing", None, ""), ("diagn", "ostic", ""), ("errors", None, ""),
            ("and", None, ""), ("impro", "ving", ""), ("patient", None, ""), ("outco", "mes", ".")
        ]
    },
    {
        "title": "Urbanization and Sustainable Cities",
        "intro": "Cities around the globe are reconsidering their transportation infrastructure.",
        "tokens": [
            ("Heavy", None, ""), ("depen", "dence", ""), ("on", None, ""), ("priv", "ate", ""),
            ("vehicles", None, ""), ("cau", "ses", ""), ("severe", None, ""), ("traf", "fic", ""),
            ("congestion", None, ""), ("a", "nd", ""), ("air", None, ""), ("pollut", "ion", "."),
            ("Investing", None, ""), ("i", "n", ""), ("modern", None, ""), ("elec", "tric", ""),
            ("buses", None, ""), ("an", "d", ""), ("subways", None, ""), ("prov", "ides", ""),
            ("a", None, ""), ("sustain", "able", ""), ("solution", None, ""), ("th", "at", ""),
            ("improves", None, ""), ("qual", "ity", ""), ("of", None, ""), ("li", "fe", ""),
            ("for", None, ""), ("resid", "ents", ".")
        ]
    }
]

C_TEST_AI_TOPICS = [
    "Cognitive Neuroscience & Memory Consolidation",
    "Marine Biology & Coral Bleaching Mechanisms",
    "Quantum Computing & Post-Quantum Cryptography",
    "Autonomous Mobility & Urban Infrastructure",
    "Global Macroeconomics, Supply Chains & Inflation",
    "Genetics, CRISPR Cas9 & Precision Medicine",
    "Astrophysics, Gravitational Waves & Black Holes",
    "Renewable Energy & Solid-State Battery Chemistry",
    "Evolutionary Linguistics & Child Language Acquisition",
    "Robotics, Biomimicry & Swarm Intelligence",
    "Microbiology & Global Antimicrobial Resistance",
    "Biophilic Architecture & Sustainable Urban Planning",
    "Deep-Sea Oceanography & Abyssal Ecosystems",
    "Behavioral Economics, Heuristics & Decision Biases",
    "Nanotechnology & Targeted Cancer Therapeutics",
    "Paleoclimatology & Polar Ice Core Records",
    "Artificial Neural Networks & Transformer Architectures",
    "Volcanology & Plate Tectonic Subduction Zones",
    "Bioarchaeology & Human Evolutionary Migrations",
    "Space Exploration, Planetary Geology & Mars Colonization",
    "Photosynthesis Efficiency & Agricultural Biotechnology",
    "Neuroplasticity & Lifelong Cognitive Resilience",
    "Atmospheric Science & Extreme Meteorological Patterns",
    "Cybersecurity, Zero-Trust Architecture & Data Sovereignty",
    "Cellular Senescence & the Biology of Aging"
]

def text_to_c_test_tokens(passage_text, target_blanks=11):
    """Converts a standard academic passage into mathematically exact DET C-Test tokens."""
    raw_tokens = re.findall(r"([A-Za-z0-9'\-]+)([^A-Za-z0-9'\-]*)", passage_text)
    skip_words = {
        'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'but',
        'is', 'are', 'was', 'were', 'it', 'its', 'as', 'by', 'if', 'be', 'so',
        'with', 'from', 'that', 'this', 'into', 'than', 'such', 'not', 'no'
    }
    tokens = []
    blank_count = 0
    candidate_idx = 0

    for word, punct in raw_tokens:
        clean_word = word.strip()
        if not clean_word:
            continue
        is_candidate = (
            len(clean_word) >= 4 and 
            clean_word.lower() not in skip_words and 
            clean_word.isalpha()
        )
        # DET Rule: Truncate second half of every second content word
        if is_candidate and (candidate_idx % 2 == 1) and blank_count < target_blanks:
            split_idx = (len(clean_word) + 1) // 2
            prefix = clean_word[:split_idx]
            missing = clean_word[split_idx:]
            tokens.append((prefix, missing, punct.rstrip()))
            blank_count += 1
        else:
            tokens.append((clean_word, None, punct.rstrip()))

        if is_candidate:
            candidate_idx += 1

    return tokens, blank_count

def save_c_test_to_archive(test_obj):
    """Saves generated tests into an offline archive pool."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        archive = []
        if os.path.exists(C_TEST_ARCHIVE_FILE):
            with open(C_TEST_ARCHIVE_FILE, "r") as f:
                archive = json.load(f)
        if not any(item.get("title") == test_obj.get("title") for item in archive):
            serializable_test = {
                "title": test_obj["title"],
                "intro": test_obj["intro"],
                "tokens": [[p, m, pt] for p, m, pt in test_obj["tokens"]],
                "clues": test_obj.get("clues", {})
            }
            archive.append(serializable_test)
            with open(C_TEST_ARCHIVE_FILE, "w") as f:
                json.dump(archive, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_unseen_c_test_from_archive():
    """Returns an unseen AI-generated C-Test from local archive if available (0ms latency, 0 API cost)."""
    if os.path.exists(C_TEST_ARCHIVE_FILE):
        try:
            with open(C_TEST_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    unseen = [item for item in archived if "tokens" in item and len(item["tokens"]) >= 8 and not is_item_seen("c_test", item)]
                    if unseen:
                        return random.choice(unseen)
        except Exception:
            pass
    return None

def get_random_c_test_from_pool():
    """Returns a random test combining the built-in bank and the AI archive (prioritizing unseen)."""
    unseen = get_unseen_c_test_from_archive()
    if unseen:
        return unseen
    pool = list(C_TEST_BANK)
    if os.path.exists(C_TEST_ARCHIVE_FILE):
        try:
            with open(C_TEST_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    for item in archived:
                        if "tokens" in item and len(item["tokens"]) >= 8:
                            pool.append(item)
        except Exception:
            pass
    unseen_pool = [item for item in pool if not is_item_seen("c_test", item)]
    return random.choice(unseen_pool) if unseen_pool else random.choice(pool)

def generate_dynamic_c_test_ai():
    """Uses Gemini in native JSON mode to compose a fresh scientific C-Test in ONE single prompt."""
    topic = random.choice(C_TEST_AI_TOPICS)
    weak_hint = get_weak_words_hint(3)
    prompt = (
        f"Generate a Duolingo English Test (DET) C-Test (Read and Complete) passage about '{topic}'.{weak_hint}\n\n"
        "Passage requirements:\n"
        "1. Academic level: CEFR B2/C1, formal scholarly English.\n"
        "2. Structure:\n"
        "   - 'title': Concise engaging academic title.\n"
        "   - 'intro': Exactly ONE complete, undamaged opening sentence providing clear context (14-20 words).\n"
        "   - 'body': Exactly 2 to 3 cohesive academic sentences continuing the topic (50-65 words). Write standard unbroken English sentences.\n"
        "   - 'clues': A dictionary mapping the key academic words used in 'body' to: 'Significado conciso em português (máx 8 palavras) | Dica de dedução gramatical ou de contexto'.\n\n"
        "Respond ONLY with valid JSON in this exact structure:\n"
        "{\n"
        '  "title": "Title Here",\n'
        '  "intro": "Complete introductory sentence here.",\n'
        '  "body": "Two or three sentences of natural academic English here.",\n'
        '  "clues": {\n'
        '    "word1": "Tradução concisa | Dica sintática ou contextual",\n'
        '    "word2": "Tradução concisa | Dica sintática ou contextual"\n'
        '  }\n'
        "}"
    )
    raw = call_gemini(prompt, json_mode=True, max_tokens=750)
    if raw:
        try:
            cleaned = re.search(r"\{.*\}", raw, re.DOTALL)
            if cleaned:
                data = json.loads(cleaned.group(0))
                if "body" in data and isinstance(data["body"], str) and len(data["body"]) > 30:
                    tokens, blank_count = text_to_c_test_tokens(data["body"])
                    if blank_count >= 8:
                        test_obj = {
                            "title": data.get("title", topic),
                            "intro": data.get("intro", ""),
                            "tokens": tokens,
                            "clues": data.get("clues", {})
                        }
                        save_c_test_to_archive(test_obj)
                        return test_obj
                if "tokens" in data and len(data["tokens"]) >= 8:
                    test_obj = {
                        "title": data.get("title", topic),
                        "intro": data.get("intro", ""),
                        "tokens": data["tokens"],
                        "clues": data.get("clues", {})
                    }
                    save_c_test_to_archive(test_obj)
                    return test_obj
        except Exception:
            pass
    return None

# REAL VS FAKE WORDS BANK
REAL_VS_FAKE_BANK = [
    {"word": "indispensable", "real": True, "def": "Absolutamente essencial ou necessário.", "ex": "Clear data is indispensable for research."},
    {"word": "substantiate", "real": True, "def": "Comprovar com evidências.", "ex": "We need empirical data to substantiate this claim."},
    {"word": "inexorable", "real": True, "def": "Implacável, impossível de impedir.", "ex": "The inexorable rise of global temperatures."},
    {"word": "comprobate", "real": False, "def": "[Palavra falsa criada para soar científica]", "ex": "Não existe em inglês."},
    {"word": "disperious", "real": False, "def": "[Palavra falsa criada para soar formal]", "ex": "Não existe em inglês."},
    {"word": "equivocal", "real": True, "def": "Ambíguo, aberto a interpretações duvidosas.", "ex": "The results remained equivocal."},
    {"word": "precipitous", "real": True, "def": "Muito íngreme ou repentino/precipitado.", "ex": "A precipitous drop in revenue."},
    {"word": "transcendence", "real": True, "def": "Transcendência, superação de limites normais.", "ex": "The artistic transcendence of the author."},
    {"word": "reflocative", "real": False, "def": "[Palavra falsa criada para soar acadêmica]", "ex": "Não existe em inglês."},
    {"word": "obversely", "real": True, "def": "De modo oposto ou inverso.", "ex": "Obversely, higher taxes reduced consumer spending."},
    {"word": "impertuable", "real": False, "def": "[Palavra falsa - a grafia real é imperturbable]", "ex": "Grafia incorreta."},
    {"word": "juxtaposition", "real": True, "def": "Ato de colocar coisas lado a lado para comparar.", "ex": "The juxtaposition of traditional and modern styles."}
]

# LISTEN AND TYPE BANK
LISTEN_TYPE_BANK = [
    {"audio": "The preliminary results corroborated our original hypothesis.", "focus": "corroborated, preliminary", "trans": "Os resultados preliminares corroboraram nossa hipótese original."},
    {"audio": "Furthermore, the committee decided to postpone the final examination.", "focus": "furthermore, postpone", "trans": "Além disso, o comitê decidiu adiar o exame final."},
    {"audio": "Technological innovation plays a pivotal role in sustainable economic growth.", "focus": "pivotal, innovation", "trans": "A inovação tecnológica desempenha um papel fundamental no crescimento econômico sustentável."},
    {"audio": "The researchers struggled to isolate the independent variable in the laboratory.", "focus": "isolate, independent variable", "trans": "Os pesquisadores tiveram dificuldades para isolar a variável independente no laboratório."},
    {"audio": "Despite the severe drought, agricultural yields improved significantly this season.", "focus": "drought, yields, significantly", "trans": "Apesar da seca severa, a produção agrícola melhorou significativamente nesta temporada."}
]

# INTERACTIVE READING BANK
INTERACTIVE_READING_BANK = [
    {
        "title": "Ecological Restoration",
        "passage_pre": "Rewilding is an ecological conservation method aimed at restoring natural processes and wilderness areas.",
        "question": "Qual frase melhor completa o argumento seguinte de forma coesa?",
        "options": [
            "Consequently, it usually involves reintroducing apex predators and native herbivores to the ecosystem.",
            "Despite this, sports cars continue to be popular in European urban centers.",
            "Instead, historians prefer to study written documents rather than biology.",
            "For example, baking bread requires yeast and warm temperature."
        ],
        "answer": 0,
        "explanation": "A opção 1 desenvolve o argumento sobre restauração ecológica ('apex predators and native herbivores')."
    },
    {
        "title": "Deep Learning Architectures",
        "passage_pre": "Neural networks require massive amounts of annotated data to achieve high classification accuracy.",
        "question": "Qual opção expressa uma limitação contrastante adequada (Transição Acadêmica)?",
        "options": [
            "Therefore, everyone buys smartphones every year.",
            "However, obtaining high-quality labeled data remains extremely time-consuming and expensive.",
            "Furthermore, neural networks do not use any computational power.",
            "Similarly, ancient Greek philosophers enjoyed debates."
        ],
        "answer": 1,
        "explanation": "'However' introduz o contraste exato sobre o alto custo e dificuldade de rotular dados."
    },
    {
        "title": "Epigenetics and Gene Regulation",
        "passage_pre": "Epigenetic modifications influence gene expression without altering the underlying DNA sequence. Environmental factors such as chronic stress, nutritional deficits, and toxin exposure can trigger biochemical tags on chromatin.",
        "question": "Qual frase conclui a explicação de forma científica e coesa?",
        "options": [
            "As a result, identical twins can exhibit divergent disease susceptibilities over time despite sharing the same genome.",
            "Nevertheless, acoustic instruments sound better in concert halls with high ceilings.",
            "On the contrary, cellular respiration has no relationship to biological metabolism.",
            "In conclusion, modern smartphones rely on lithium-ion batteries for everyday operations."
        ],
        "answer": 0,
        "explanation": "A opção conecta a influência ambiental na expressão genética à divergência clínica observada em gêmeos monozigóticos."
    },
    {
        "title": "Urban Heat Islands",
        "passage_pre": "Metropolitan areas with dense concrete infrastructure absorb solar radiation and trap thermal energy, elevating local temperatures significantly above rural baselines. Municipal planners are experimenting with reflective building surfaces and extensive green corridors.",
        "question": "Qual frase estabelece o resultado esperado dessa intervenção urbana?",
        "options": [
            "Consequently, these architectural interventions reduce cooling demand and mitigate localized heat stress.",
            "In spite of this, solar panels are strictly prohibited on modern commercial rooftops.",
            "Hence, classical literature remains a mandatory prerequisite for engineering students.",
            "Otherwise, underwater acoustic communication continues to face attenuation issues."
        ],
        "answer": 0,
        "explanation": "'Consequently' liga a implementação de superfícies reflexivas e corredores verdes à redução do calor urbano e da demanda de energia."
    },
    {
        "title": "Behavioral Economics and Decision Making",
        "passage_pre": "Classical economic theory assumes that market participants are rational agents who consistently optimize utility based on perfect information. However, empirical findings in behavioral economics reveal systematic cognitive biases that distort financial judgments.",
        "question": "Qual frase ilustra adequadamente a aplicação prática dessa descoberta?",
        "options": [
            "Because of this, all physical banks have ceased providing credit cards to retail customers.",
            "Accordingly, policymakers increasingly deploy subtle nudges and default enrollments to foster better retirement savings.",
            "Moreover, agricultural irrigation has expanded rapidly across arid valleys.",
            "Nevertheless, computer hardware manufacturers continue to shrink transistor gate dimensions."
        ],
        "answer": 1,
        "explanation": "'Accordingly' introduz a resposta prática dos formuladores de políticas (nudges / opções padrão) para contornar vieses cognitivos na poupança."
    },
    {
        "title": "Renewable Energy Grid Integration",
        "passage_pre": "While wind and solar power generation have expanded exponentially, their intermittent output poses severe challenges for transmission grid stability. Without large-scale utility storage, sudden drops in weather-dependent generation require rapid backup from carbon-intensive peaker plants.",
        "question": "Qual frase aponta a solução tecnológica necessária com coesão acadêmica?",
        "options": [
            "Therefore, developing long-duration flow batteries and grid-scale storage is critical to ensure uninterruptible power delivery.",
            "In addition, ocean currents are primarily driven by thermohaline circulation mechanisms.",
            "Conversely, fossil fuel reserves are infinite and do not affect greenhouse gas concentrations.",
            "For instance, classical pianists practice polyrhythms to build motor independence."
        ],
        "answer": 0,
        "explanation": "'Therefore' articula a necessidade imperativa de baterias de longa duração para resolver o gargalo da intermitência nas redes elétricas."
    }
]

INTERACTIVE_READING_AI_TOPICS = [
    "Neuroplasticity & Habit Formation",
    "Deep-Sea Hydrothermal Ecosystems",
    "Generative AI & Algorithmic Transparency",
    "Urban Heat Islands & Microclimate Engineering",
    "Linguistic Drift & Dialect Evolution",
    "Renewable Energy Storage & Flow Batteries",
    "Epigenetics & Environmental Gene Expression",
    "Behavioral Economics & Choice Architecture",
    "CRISPR Technology & Ethical Governance",
    "Paleoclimatology & Ice Sheet Dynamics",
    "Antimicrobial Resistance & Bacteriophage Therapy",
    "Microplastics in Marine Food Chains",
    "Post-Quantum Cryptography & Security Protocols",
    "Cognitive Biases in Public Policy Decision-Making",
    "Biodiversity Loss & Pollinator Conservation",
    "Space Exploration & Exoplanet Habitability",
    "Sociolinguistics & Digital Code-Switching",
    "Materials Science & Nanotechnology in Medicine",
    "Supply Chain Fragility & Semiconductor Fabrication",
    "Sleep Architecture & Cognitive Memory Consolidation"
]

# PROMPTS
WRITING_PROMPTS = [
    "Some educators argue that graduate programs should focus entirely on practical skills rather than theoretical academic knowledge. Do you agree or disagree? Provide reasons and examples to support your position.",
    "Advances in artificial intelligence and automation are changing the modern workplace. In your opinion, what is the most significant challenge or opportunity this presents for young researchers?",
    "Many universities now offer fully remote or hybrid degrees. Do the benefits of online education outweigh the disadvantages of losing in-person campus interaction? Explain your viewpoint.",
    "Environmental protection often clashes with rapid economic development. How can developing nations strike an effective balance between industrial growth and ecological preservation?",
    "Describe an obstacle or challenge you faced in your academic or professional journey. How did you overcome it, and what valuable lessons did you learn?"
]

SPEAKING_PROMPTS = [
    "Talk about a teacher, professor, or mentor who had a lasting impact on your life. Describe who they are, what they taught you, and why their guidance was important.",
    "Describe a book, article, or documentary that changed how you view a particular topic. Explain what it was about and why it impressed you.",
    "Some people prefer working in a collaborative team, while others prefer working independently. Which style fits you better and why?",
    "If you could conduct research on any scientific or social topic in your master's program without budget restrictions, what would it be and why?"
]

VOCAB_DRILL = [
    {
        "word": "Furthermore",
        "type": "Connector / Transition",
        "question": "Choose the best synonym for 'Furthermore' in an academic argument:",
        "options": ["Nevertheless", "In addition", "Instead", "Consequently"],
        "answer": 1,
        "explanation": "'Furthermore' and 'In addition' are additive transition words used to strengthen a point."
    },
    {
        "word": "Consequently",
        "type": "Connector / Transition",
        "question": "Which sentence uses 'Consequently' correctly?",
        "options": [
            "He missed the deadline; consequently, he could not submit his thesis.",
            "Consequently he was tired, he decided to run a marathon.",
            "The experiment failed, consequently it was a sunny day.",
            "She studied thoroughly consequently she forgot the formulas."
        ],
        "answer": 0,
        "explanation": "'Consequently' indicates a cause-and-effect relationship (as a result)."
    },
    {
        "word": "Feasible",
        "type": "Academic Adjective",
        "question": "What is the closest meaning of 'Feasible' in a research proposal context?",
        "options": ["Impossible", "Viable / Practical", "Theoretical only", "Outdated"],
        "answer": 1,
        "explanation": "'Feasible' means capable of being done or carried out successfully."
    },
    {
        "word": "Substantial",
        "type": "Academic Adjective",
        "question": "'The study demonstrated a substantial increase in memory retention.' 'Substantial' means:",
        "options": ["Minimal", "Considerable / Significant", "Unlikely", "Temporary"],
        "answer": 1,
        "explanation": "'Substantial' means of considerable importance, size, or worth."
    },
    {
        "word": "Despite",
        "type": "Connector / Contrast",
        "question": "Which structure correctly follows 'Despite'?",
        "options": [
            "Despite of the difficulties, we succeeded.",
            "Despite the difficulties, we succeeded.",
            "Despite that we succeeded, it was difficult.",
            "Despite although it was hard, we passed."
        ],
        "answer": 1,
        "explanation": "'Despite' takes a noun phrase directly (never 'despite of')."
    }
]

ACADEMIC_CONNECTORS = [
    "furthermore", "moreover", "in addition", "additionally",
    "however", "nevertheless", "nonetheless", "on the other hand",
    "consequently", "therefore", "thus", "as a result",
    "in contrast", "conversely", "despite", "although",
    "specifically", "for instance", "for example", "ultimately", "significant", "crucial"
]

# ==============================================================================
# UI HELPERS
# ==============================================================================
def clear():
    os.system("cls" if IS_WINDOWS else "clear")

def header():
    clear()
    stats = load_stats()
    streak = stats.get("streak", 0)
    pending = len(load_pending_cards())
    anki_status = f"{GREEN}🟢 Conectado{RESET}" if is_anki_online() else f"{YELLOW}🟡 Buffer ({pending} pendentes){RESET}"
    gemini_key = get_gemini_key()
    ai_status = f"{GREEN}🟢 Gemini Pro Ativo{RESET}" if gemini_key else f"{DIM}⚪ IA Desconectada{RESET}"

    print(f"{CYAN}{BOLD}==============================================================================={RESET}")
    print(f"{CYAN}{BOLD}               DET DRILL PRO - DUOLINGO ENGLISH TEST SUITE                    {RESET}")
    print(f"{CYAN}{BOLD}==============================================================================={RESET}")
    print(f" {YELLOW}🔥 Streak: {streak} dia(s){RESET} | Anki: {anki_status} | IA: {ai_status}")
    print(f" {MAGENTA}Meta UFRJ: 95-105+ pts (B2/C1){RESET} | {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{DIM}-------------------------------------------------------------------------------{RESET}")

# ==============================================================================
# 1. READ & COMPLETE (C-TEST)
# ==============================================================================
def render_c_test_text(tokens, current_blank_idx, answered, show_solutions=False):
    words_output = []
    blank_counter = 0

    for prefix, missing, punct in tokens:
        if missing is None:
            words_output.append(prefix + punct)
        else:
            needed_len = len(missing)
            underscores = "_" * needed_len
            if blank_counter in answered:
                user_val, is_correct = answered[blank_counter]
                if show_solutions:
                    if is_correct:
                        rendered = f"{GREEN}{BOLD}{prefix}{missing}{RESET}{punct}"
                    else:
                        rendered = f"{RED}{BOLD}{prefix}[{user_val}]{RESET}{DIM}({prefix}{missing}){RESET}{punct}"
                else:
                    # While test is still active, show the candidate's typed letters neutrally (or highlighted if selected)
                    if blank_counter == current_blank_idx:
                        rendered = f"{BG_YELLOW}{BOLD}{prefix}{user_val}{RESET}{punct}"
                    else:
                        rendered = f"{GREEN}{BOLD}{prefix}{user_val}{RESET}{punct}"
            elif show_solutions:
                rendered = f"{RED}{BOLD}{prefix}[___]{RESET}{DIM}({prefix}{missing}){RESET}{punct}"
            elif blank_counter == current_blank_idx:
                rendered = f"{BG_YELLOW}{BOLD}{prefix}{underscores}{RESET}{punct}"
            else:
                rendered = f"{CYAN}{prefix}{BOLD}{underscores}{RESET}{punct}"
            words_output.append(rendered)
            blank_counter += 1

    return " ".join(words_output)

def run_c_test(force_ai=True):
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 1: READ & COMPLETE (C-TEST / FILL IN THE BLANKS)]{RESET}")
    print(f"• Cada traço corresponde a {BOLD}EXATAMENTE UMA LETRA{RESET} faltante.")
    print(f"• Navegação livre: digite {BOLD}>{RESET} para pular, {BOLD}<{RESET} para voltar, {BOLD}?{RESET} para pista, ou {BOLD}FIM{RESET} para entregar.")
    print("• Tempo oficial de prova: 3 minutos.\n")

    test = None
    if force_ai:
        test = get_unseen_c_test_from_archive()
        if test:
            print(f"{GREEN}⚡ Texto inédito carregado do buffer local instantaneamente (0ms / 0 requisição)!{RESET}\n")
        elif get_gemini_key():
            print(f"{CYAN}🤖 Solicitando à IA (Gemini) um texto acadêmico inédito...{RESET}")
            test = generate_dynamic_c_test_ai()
            if test:
                print(f"{GREEN}✓ Novo texto gerado pela IA com sucesso!{RESET}\n")
            else:
                print(f"{YELLOW}⚠️ Não foi possível gerar via IA no momento. Carregando do banco...{RESET}\n")
        else:
            print(f"{YELLOW}⚠️ Chave do Gemini não configurada. Usando texto do banco...{RESET}\n")

    if not test:
        test = get_random_c_test_from_pool()

    mark_item_seen("c_test", test)

    tokens = test["tokens"]
    blank_tokens = [(t_idx, p, m, pt) for t_idx, (p, m, pt) in enumerate(tokens) if m is not None]
    total_blanks = len(blank_tokens)
    test_clues = test.get("clues", {})

    print(f"{CYAN}Tópico:{RESET} {BOLD}{test['title']}{RESET}")
    print(f"{DIM}{test['intro']}{RESET}\n")

    input(f"{GREEN}Pressione [ENTER] para iniciar o cronômetro de 3 minutos...{RESET}")
    start_time = time.time()
    answered = {}
    b_idx = 0
    time_expired = False

    while True:
        elapsed = int(time.time() - start_time)
        remaining = max(0, 180 - elapsed)
        if remaining <= 0:
            time_expired = True
            break

        mins, secs = divmod(remaining, 60)
        time_color = RED if remaining < 30 else (YELLOW if remaining < 60 else GREEN)

        target_t_idx, prefix, missing, punct = blank_tokens[b_idx]
        needed_len = len(missing)
        exact_underscores = "_" * needed_len
        full_word = prefix + missing

        header()
        print(f"\n{BOLD}C-TEST: {test['title']}{RESET} | Tempo Restante: {time_color}{BOLD}{mins:02d}:{secs:02d}{RESET} | Respondidas: {len(answered)}/{total_blanks}")
        print(f"{DIM}{test['intro']}{RESET}\n")
        print(render_c_test_text(tokens, b_idx, answered, show_solutions=False))
        print(f"\n{DIM}" + "-" * 75 + f"{RESET}")

        current_ans_str = f" (Atual: {GREEN}{answered[b_idx][0]}{RESET})" if b_idx in answered else ""
        print(f"Lacuna [{b_idx + 1}/{total_blanks}]: {BOLD}{CYAN}{prefix}{exact_underscores}{RESET}{current_ans_str} | Faltam: {YELLOW}{BOLD}{needed_len} letra(s){RESET}")
        print(f"{DIM}Comandos: [>] Pular | [<] Voltar | [?] Pista morfológica | [FIM] Entregar prova{RESET}")

        try:
            ans = input(f"Sua resposta ({needed_len} letras): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExercício cancelado.")
            return

        if int(time.time() - start_time) >= 180:
            time_expired = True
            break

        if not ans or ans in [">", "p", "tab"]:
            b_idx = (b_idx + 1) % total_blanks
            continue
        elif ans in ["<", "v"]:
            b_idx = (b_idx - 1) % total_blanks
            continue
        elif ans.upper() == "FIM":
            break
        elif ans == "?":
            w_clean = re.sub(r'[^a-zA-Z]', '', full_word).lower().strip()
            raw_clue = test_clues.get(w_clean) or test_clues.get(full_word) or WORD_DEFINITIONS.get(w_clean, "")
            meaning_hint = raw_clue.split(" | ")[0] if raw_clue else "Termo contextual acadêmico"
            print(f"\n{YELLOW}💡 PISTA:{RESET} Termina com a letra '{BOLD}{missing[-1]}{RESET}' | Sentido: {CYAN}{meaning_hint}{RESET}")
            input(f"{DIM}Pressione [ENTER] para tentar...{RESET}")
            continue

        if ans.lower().startswith(prefix.lower()) and len(ans) == len(full_word):
            user_missing = ans[len(prefix):]
        else:
            user_missing = ans

        if len(user_missing) != needed_len:
            print(f"{YELLOW}⚠️  Atenção: a lacuna pede exatamente {needed_len} letra(s) (você digitou {len(user_missing)}).{RESET}")
            confirm = input("Confirmar mesmo assim? [s/N]: ").strip().lower()
            if confirm != "s":
                continue

        is_match = (user_missing.lower() == missing.lower())
        answered[b_idx] = (user_missing, is_match)

        # Auto-advance to next unanswered blank, or finish if all answered
        if len(answered) >= total_blanks:
            header()
            print(f"\n{BOLD}Todas as {total_blanks} lacunas foram preenchidas!{RESET}\n")
            print(render_c_test_text(tokens, -1, answered, show_solutions=False))
            done_q = input(f"\nDeseja entregar e corrigir agora? ([ENTER]=Sim / [<]=Revisar anterior): ").strip()
            if done_q in ["<", "v", "n", "nao"]:
                b_idx = (b_idx - 1) % total_blanks
                continue
            break
        else:
            for offset in range(1, total_blanks + 1):
                cand = (b_idx + offset) % total_blanks
                if cand not in answered:
                    b_idx = cand
                    break

    # Final Grading & Post-processing (100% Local, Zero Extra API Calls)
    correct_count = 0
    mistakes_to_process = []

    for idx_b, (target_t_idx, prefix, missing, punct) in enumerate(blank_tokens):
        needed_len = len(missing)
        full_word = prefix + missing
        if idx_b in answered and answered[idx_b][1]:
            correct_count += 1
        else:
            user_ans = answered[idx_b][0] if idx_b in answered else "___"
            mistakes_to_process.append({
                "target_t_idx": target_t_idx,
                "prefix": prefix,
                "missing": missing,
                "needed_len": needed_len,
                "full_word": full_word,
                "punct": punct,
                "user_ans": user_ans
            })
            record_weak_word(full_word)

    header()
    if time_expired:
        print(f"\n{RED}{BOLD}⏰ TEMPO ESGOTADO (03:00)! Prova encerrada automaticamente.{RESET}")
    print(f"\n{BOLD}C-TEST CONCLUÍDO:{RESET} {test['title']}\n")
    print(render_c_test_text(tokens, -1, answered, show_solutions=True))
    print("\n" + "=" * 65)

    score_pct = (correct_count / total_blanks) * 100
    print(f"{BOLD}Pontuação:{RESET} {correct_count}/{total_blanks} acertos ({score_pct:.1f}%)")

    if mistakes_to_process:
        mistakes_added = 0
        mistake_details = []

        for item in mistakes_to_process:
            full_word = item["full_word"]
            target_t_idx = item["target_t_idx"]
            prefix = item["prefix"]
            missing = item["missing"]
            needed_len = item["needed_len"]
            w_clean = re.sub(r'[^a-zA-Z]', '', full_word).lower().strip()

            raw_clue = test_clues.get(w_clean) or test_clues.get(full_word) or test_clues.get(full_word.lower()) or ""
            if " | " in raw_clue:
                parts = raw_clue.split(" | ", 1)
                defn = parts[0].strip()
                rationale = parts[1].strip()
            elif raw_clue:
                defn = raw_clue.strip()
                rationale = WORD_RATIONALES.get(w_clean, f"Pista sintática/semântica no contexto de '{test['title']}'.")
            else:
                defn = WORD_DEFINITIONS.get(w_clean, "Palavra acadêmica de alta frequência.")
                rationale = WORD_RATIONALES.get(w_clean, f"Pista contextual: Palavra associada ao tema '{test['title']}'.")

            mistake_details.append((full_word, defn, rationale))

            passage_parts = []
            for t_idx, (p, m, pt) in enumerate(tokens):
                if m is None:
                    passage_parts.append(f"{p}{pt}")
                elif t_idx == target_t_idx:
                    blank_html = f"<b style=\"color:#0284c7; background:rgba(2,132,199,0.15); padding:2px 6px; border-radius:4px; border:1px solid rgba(2,132,199,0.4);\">{prefix}{'_' * needed_len}</b>{pt}"
                    passage_parts.append(blank_html)
                else:
                    passage_parts.append(f"{p}{m}{pt}")
            passage_html = " ".join(passage_parts)

            front_context = "<b>[DET: Fill in the Blanks]</b><br>"
            front_context += f"<span style=\"font-size:13px; opacity:0.75;\">Tópico: {test.get('title', 'Fill in the Blanks')}</span><br><br>"
            front_context += "<div style=\"text-align:left; background:rgba(59,130,246,0.08); padding:16px; border-radius:8px; line-height:1.7; font-size:16px; border:1.5px solid rgba(59,130,246,0.25);\">"
            if test.get("intro"):
                front_context += f"<i>{test['intro']}</i><br><br>"
            front_context += f"{passage_html}</div><br>"
            front_context += f"<div style=\"font-size:15px;\">👉 Preencha a lacuna com <b>{needed_len}</b> letras: <b style=\"color:#0284c7; font-size:17px;\">{prefix}{'_' * needed_len}</b></div>"

            back_content = f"<h2 style='color:#10b981; margin-bottom:8px;'>{full_word}</h2>"
            back_content += f"<p style='font-size:16px; margin:8px 0;'><b>Significado:</b> {defn}</p>"
            back_content += f"<p style='font-size:14px; opacity:0.85; margin:4px 0;'><b>Letras da lacuna:</b> <span style='color:#10b981; font-weight:bold;'>{missing}</span></p>"
            back_content += f"<p style='opacity:0.7; font-size:13px; margin:4px 0;'><b>Tópico:</b> {test['title']}</p>"
            back_content += f"""<div style="text-align:left; background:rgba(16,185,129,0.08); border-left:3.5px solid #10b981; padding:12px 16px; border-radius:6px; margin:14px 0; font-size:14.5px; line-height:1.6;">
<div style="font-weight:bold; color:#10b981; margin-bottom:4px; font-size:14px;">💡 Por que essa palavra aqui? (Pista de Dedução)</div>
{rationale}
</div>"""

            push_to_anki(
                subdeck_name="Fill in the Blanks",
                front_html=front_context,
                back_html=back_content,
                tags=["DET", "DET_FillInTheBlanks"],
                audio_text=full_word
            )
            mistakes_added += 1

        print(f"{YELLOW}📥 {mistakes_added} card(s) enfileirados em background para o Anki (0ms)!{RESET}")
        print(f"\n{YELLOW}{BOLD}💡 ANÁLISE PEDAGÓGICA (COMO DEDUZIR OS SEUS ERROS):{RESET}")
        print(f"{DIM}" + "-" * 75 + f"{RESET}")
        for word, defn, rat in mistake_details:
            clean_rat = re.sub(r'<[^>]+>', '', rat)
            print(f"• {CYAN}{BOLD}{word}{RESET} ({defn}): {clean_rat}")
        print(f"{DIM}" + "-" * 75 + f"{RESET}")
    else:
        print(f"{GREEN}🎉 Zero erros! Excelente domínio ortográfico e sintático.{RESET}")

    record_skill_progress(["literacy", "comprehension"], correct_count, total_blanks)
    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 2. READ & SELECT (REAL VS FAKE WORDS — BATCH OF 12 WORDS PER CALL)
# ==============================================================================
def save_read_select_to_archive(words_list):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        archive = []
        if os.path.exists(READ_SELECT_ARCHIVE_FILE):
            with open(READ_SELECT_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive = json.load(f)
        existing_words = {w.get("word", "").lower() for w in archive}
        for w in words_list:
            if w.get("word", "").lower() not in existing_words:
                archive.append(w)
                existing_words.add(w.get("word", "").lower())
        with open(READ_SELECT_ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(archive, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_unseen_read_select_batch(count=6):
    if os.path.exists(READ_SELECT_ARCHIVE_FILE):
        try:
            with open(READ_SELECT_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    unseen = [w for w in archived if "word" in w and not is_item_seen("read_select", w)]
                    if len(unseen) >= count:
                        return random.sample(unseen, count)
        except Exception:
            pass
    return None

def get_random_read_select_pool():
    pool = list(REAL_VS_FAKE_BANK)
    if os.path.exists(READ_SELECT_ARCHIVE_FILE):
        try:
            with open(READ_SELECT_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    pool.extend(archived)
        except Exception:
            pass
    seen = set()
    unique_pool = []
    for item in pool:
        w = item.get("word", "").lower()
        if w and w not in seen:
            seen.add(w)
            unique_pool.append(item)
    return unique_pool

def generate_dynamic_read_select_ai(batch_size=12):
    """Generates a batch of 12 words (6 real B2/C1 + 6 pseudo-words) in ONE API call (serves 2 rounds!)."""
    half = batch_size // 2
    prompt = (
        f"You are an expert test designer for the Duolingo English Test (DET) at CEFR B2/C1 level.\n"
        f"Generate exactly {batch_size} words for the 'Read and Select' task: exactly {half} REAL academic English words and {half} convincing PSEUDO-WORDS "
        "(fake words that follow English morphology/phonotactics and typical affixes like -ive, -ious, -ate, -tion, but do not exist in the dictionary).\n\n"
        f"Respond ONLY with valid JSON array of {batch_size} objects:\n"
        "[\n"
        '  {"word": "mitigate", "real": true, "def": "Atenuar, suavizar ou reduzir a severidade.", "ex": "Policies are needed to mitigate economic risks."},\n'
        '  {"word": "demarcitate", "real": false, "def": "Pseudo-palavra inventada (a forma real é demarcate).", "ex": "Não existe em inglês."}\n'
        "]"
    )
    raw = call_gemini(prompt, json_mode=True, max_tokens=900)
    if raw:
        try:
            cleaned = re.search(r"\[.*\]", raw, re.DOTALL)
            if cleaned:
                data = json.loads(cleaned.group(0))
                if isinstance(data, list) and len(data) >= 6:
                    valid_words = []
                    for item in data:
                        if "word" in item and "real" in item:
                            valid_words.append({
                                "word": str(item["word"]).strip(),
                                "real": bool(item["real"]),
                                "def": str(item.get("def", "")).strip(),
                                "ex": str(item.get("ex", "")).strip()
                            })
                    if len(valid_words) >= 6:
                        save_read_select_to_archive(valid_words)
                        random.shuffle(valid_words)
                        return valid_words[:6]
        except Exception:
            pass
    return None

def run_read_select(force_ai=True):
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 2: READ & SELECT (REAL VS FAKE WORDS)]{RESET}")
    print("• Identifique se a palavra existe legitimamente na língua inglesa.")
    print(f"• Erros são enviados ao Anki em segundo plano com {BOLD}Áudio Nativo .MP3{RESET}.\n")

    sample_words = None
    if force_ai:
        sample_words = get_unseen_read_select_batch(6)
        if sample_words:
            print(f"{GREEN}⚡ 6 palavras inéditas carregadas do lote local (0ms / 0 requisição)!{RESET}\n")
        elif get_gemini_key():
            print(f"{CYAN}🤖 Solicitando à IA (Gemini) um novo lote de palavras acadêmicas inéditas...{RESET}")
            sample_words = generate_dynamic_read_select_ai(12)
            if sample_words:
                print(f"{GREEN}✓ Lote de palavras gerado com sucesso via IA!{RESET}\n")
            else:
                print(f"{YELLOW}⚠️ Não foi possível gerar via IA no momento. Carregando do banco/arquivo...{RESET}\n")
        else:
            print(f"{YELLOW}⚠️ Chave do Gemini não configurada. Usando banco/arquivo...{RESET}\n")

    if not sample_words:
        pool = get_random_read_select_pool()
        sample_words = random.sample(pool, min(6, len(pool)))

    correct = 0
    mistakes = 0

    for idx, item in enumerate(sample_words, 1):
        mark_item_seen("read_select", item)
        word = item["word"]
        print(f"\nPalavra [{idx}/{len(sample_words)}]: {CYAN}{BOLD}{word}{RESET}")
        try:
            ans = input("É uma palavra real em inglês? [s/n]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nRetornando ao menu...")
            return

        user_thinks_real = (ans in ["s", "sim", "y"])
        is_correct = (user_thinks_real == item["real"])

        if is_correct:
            print(f"{GREEN}✓ Correto!{RESET}")
            correct += 1
        else:
            print(f"{RED}✗ Incorreto!{RESET}")
            status_str = "é uma PALAVRA REAL" if item["real"] else "é uma PALAVRA FALSA (inventada)"
            print(f"👉 Na verdade, '{word}' {status_str}.")
            print(f"💡 {item['def']}")
            if item["real"]:
                record_weak_word(word)

            front = f"<b>[DET: Real vs Fake Word]</b><br><br><h2 style='color:#3b82f6;'>{word}</h2><br>Essa palavra existe em inglês?"
            back = f"<h2 style='color:{'#10b981' if item['real'] else '#ef4444'};'>{'SIM (Real)' if item['real'] else 'NÃO (Pseudo-palavra)'}</h2>"
            back += f"<p><b>Significado/Regra:</b> {item['def']}</p>"
            if item.get("ex"):
                back += f"<p><b>Exemplo:</b> <i>{item['ex']}</i></p>"

            audio_to_gen = word if item["real"] else None
            push_to_anki(
                subdeck_name="Read & Select",
                front_html=front,
                back_html=back,
                tags=["DET", "DET_ReadAndSelect"],
                audio_text=audio_to_gen
            )
            mistakes += 1

    print("\n" + "=" * 55)
    print(f"{BOLD}Pontuação:{RESET} {correct}/{len(sample_words)}")
    if mistakes > 0:
        print(f"{YELLOW}📥 {mistakes} card(s) com áudio enviados em background ao Anki!{RESET}")
    record_skill_progress(["comprehension"], correct, len(sample_words))
    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 3. LISTEN & TYPE (BATCH OF 6 SENTENCES + HUMAN TTS + WORD-BY-WORD COLOR DIFF)
# ==============================================================================
def save_listen_type_batch_to_archive(items_list):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        archive = []
        if os.path.exists(LISTEN_TYPE_ARCHIVE_FILE):
            with open(LISTEN_TYPE_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive = json.load(f)
        existing = {entry.get("audio", "").strip().lower() for entry in archive}
        for item in items_list:
            aud = item.get("audio", "").strip()
            if aud and aud.lower() not in existing:
                archive.append(item)
                existing.add(aud.lower())
        with open(LISTEN_TYPE_ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(archive, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_unseen_listen_type_from_archive():
    if os.path.exists(LISTEN_TYPE_ARCHIVE_FILE):
        try:
            with open(LISTEN_TYPE_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    unseen = [item for item in archived if "audio" in item and len(item["audio"]) > 10 and not is_item_seen("listen_type", item)]
                    if unseen:
                        return random.choice(unseen)
        except Exception:
            pass
    return None

def get_random_listen_type_from_pool():
    unseen = get_unseen_listen_type_from_archive()
    if unseen:
        return unseen
    pool = list(LISTEN_TYPE_BANK)
    if os.path.exists(LISTEN_TYPE_ARCHIVE_FILE):
        try:
            with open(LISTEN_TYPE_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    for item in archived:
                        if "audio" in item and len(item["audio"]) > 10:
                            pool.append(item)
        except Exception:
            pass
    unseen_pool = [item for item in pool if not is_item_seen("listen_type", item)]
    return random.choice(unseen_pool) if unseen_pool else random.choice(pool)

def generate_dynamic_listen_type_ai(batch_size=6):
    """Generates a batch of 6 brand-new spoken sentences in ONE single API request (85% less API usage!)."""
    topics_sample = random.sample(C_TEST_AI_TOPICS, min(4, len(C_TEST_AI_TOPICS)))
    weak_hint = get_weak_words_hint(3)
    prompt = (
        f"You are an expert test designer for the Duolingo English Test (DET) at CEFR B2/C1 level.\n"
        f"Generate a batch of {batch_size} diverse, brand-new sentences for the 'Listen & Type' (dictation) task across academic themes such as {', '.join(topics_sample)}.{weak_hint}\n\n"
        "Requirements for EACH sentence:\n"
        "1. Academic or formal spoken English (11-17 words).\n"
        "2. Clean grammatical structure with high-utility academic vocabulary or connectors.\n"
        "3. Identify 2-3 focus words/features (phonetic/spelling difficulty).\n"
        "4. Provide precise Portuguese translation.\n\n"
        f"Respond ONLY with valid JSON array of {batch_size} objects:\n"
        "[\n"
        "  {\n"
        '    "audio": "Exact academic sentence here.",\n'
        '    "focus": "focus_word1, focus_word2",\n'
        '    "trans": "Tradução precisa em português."\n'
        "  }\n"
        "]"
    )
    raw = call_gemini(prompt, json_mode=True, max_tokens=900)
    if raw:
        try:
            cleaned = re.search(r"\[.*\]", raw, re.DOTALL)
            if cleaned:
                data = json.loads(cleaned.group(0))
                if isinstance(data, list):
                    valid_items = []
                    for entry in data:
                        if isinstance(entry, dict) and "audio" in entry and len(entry["audio"].split()) >= 6:
                            aud = entry["audio"].strip().rstrip(".") + "."
                            valid_items.append({
                                "audio": aud,
                                "focus": entry.get("focus", "").strip(),
                                "trans": entry.get("trans", "").strip()
                            })
                    if valid_items:
                        save_listen_type_batch_to_archive(valid_items)
                        return valid_items[0]
        except Exception:
            pass
    return None

def build_word_diff_report(orig_text, user_text):
    """Builds a colored word-by-word visual diff and partial accuracy score (official DET style)."""
    orig_words = orig_text.split()
    user_words = user_text.split()

    def clean_w(w):
        return re.sub(r"[^a-zA-Z0-9]", "", w).lower()

    orig_clean = [clean_w(w) for w in orig_words]
    user_clean = [clean_w(w) for w in user_words]

    matcher = difflib.SequenceMatcher(None, orig_clean, user_clean)
    diff_tokens = []
    matched_score = 0.0
    missed_words = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                diff_tokens.append(f"{GREEN}{orig_words[k]}{RESET}")
                matched_score += 1.0
        elif tag == "replace":
            orig_slice = orig_words[i1:i2]
            user_slice = user_words[j1:j2]
            max_len = max(len(orig_slice), len(user_slice))
            for k in range(max_len):
                if k < len(orig_slice) and k < len(user_slice):
                    ow = orig_slice[k]
                    uw = user_slice[k]
                    sim = difflib.SequenceMatcher(None, clean_w(ow), clean_w(uw)).ratio()
                    if sim >= 0.72:
                        diff_tokens.append(f"{YELLOW}{uw}→{BOLD}{ow}{RESET}")
                        matched_score += 0.65
                    else:
                        diff_tokens.append(f"{RED}{uw}→{BOLD}{ow}{RESET}")
                    missed_words.append(ow)
                elif k < len(orig_slice):
                    diff_tokens.append(f"{RED}[faltou: {BOLD}{orig_slice[k]}{RESET}{RED}]{RESET}")
                    missed_words.append(orig_slice[k])
                else:
                    diff_tokens.append(f"{RED}[-{user_slice[k]}-]{RESET}")
        elif tag == "delete":
            for k in range(i1, i2):
                diff_tokens.append(f"{RED}[faltou: {BOLD}{orig_words[k]}{RESET}{RED}]{RESET}")
                missed_words.append(orig_words[k])
        elif tag == "insert":
            for k in range(j1, j2):
                diff_tokens.append(f"{RED}[-{user_words[k]}-]{RESET}")

    total_w = max(1, len(orig_words))
    accuracy = min(1.0, matched_score / total_w)
    return " ".join(diff_tokens), accuracy, missed_words

def run_listen_type(force_ai=True):
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 3: LISTEN & TYPE (DITADO DE FRASES AUDITIVAS)]{RESET}")
    print("• Ouça a frase com voz humana natural (Google TTS / Nativo).")
    print("• Digite 'r' para ouvir de novo (máximo de 3 vezes).")
    print("• Pontuação parcial palavra por palavra + Diff colorido.\n")

    item = None
    if force_ai:
        item = get_unseen_listen_type_from_archive()
        if item:
            print(f"{GREEN}⚡ Frase inédita carregada do lote local (0ms / 0 requisição)!{RESET}\n")
        elif get_gemini_key():
            print(f"{CYAN}🤖 Solicitando à IA (Gemini) um lote de 6 frases auditivas inéditas (B2/C1)...{RESET}")
            item = generate_dynamic_listen_type_ai(6)
            if item:
                print(f"{GREEN}✓ Lote de 6 frases gerado via IA (próximos 5 treinos terão 0ms de espera)!{RESET}\n")
            else:
                print(f"{YELLOW}⚠️ Não foi possível gerar via IA no momento. Carregando do banco/arquivo...{RESET}\n")
        else:
            print(f"{YELLOW}⚠️ Chave do Gemini não configurada. Usando banco/arquivo...{RESET}\n")

    if not item:
        item = get_random_listen_type_from_pool()

    mark_item_seen("listen_type", item)
    text = item["audio"]

    replays = 3
    print(f"{CYAN}🔊 Reproduzindo áudio...{RESET}")
    speak_text(text)

    while True:
        prompt_txt = f"\nDigite a frase que ouviu (ou 'r' para repetir, restam {replays}): "
        try:
            ans = input(prompt_txt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nRetornando ao menu...")
            return
        if ans.lower() == "r":
            if replays > 0:
                replays -= 1
                speak_text(text)
            else:
                print(f"{YELLOW}Sem repetições restantes!{RESET}")
            continue
        if not ans:
            continue
        break

    diff_str, accuracy, missed_words = build_word_diff_report(text, ans)
    acc_pct = accuracy * 100

    for mw in missed_words:
        if len(mw) >= 5:
            record_weak_word(mw)

    if accuracy >= 0.99:
        print(f"\n{GREEN}{BOLD}✓ Perfeito (100%)! Transcrição exata.{RESET}")
        print(f"• Tradução: {DIM}{item.get('trans', '')}{RESET}")
        record_skill_progress(["comprehension", "conversation"], 1, 1)
    else:
        badge_color = GREEN if acc_pct >= 80 else (YELLOW if acc_pct >= 55 else RED)
        print(f"\n{badge_color}{BOLD}📊 Precisão DET: {acc_pct:.1f}%{RESET}")
        print(f"• {BOLD}Diff Palavra por Palavra:{RESET} {diff_str}")
        print(f"• {BOLD}Frase Original:{RESET}           {GREEN}{text}{RESET}")
        print(f"• {BOLD}Tradução:{RESET}                 {CYAN}{item.get('trans', '')}{RESET}")
        if item.get("focus"):
            print(f"• {BOLD}Foco Ortográfico:{RESET}         {YELLOW}{item.get('focus', '')}{RESET}")

        defn = item.get("trans", "Ditado auditivo de alta frequência acadêmica.")
        front = f"<b>[DET: Listen & Type]</b><br><br>Frase do teste auditivo:<br><br><i>[Ouça e transcreva mentalmente]</i><br><br><b>Foco:</b> {item.get('focus', '')}"
        back = f"<h3 style='color:#10b981; margin-bottom:8px;'>{text}</h3>"
        back += f"<p style='font-size:16px; margin:8px 0;'><b>Significado / Tradução:</b> {defn}</p>"
        back += f"<p style='font-size:14px; color:#475569;'><b>Sua tentativa ({acc_pct:.0f}%):</b> {ans}</p>"

        push_to_anki(
            subdeck_name="Listen & Type",
            front_html=front,
            back_html=back,
            tags=["DET", "DET_ListenAndType"],
            audio_text=text
        )
        print(f"{YELLOW}📥 Card de ditado com áudio nativo enviado ao Anki em segundo plano!{RESET}")
        partial_credit = round(accuracy, 2) if accuracy >= 0.6 else 0
        record_skill_progress(["comprehension", "conversation"], partial_credit, 1)

        # Frente 2: Active Recall Retry (Memória Motora)
        print(f"\n{MAGENTA}{BOLD}✍️  FIXAÇÃO ATIVA (Memória Motora):{RESET}")
        speak_text(text)
        try:
            retry_ans = input(f"Redigite a frase corrigida agora para fixar (ou [ENTER] para pular): ").strip()
            if retry_ans:
                norm_o = re.sub(r"[^a-zA-Z0-9 ]", "", text.lower()).strip()
                norm_r = re.sub(r"[^a-zA-Z0-9 ]", "", retry_ans.lower()).strip()
                if norm_o == norm_r:
                    print(f"{GREEN}{BOLD}✓ Excelente! Ortografia gravada na memória muscular.{RESET}")
                else:
                    print(f"{YELLOW}Quase lá! Compare novamente com: {GREEN}{text}{RESET}")
        except (KeyboardInterrupt, EOFError):
            pass

    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 4. TIMED WRITING (BATCH PROMPTS + LIVE TIMER + REAL DASHBOARD SUBSCORES)
# ==============================================================================
def save_writing_prompts_to_archive(prompts_list):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        archive = []
        if os.path.exists(WRITING_PROMPTS_ARCHIVE_FILE):
            with open(WRITING_PROMPTS_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive = json.load(f)
        for p in prompts_list:
            if p and p not in archive:
                archive.append(p)
        with open(WRITING_PROMPTS_ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(archive, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_unseen_writing_prompt():
    if os.path.exists(WRITING_PROMPTS_ARCHIVE_FILE):
        try:
            with open(WRITING_PROMPTS_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    unseen = [p for p in archived if isinstance(p, str) and len(p) > 25 and not is_item_seen("writing", p)]
                    if unseen:
                        return random.choice(unseen)
        except Exception:
            pass
    return None

def get_random_writing_prompt_pool():
    unseen = get_unseen_writing_prompt()
    if unseen:
        return unseen
    pool = list(WRITING_PROMPTS)
    if os.path.exists(WRITING_PROMPTS_ARCHIVE_FILE):
        try:
            with open(WRITING_PROMPTS_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    pool.extend(archived)
        except Exception:
            pass
    unseen_pool = [p for p in pool if not is_item_seen("writing", p)]
    return random.choice(unseen_pool) if unseen_pool else random.choice(pool)

def generate_dynamic_writing_prompt_ai(batch_size=4):
    """Generates a batch of 4 brand-new academic essay prompts in ONE API call."""
    topics_sample = random.sample(C_TEST_AI_TOPICS, min(batch_size, len(C_TEST_AI_TOPICS)))
    prompt = (
        f"You are a Senior Duolingo English Test (DET) Examiner designing 'Read, Then Write' prompts (5-minute academic essay) at CEFR B2/C1.\n"
        f"Create {batch_size} engaging, debate-worthy academic prompts inspired by: {', '.join(topics_sample)}.\n"
        "Requirements for EACH prompt:\n"
        "1. Present a clear academic, technological, or societal dilemma.\n"
        "2. Instruct the candidate to argue their position with concrete reasons and examples (2-3 sentences).\n\n"
        f"Respond ONLY with a valid JSON array of {batch_size} strings:\n"
        '["Prompt 1...", "Prompt 2..."]'
    )
    raw = call_gemini(prompt, json_mode=True, max_tokens=600)
    if raw:
        try:
            cleaned = re.search(r"\[.*\]", raw, re.DOTALL)
            if cleaned:
                data = json.loads(cleaned.group(0))
                if isinstance(data, list):
                    valid = [str(p).strip() for p in data if len(str(p).strip()) > 30]
                    if valid:
                        save_writing_prompts_to_archive(valid)
                        return valid[0]
        except Exception:
            pass
    return None

def run_writing_prompt(force_ai=True):
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 4: INTERACTIVE WRITING (5 MIN ETAPA 1 + 3 MIN FOLLOW-UP OFICIAL)]{RESET}")

    prompt = None
    if force_ai:
        prompt = get_unseen_writing_prompt()
        if prompt:
            print(f"{GREEN}⚡ Tema inédito carregado do lote local (0ms / 0 requisição)!{RESET}")
        elif get_gemini_key():
            print(f"{CYAN}🤖 Gerando lote de temas de redação acadêmica inéditos via IA...{RESET}")
            prompt = generate_dynamic_writing_prompt_ai(4)
            if prompt:
                print(f"{GREEN}✓ Lote de temas gerado via IA!{RESET}")
            else:
                print(f"{YELLOW}⚠️ Não foi possível gerar prompt via IA. Usando tema do banco...{RESET}")
        else:
            print(f"{YELLOW}⚠️ Chave do Gemini não configurada. Usando tema do banco...{RESET}")

    if not prompt:
        prompt = get_random_writing_prompt_pool()

    mark_item_seen("writing", prompt)
    mission = get_c1_lexical_mission(3)

    print(f"\n{BOLD}PROMPT ETAPA 1 (5 MINUTOS):{RESET}")
    print(f"{YELLOW}{prompt}{RESET}\n")
    print_c1_mission_banner(mission)
    print("Dicas DET:")
    print("  • Etapa 1 (5 min): 110-140 palavras | Etapa 2 Follow-up (3 min): 60-90 palavras.")
    print("  • Ao terminar cada etapa antes do tempo, digite 'FIM' em uma linha separada.\n")

    input(f"{GREEN}Pressione [ENTER] para iniciar os 5 minutos da Etapa 1...{RESET}")
    start_t = time.time()
    print(f"\n{CYAN}Cronômetro Etapa 1 iniciado (05:00)! Digite seus parágrafos (e 'FIM' para concluir):{RESET}\n")

    lines = []
    while True:
        elapsed_now = int(time.time() - start_t)
        rem_now = max(0, 300 - elapsed_now)
        m_r, s_r = divmod(rem_now, 60)
        curr_words = len(" ".join(lines).split())
        t_col = RED if rem_now < 45 else (YELLOW if rem_now < 120 else DIM)
        try:
            line = input(f"{t_col}[E1 {m_r:02d}:{s_r:02d} | {curr_words} pal.] > {RESET}")
            if line.strip().upper() == "FIM":
                break
            lines.append(line)
            if rem_now <= 0:
                print(f"\n{RED}{BOLD}⏰ Tempo de 5 minutos da Etapa 1 concluído!{RESET}")
                break
        except (KeyboardInterrupt, EOFError):
            break

    elapsed_1 = time.time() - start_t
    stage1_text = " ".join(lines).strip()
    stage2_prompt = ""
    stage2_text = ""
    elapsed_2 = 0.0

    # Frente 3: Interactive Writing Stage 2 (3-Minute Follow-up)
    if len(stage1_text.split()) >= 12:
        try:
            do_followup = input(f"\n{CYAN}👉 Realizar a Etapa 2 Oficial do DET (3 min de Interactive Follow-up sobre seu texto)? [S/n]: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            do_followup = "n"

        if do_followup not in ["n", "nao", "no"]:
            if get_gemini_key():
                print(f"{CYAN}🤖 Lendo seu argumento e gerando a pergunta oficial de Follow-up (3 min)...{RESET}")
                fp_req = (
                    f"Initial Prompt: {prompt}\nCandidate Stage 1 Response: {stage1_text}\n\n"
                    "As an official Duolingo English Test Interactive Writing module, generate 1 direct, thought-provoking "
                    "follow-up prompt (1-2 sentences) for the 3-minute Stage 2. Challenge a specific assumption in the candidate's "
                    "response, ask for a concrete counter-perspective, or ask about long-term implementation trade-offs. "
                    "Output ONLY the follow-up prompt in English."
                )
                stage2_prompt = (call_gemini(fp_req, max_tokens=120) or "").strip().strip('"')
            if not stage2_prompt:
                stage2_prompt = "Considering your perspective above, what is the strongest counterargument a critic might raise against your position, and how can its negative trade-offs be mitigated in practice?"

            print(f"\n{BOLD}{MAGENTA}── ETAPA 2: INTERACTIVE FOLLOW-UP (3 MINUTOS) ──{RESET}")
            print(f"{YELLOW}{stage2_prompt}{RESET}\n")
            start_t2 = time.time()
            lines_2 = []
            while True:
                el2 = int(time.time() - start_t2)
                rem2 = max(0, 180 - el2)
                m2, s2 = divmod(rem2, 60)
                cw2 = len(" ".join(lines_2).split())
                tc2 = RED if rem2 < 30 else (YELLOW if rem2 < 60 else DIM)
                try:
                    line2 = input(f"{tc2}[E2 {m2:02d}:{s2:02d} | {cw2} pal.] > {RESET}")
                    if line2.strip().upper() == "FIM":
                        break
                    lines_2.append(line2)
                    if rem2 <= 0:
                        print(f"\n{RED}{BOLD}⏰ Tempo de 3 minutos da Etapa 2 concluído!{RESET}")
                        break
                except (KeyboardInterrupt, EOFError):
                    break
            elapsed_2 = time.time() - start_t2
            stage2_text = " ".join(lines_2).strip()

    elapsed = elapsed_1 + elapsed_2
    full_text = f"{stage1_text}\n\n{stage2_text}".strip() if stage2_text else stage1_text
    words = full_text.split()
    word_count = len(words)
    mins = elapsed / 60.0
    wpm = word_count / mins if mins > 0 else 0

    print("\n" + "=" * 65)
    print(f"{BOLD}ANÁLISE ESTATÍSTICA & LÉXICA LOCAL (0ms):{RESET}")
    print(f"• Tempo Total: {int(elapsed//60)}m {int(elapsed%60)}s | Total de Palavras: {BOLD}{word_count}{RESET} | WPM: {wpm:.1f}")

    lower_text = full_text.lower()
    found_connectors = [c for c in ACADEMIC_CONNECTORS if c in lower_text]
    print(f"• Conectivos detectados ({len(found_connectors)}): {GREEN}{', '.join(set(found_connectors)) or 'Nenhum'}{RESET}")
    evaluate_c1_mission_and_cliches(full_text, mission)

    gemini_key = get_gemini_key()
    scored_by_ai = False
    if gemini_key and word_count >= 15:
        print(f"\n{CYAN}🤖 Consultando Google Gemini AI Pro para correção oficial DET...{RESET}")
        sys_inst = (
            "Você é um Examinador Sênior Oficial do Duolingo English Test (DET). "
            "Analise a redação (Interactive Writing) do candidato em português de forma estruturada segundo as rubricas oficiais:\n"
            "1. 📊 NOTA ESTIMADA DET (Escala 10-160, meta UFRJ B2/C1: 95-115) & Nível CEFR.\n"
            "2. 📝 CORREÇÕES GRAMATICAIS & SINTÁTICAS DIRETAS (Original -> Correção).\n"
            "3. ✨ UPGRADES LEXICAIS C1 (Como substituir termos simples por vocabulário acadêmico de alto impacto).\n"
            "4. 🏆 PARÁGRAFO MODELO C1 REESCRITO.\n\n"
            "IMPORTANTE: Ao final absoluto da sua resposta, inclua obrigatoriamente a tag de pontuação no formato exato:\n"
            "[DET_EVAL: LITERACY=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )
        if stage2_text:
            ai_prompt = (
                f"Stage 1 Prompt (5 min): {prompt}\nCandidate Stage 1 Essay:\n{stage1_text}\n\n"
                f"Stage 2 Follow-up Prompt (3 min): {stage2_prompt}\nCandidate Stage 2 Follow-up Essay:\n{stage2_text}"
            )
        else:
            ai_prompt = f"Prompt: {prompt}\n\nCandidate's Essay ({word_count} words):\n{full_text}"

        ai_resp = call_gemini(ai_prompt, sys_inst)
        if ai_resp:
            print(f"\n{BOLD}{CYAN}AVALIAÇÃO DA BANCA (GEMINI AI):{RESET}")
            print(ai_resp)

            lit_score, prod_score = extract_writing_scores(ai_resp)
            record_skill_score("literacy", lit_score)
            record_skill_score("production", prod_score)
            scored_by_ai = True
            print(f"\n{BOLD}📊 Subscores Oficiais Registrados no Dashboard DET:{RESET}")
            print(f"  • Literacy:   {CYAN}{lit_score}/160 pts{RESET}")
            print(f"  • Production: {CYAN}{prod_score}/160 pts{RESET}")

            front = f"<b>[DET: Interactive Writing Upgrade]</b><br><br><b>Prompt:</b> {prompt}<br><br><b>Sua redação ({word_count} palavras):</b><br><pre>{full_text[:350]}...</pre>"
            back = f"<h3>Feedback Oficial DET ({lit_score}/160):</h3><div style='text-align:left;'>{ai_resp.replace(chr(10), '<br>')}</div>"
            push_to_anki(
                subdeck_name="Writing Upgrades",
                front_html=front,
                back_html=back,
                tags=["DET", "DET_Writing"]
            )
            print(f"\n{YELLOW}📥 Análise completa enviada ao Anki em segundo plano!{RESET}")

    if not scored_by_ai:
        quality_score = 1 if (word_count >= 100 and len(found_connectors) >= 2) else 0
        record_skill_progress(["literacy", "production"], quality_score, 1)
    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 5. INTERACTIVE READING (FULL 4-STAGE OFFICIAL DET SIMULATOR IN 1 SINGLE CALL)
# ==============================================================================
def save_interactive_reading_to_archive(item):
    """Saves generated Interactive Reading items into an offline archive pool."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        archive = []
        if os.path.exists(INTERACTIVE_READING_ARCHIVE_FILE):
            with open(INTERACTIVE_READING_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive = json.load(f)
        if not any(entry.get("title") == item.get("title") for entry in archive):
            archive.append(item)
            with open(INTERACTIVE_READING_ARCHIVE_FILE, "w", encoding="utf-8") as f:
                json.dump(archive, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_unseen_interactive_reading_from_archive():
    if os.path.exists(INTERACTIVE_READING_ARCHIVE_FILE):
        try:
            with open(INTERACTIVE_READING_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    # Prefer full 4-stage items that are unseen
                    unseen_full = [i for i in archived if "clozes" in i and not is_item_seen("interactive_reading", i)]
                    if unseen_full:
                        return random.choice(unseen_full)
                    unseen_any = [i for i in archived if not is_item_seen("interactive_reading", i)]
                    if unseen_any:
                        return random.choice(unseen_any)
        except Exception:
            pass
    return None

def get_random_interactive_reading_from_pool():
    unseen = get_unseen_interactive_reading_from_archive()
    if unseen:
        return unseen
    pool = list(INTERACTIVE_READING_BANK)
    if os.path.exists(INTERACTIVE_READING_ARCHIVE_FILE):
        try:
            with open(INTERACTIVE_READING_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    pool.extend(archived)
        except Exception:
            pass
    return random.choice(pool)

def _shuffle_question_dict(q_dict):
    """Helper to shuffle 4 options when given correct_option and distractors or options+answer."""
    if "correct_option" in q_dict:
        correct = str(q_dict["correct_option"]).strip()
        distractors = [
            str(q_dict.get("distractor_1", "")).strip(),
            str(q_dict.get("distractor_2", "")).strip(),
            str(q_dict.get("distractor_3", "")).strip()
        ]
        opts = [correct] + distractors
        random.shuffle(opts)
        return {
            "label": q_dict.get("label", ""),
            "question": q_dict.get("question", ""),
            "options": opts,
            "answer": opts.index(correct),
            "explanation": str(q_dict.get("explanation", "")).strip()
        }
    elif "options" in q_dict and isinstance(q_dict["options"], list) and len(q_dict["options"]) == 4:
        ans_idx = int(q_dict.get("answer", 0))
        correct = q_dict["options"][ans_idx]
        opts = list(q_dict["options"])
        random.shuffle(opts)
        return {
            "label": q_dict.get("label", ""),
            "question": q_dict.get("question", ""),
            "options": opts,
            "answer": opts.index(correct),
            "explanation": str(q_dict.get("explanation", "")).strip()
        }
    return None

def generate_dynamic_interactive_reading_ai():
    """Composes a complete 4-stage DET Interactive Reading passage in ONE single JSON API call."""
    topic = random.choice(INTERACTIVE_READING_AI_TOPICS)
    weak_hint = get_weak_words_hint(3)
    prompt = (
        f"You are an expert test designer for the Duolingo English Test (DET) at the CEFR B2/C1 academic level.\n"
        f"Generate a complete 4-stage 'Interactive Reading' simulation about '{topic}'.{weak_hint}\n\n"
        "Structure requirements:\n"
        "1. 'title': Specific academic title of the passage.\n"
        "2. 'paragraph_1': First academic paragraph (55-75 words) containing exactly 3 numbered blanks written literally as [1], [2], and [3] in place of key academic words/connectors.\n"
        "3. 'clozes': Array of 3 objects for [1], [2], and [3], each with 'label' ('[1]', '[2]', '[3]'), 'correct_option', 'distractor_1', 'distractor_2', 'distractor_3', and 'explanation' (in Portuguese).\n"
        "4. 'bridge_question': Object for Stage 2 (Complete the Passage — the missing transition sentence between paragraph_1 and paragraph_2), with 'correct_option', 'distractor_1', 'distractor_2', 'distractor_3', and 'explanation' (in Portuguese).\n"
        "5. 'paragraph_2': Concluding academic paragraph (45-65 words) that follows the bridge sentence.\n"
        "6. 'idea_question': Object for Stage 3 (Identify the Idea — main thesis of the whole text), with 'correct_option', 'distractor_1', 'distractor_2', 'distractor_3', and 'explanation' (in Portuguese).\n"
        "7. 'title_question': Object for Stage 4 (Title the Passage — best academic title), with 'correct_option', 'distractor_1', 'distractor_2', 'distractor_3', and 'explanation' (in Portuguese).\n\n"
        "Respond ONLY with valid JSON in this exact schema:\n"
        "{\n"
        '  "title": "Academic Title",\n'
        '  "paragraph_1": "Text with [1] and [2] and [3]...",\n'
        '  "clozes": [\n'
        '    {"label": "[1]", "correct_option": "word", "distractor_1": "d1", "distractor_2": "d2", "distractor_3": "d3", "explanation": "Explicação em PT..."}\n'
        "  ],\n"
        '  "bridge_question": {"correct_option": "Full bridge sentence.", "distractor_1": "d1", "distractor_2": "d2", "distractor_3": "d3", "explanation": "Explicação em PT..."},\n'
        '  "paragraph_2": "Second paragraph text...",\n'
        '  "idea_question": {"correct_option": "Main idea statement.", "distractor_1": "d1", "distractor_2": "d2", "distractor_3": "d3", "explanation": "Explicação em PT..."},\n'
        '  "title_question": {"correct_option": "Best Title", "distractor_1": "d1", "distractor_2": "d2", "distractor_3": "d3", "explanation": "Explicação em PT..."}\n'
        "}"
    )
    raw = call_gemini(prompt, json_mode=True, max_tokens=1500)
    if raw:
        try:
            cleaned = re.search(r"\{.*\}", raw, re.DOTALL)
            if cleaned:
                data = json.loads(cleaned.group(0))
                if all(k in data for k in ["paragraph_1", "clozes", "bridge_question", "paragraph_2", "idea_question", "title_question"]):
                    clozes_shuffled = []
                    for c in data["clozes"][:3]:
                        sq = _shuffle_question_dict(c)
                        if sq:
                            clozes_shuffled.append(sq)
                    bridge_q = _shuffle_question_dict(data["bridge_question"])
                    idea_q = _shuffle_question_dict(data["idea_question"])
                    title_q = _shuffle_question_dict(data["title_question"])

                    if len(clozes_shuffled) == 3 and bridge_q and idea_q and title_q:
                        item = {
                            "title": data.get("title", topic).strip(),
                            "paragraph_1": data["paragraph_1"].strip(),
                            "clozes": clozes_shuffled,
                            "bridge_question": bridge_q,
                            "paragraph_2": data["paragraph_2"].strip(),
                            "idea_question": idea_q,
                            "title_question": title_q
                        }
                        save_interactive_reading_to_archive(item)
                        return item
        except Exception:
            pass
    return None

def _ask_mc_question(header_title, context_box, question_prompt, q_obj, anki_tag_suffix):
    """Renders and evaluates a 4-option multiple-choice stage in Interactive Reading."""
    print(f"\n{BOLD}{MAGENTA}{header_title}{RESET}")
    if context_box:
        print(f"{context_box}\n")
    print(f"{YELLOW}{question_prompt}{RESET}\n")
    for idx, opt in enumerate(q_obj["options"], 1):
        print(f"  {BOLD}{idx}){RESET} {opt}")

    while True:
        try:
            ans = input("\nEscolha a alternativa (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if ans in ["1", "2", "3", "4"]:
            user_idx = int(ans) - 1
            break
        print("Digite 1, 2, 3 ou 4.")

    correct_opt = q_obj["options"][q_obj["answer"]]
    if user_idx == q_obj["answer"]:
        print(f"{GREEN}✓ Correto!{RESET} {q_obj['explanation']}")
        return True
    else:
        print(f"{RED}✗ Incorreto.{RESET} Resposta correta: ({q_obj['answer'] + 1}) {BOLD}{correct_opt}{RESET}")
        print(f"{DIM}Explicação: {q_obj['explanation']}{RESET}")
        if len(correct_opt.split()) == 1:
            record_weak_word(correct_opt)
        front = f"<b>[DET: Interactive Reading - {anki_tag_suffix}]</b><br><br><i>{context_box[:400]}</i><br><br><b>Pergunta:</b> {question_prompt}"
        back = f"<h3 style='color:#10b981;'>{correct_opt}</h3><p><b>Explicação:</b> {q_obj['explanation']}</p>"
        push_to_anki(
            subdeck_name="Interactive Reading",
            front_html=front,
            back_html=back,
            tags=["DET", "DET_InteractiveReading"],
            audio_text=correct_opt
        )
        return False

def run_interactive_reading(force_ai=True):
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 5: INTERACTIVE READING (SIMULADOR OFICIAL DE 4 ETAPAS DET)]{RESET}")
    print("• Etapa 1: Complete the Sentences (3 lacunas conceituais no Parágrafo 1)")
    print("• Etapa 2: Complete the Passage (Frase de conexão entre Parágrafo 1 e 2)")
    print("• Etapa 3: Identify the Idea (Ideia central do texto completo)")
    print("• Etapa 4: Title the Passage (Escolha do título acadêmico ideal)\n")

    item = None
    if force_ai:
        item = get_unseen_interactive_reading_from_archive()
        if item and "clozes" in item:
            print(f"{GREEN}⚡ Bloco completo de 4 etapas carregado do buffer local (0ms / 0 requisição)!{RESET}\n")
        elif get_gemini_key():
            print(f"{CYAN}🤖 Solicitando à IA (Gemini) um bloco completo de Interactive Reading (4 etapas em 1 chamada)...{RESET}")
            item = generate_dynamic_interactive_reading_ai()
            if item:
                print(f"{GREEN}✓ Simulador completo de 4 etapas gerado com sucesso via IA!{RESET}\n")
            else:
                print(f"{YELLOW}⚠️ Não foi possível gerar via IA no momento. Carregando do banco/arquivo...{RESET}\n")
        else:
            print(f"{YELLOW}⚠️ Chave do Gemini não configurada. Usando texto do banco/arquivo...{RESET}\n")

    if not item:
        item = get_random_interactive_reading_from_pool()

    mark_item_seen("interactive_reading", item)

    # Full 4-stage interactive reading block
    if "clozes" in item:
        total_pts = 0
        max_pts = len(item["clozes"]) + 3
        p1_display = item["paragraph_1"]

        # STAGE 1: Complete the Sentences
        for idx, cloze in enumerate(item["clozes"], 1):
            label = cloze.get("label") or f"[{idx}]"
            highlighted_p1 = p1_display.replace(label, f"{BG_YELLOW}{BOLD}{label}{RESET}")
            res = _ask_mc_question(
                f"── ETAPA 1/4: COMPLETE THE SENTENCES (Lacuna {label}) ──",
                f"\"{highlighted_p1}\"",
                f"Qual palavra/expressão preenche perfeitamente a lacuna {label}?",
                cloze,
                "CompleteTheSentences"
            )
            if res is None:
                return
            if res:
                total_pts += 1
            correct_word = cloze["options"][cloze["answer"]]
            p1_display = p1_display.replace(label, f"{GREEN}{BOLD}{correct_word}{RESET}")

        # STAGE 2: Complete the Passage
        p1_clean = re.sub(r"\033\[[0-9;]*m", "", p1_display)
        context_stage2 = (
            f"{BOLD}Parágrafo 1:{RESET} \"{p1_display}\"\n\n"
            f"  {BG_YELLOW}{BOLD}>>> [FRASE DE TRANSIÇÃO FALTANTE AQUI] <<<{RESET}\n\n"
            f"{BOLD}Parágrafo 2:{RESET} \"{item['paragraph_2']}\""
        )
        res2 = _ask_mc_question(
            "── ETAPA 2/4: COMPLETE THE PASSAGE (Conexão entre Parágrafos) ──",
            context_stage2,
            "Qual frase melhor conecta o Parágrafo 1 ao Parágrafo 2 de forma lógica e coesa?",
            item["bridge_question"],
            "CompleteThePassage"
        )
        if res2 is None:
            return
        if res2:
            total_pts += 1

        bridge_correct = item["bridge_question"]["options"][item["bridge_question"]["answer"]]
        full_passage_clean = f"{p1_clean} {bridge_correct} {item['paragraph_2']}"
        full_passage_display = f"\"{p1_display} {CYAN}{BOLD}{bridge_correct}{RESET} {item['paragraph_2']}\""

        # STAGE 3: Identify the Idea
        res3 = _ask_mc_question(
            "── ETAPA 3/4: IDENTIFY THE IDEA (Tese Central do Texto) ──",
            full_passage_display,
            "Qual alternativa sintetiza com precisão a ideia principal (Main Idea) desta passagem?",
            item["idea_question"],
            "IdentifyTheIdea"
        )
        if res3 is None:
            return
        if res3:
            total_pts += 1

        # STAGE 4: Title the Passage
        res4 = _ask_mc_question(
            "── ETAPA 4/4: TITLE THE PASSAGE (Título Acadêmico) ──",
            full_passage_display,
            "Qual é o título acadêmico mais adequado e preciso para o texto completo?",
            item["title_question"],
            "TitleThePassage"
        )
        if res4 is None:
            return
        if res4:
            total_pts += 1

        print("\n" + "=" * 65)
        pct = (total_pts / max_pts) * 100
        col = GREEN if pct >= 75 else (YELLOW if pct >= 50 else RED)
        print(f"{BOLD}RESULTADO INTERACTIVE READING:{RESET} {col}{BOLD}{total_pts}/{max_pts} acertos ({pct:.0f}%){RESET}")
        if total_pts < max_pts:
            print(f"{YELLOW}📥 Cards das etapas erradas enviados ao Anki em segundo plano!{RESET}")
        record_skill_progress(["literacy", "comprehension"], total_pts, max_pts)
    else:
        # Fallback for legacy 1-question items
        print(f"{BOLD}Texto Base:{RESET} {CYAN}{item['title']}{RESET}")
        res = _ask_mc_question(
            "── COMPLETE THE PASSAGE ──",
            f"\"{item['passage_pre']}\"",
            item["question"],
            item,
            "CompleteThePassage"
        )
        if res is None:
            return
        record_skill_progress(["literacy", "comprehension"], 1 if res else 0, 1)

    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 6. VOCAB & CONNECTORS DRILL (BATCH OF 10 QUESTIONS PER API CALL)
# ==============================================================================
def save_vocab_drill_to_archive(questions_list):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        archive = []
        if os.path.exists(VOCAB_DRILL_ARCHIVE_FILE):
            with open(VOCAB_DRILL_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive = json.load(f)
        existing_qs = {q.get("question", "").strip().lower() for q in archive}
        for q in questions_list:
            if q.get("question", "").strip().lower() not in existing_qs:
                archive.append(q)
                existing_qs.add(q.get("question", "").strip().lower())
        with open(VOCAB_DRILL_ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(archive, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_unseen_vocab_drill_batch(count=5):
    if os.path.exists(VOCAB_DRILL_ARCHIVE_FILE):
        try:
            with open(VOCAB_DRILL_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    unseen = [q for q in archived if "question" in q and "options" in q and len(q["options"]) == 4 and not is_item_seen("vocab_drill", q)]
                    if len(unseen) >= count:
                        return random.sample(unseen, count)
        except Exception:
            pass
    return None

def get_random_vocab_drill_pool():
    pool = list(VOCAB_DRILL)
    if os.path.exists(VOCAB_DRILL_ARCHIVE_FILE):
        try:
            with open(VOCAB_DRILL_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    for item in archived:
                        if "question" in item and "options" in item and len(item["options"]) == 4:
                            pool.append(item)
        except Exception:
            pass
    return pool

def generate_dynamic_vocab_drill_ai(batch_size=10):
    """Generates 10 academic vocabulary and transition questions in ONE call (serves 2 full rounds!)."""
    weak_hint = get_weak_words_hint(3)
    prompt = (
        f"You are an expert test designer for the Duolingo English Test (DET) at CEFR B2/C1 level.\n"
        f"Generate {batch_size} brand-new multiple choice questions focusing on academic connectors, discourse markers, transitions, and B2/C1 scholarly vocabulary.{weak_hint}\n\n"
        "Requirements for each question:\n"
        "1. 'word': The target word or connector.\n"
        "2. 'type': E.g. 'Connector / Contrast', 'Connector / Cause & Effect', 'Academic Adjective', 'Academic Verb'.\n"
        "3. 'question': Clear contextual question or fill-in-the-blank sentence.\n"
        "4. 'options': Array of 4 plausible options.\n"
        "5. 'answer': 0, 1, 2, or 3 (index of correct option).\n"
        "6. 'explanation': Pedagogical explanation in Portuguese explaining why the correct option fits and why others fail.\n\n"
        f"Respond ONLY with valid JSON array of {batch_size} objects:\n"
        "[\n"
        "  {\n"
        '    "word": "Notwithstanding",\n'
        '    "type": "Connector / Contrast",\n'
        '    "question": "Which sentence uses \'Notwithstanding\' correctly in an academic context?",\n'
        '    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],\n'
        '    "answer": 0,\n'
        '    "explanation": "Explicação em português..."\n'
        "  }\n"
        "]"
    )
    raw = call_gemini(prompt, json_mode=True, max_tokens=1500)
    if raw:
        try:
            cleaned = re.search(r"\[.*\]", raw, re.DOTALL)
            if cleaned:
                data = json.loads(cleaned.group(0))
                if isinstance(data, list) and len(data) >= 5:
                    valid_qs = []
                    for q in data:
                        if all(k in q for k in ["word", "question", "options", "answer", "explanation"]):
                            if isinstance(q["options"], list) and len(q["options"]) == 4 and 0 <= int(q["answer"]) < 4:
                                # Randomize options position
                                corr_opt = q["options"][int(q["answer"])]
                                opts = list(q["options"])
                                random.shuffle(opts)
                                q["options"] = opts
                                q["answer"] = opts.index(corr_opt)
                                valid_qs.append(q)
                    if len(valid_qs) >= 5:
                        save_vocab_drill_to_archive(valid_qs)
                        return valid_qs[:5]
        except Exception:
            pass
    return None

def run_vocab_drill(force_ai=True):
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 6: VOCAB & CONNECTORS DRILL]{RESET}")
    print("Questões de múltipla escolha focadas no padrão acadêmico do DET.\n")

    questions = None
    if force_ai:
        questions = get_unseen_vocab_drill_batch(5)
        if questions:
            print(f"{GREEN}⚡ 5 questões inéditas carregadas do lote local (0ms / 0 requisição)!{RESET}\n")
        elif get_gemini_key():
            print(f"{CYAN}🤖 Solicitando à IA (Gemini) um lote de 10 questões inéditas de vocabulário e conectivos...{RESET}")
            questions = generate_dynamic_vocab_drill_ai(10)
            if questions:
                print(f"{GREEN}✓ Lote de questões gerado via IA!{RESET}\n")
            else:
                print(f"{YELLOW}⚠️ Não foi possível gerar via IA no momento. Usando banco/arquivo...{RESET}\n")
        else:
            print(f"{YELLOW}⚠️ Chave do Gemini não configurada. Usando banco/arquivo...{RESET}\n")

    if not questions:
        pool = get_random_vocab_drill_pool()
        questions = random.sample(pool, min(5, len(pool)))

    correct = 0
    mistakes = 0

    for idx, q in enumerate(questions, 1):
        mark_item_seen("vocab_drill", q)
        q_type = q.get("type", "Vocab & Transition")
        print(f"\n{BOLD}Questão {idx}/{len(questions)}:{RESET} [{CYAN}{q_type}{RESET}]")
        print(f"{q['question']}")
        for opt_idx, opt in enumerate(q['options']):
            print(f"  {BOLD}{opt_idx+1}){RESET} {opt}")

        while True:
            try:
                choice = input("\nSua opção (1-4): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nRetornando ao menu...")
                return
            if choice in ["1", "2", "3", "4"]:
                user_idx = int(choice) - 1
                break
            print("Digite apenas 1, 2, 3 ou 4.")

        target_word = q.get("word", "")
        word_tag = f" [{CYAN}{target_word}{RESET}]" if target_word else ""
        if user_idx == q["answer"]:
            print(f"{GREEN}✓ Correto!{RESET}{word_tag} - {q['explanation']}")
            correct += 1
        else:
            print(f"{RED}✗ Incorreto.{RESET} A resposta certa era: {BOLD}{q['options'][q['answer']]}{RESET}{word_tag}")
            print(f"{DIM}Explicação: {q['explanation']}{RESET}")
            record_weak_word(q["word"])

            front = f"<b>[DET: Vocab & Transition]</b><br><br><h3>Palavra/Conectivo: {q['word']}</h3><br>{q['question']}"
            back = f"<h2 style='color:#10b981;'>{q['options'][q['answer']]}</h2><p><b>Regra de Uso:</b> {q['explanation']}</p>"
            push_to_anki(
                subdeck_name="Vocab & Connectors",
                front_html=front,
                back_html=back,
                tags=["DET", "DET_Vocab"],
                audio_text=q['options'][q['answer']]
            )
            mistakes += 1

    print("\n" + "=" * 45)
    print(f"{BOLD}Pontuação:{RESET} {correct}/{len(questions)}")
    if mistakes > 0:
        print(f"{YELLOW}📥 {mistakes} card(s) com áudio enviados ao Anki em segundo plano!{RESET}")
    record_skill_progress(["literacy"], correct, len(questions))
    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 7. SPEAKING SIMULATOR (BATCH PROMPTS + LINUX/MACOS MIC + GEMINI MULTIMODAL)
# ==============================================================================
def save_speaking_prompts_to_archive(prompts_list):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        archive = []
        if os.path.exists(SPEAKING_PROMPTS_ARCHIVE_FILE):
            with open(SPEAKING_PROMPTS_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive = json.load(f)
        for p in prompts_list:
            if p and p not in archive:
                archive.append(p)
        with open(SPEAKING_PROMPTS_ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(archive, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_unseen_speaking_prompt():
    if os.path.exists(SPEAKING_PROMPTS_ARCHIVE_FILE):
        try:
            with open(SPEAKING_PROMPTS_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    unseen = [p for p in archived if isinstance(p, str) and len(p) > 25 and not is_item_seen("speaking", p)]
                    if unseen:
                        return random.choice(unseen)
        except Exception:
            pass
    return None

def get_random_speaking_prompt_pool():
    unseen = get_unseen_speaking_prompt()
    if unseen:
        return unseen
    pool = list(SPEAKING_PROMPTS)
    if os.path.exists(SPEAKING_PROMPTS_ARCHIVE_FILE):
        try:
            with open(SPEAKING_PROMPTS_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    pool.extend(archived)
        except Exception:
            pass
    unseen_pool = [p for p in pool if not is_item_seen("speaking", p)]
    return random.choice(unseen_pool) if unseen_pool else random.choice(pool)

def generate_dynamic_speaking_prompt_ai(batch_size=4):
    """Generates a batch of 4 brand-new speaking prompts for DET Speaking Simulator (90s) in ONE call."""
    topics_sample = random.sample(C_TEST_AI_TOPICS, min(batch_size, len(C_TEST_AI_TOPICS)))
    prompt = (
        f"You are a Senior Duolingo English Test (DET) Examiner designing 'Speak About the Topic' prompts (90 seconds) at CEFR B2/C1.\n"
        f"Create {batch_size} engaging academic or personal-professional speaking prompts touching on: {', '.join(topics_sample)}.\n"
        "Requirements for EACH prompt:\n"
        "1. Include 2-3 specific sub-questions guiding the 90-second response (e.g. Describe X, explain why Y occurred, and reflect on Z).\n\n"
        f"Respond ONLY with a valid JSON array of {batch_size} strings:\n"
        '["Speaking prompt 1...", "Speaking prompt 2..."]'
    )
    raw = call_gemini(prompt, json_mode=True, max_tokens=600)
    if raw:
        try:
            cleaned = re.search(r"\[.*\]", raw, re.DOTALL)
            if cleaned:
                data = json.loads(cleaned.group(0))
                if isinstance(data, list):
                    valid = [str(p).strip() for p in data if len(str(p).strip()) > 30]
                    if valid:
                        save_speaking_prompts_to_archive(valid)
                        return valid[0]
        except Exception:
            pass
    return None

def get_windows_dshow_mic():
    """Auto-detects the default Windows DirectShow audio input device via ffmpeg."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore", timeout=3
        )
        out = (proc.stderr or "") + (proc.stdout or "")
        for line in out.splitlines():
            if "(audio)" in line.lower() and '"' in line:
                m = re.search(r'"([^"]+)"', line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return "Microphone"

def get_ffmpeg_mic_cmd(output_path, duration_sec=90):
    """Returns cross-platform ffmpeg microphone capture command (macOS AVFoundation vs Windows DirectShow vs Linux PulseAudio)."""
    if IS_MACOS:
        return ["ffmpeg", "-y", "-f", "avfoundation", "-i", ":0", "-t", str(duration_sec), "-ac", "1", "-ar", "16000", output_path]
    elif IS_WINDOWS:
        mic_name = get_windows_dshow_mic()
        return ["ffmpeg", "-y", "-f", "dshow", "-i", f"audio={mic_name}", "-t", str(duration_sec), "-ac", "1", "-ar", "16000", output_path]
    return ["ffmpeg", "-y", "-f", "pulse", "-i", "default", "-t", str(duration_sec), "-ac", "1", "-ar", "16000", output_path]

def record_mic_clip(output_path, duration_sec=30, label="Gravando áudio"):
    """Records microphone audio for up to duration_sec with visual progress bar and Ctrl+C early stop."""
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass

    rec_proc = subprocess.Popen(
        get_ffmpeg_mic_cmd(output_path, duration_sec),
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    elapsed = 0
    try:
        for remaining in range(duration_sec, 0, -1):
            elapsed = duration_sec - remaining + 1
            mins, secs = divmod(remaining, 60)
            bar_len = int((duration_sec - remaining) / max(1, duration_sec) * 28)
            progress = "█" * bar_len + "░" * (28 - bar_len)
            color = GREEN if remaining > (duration_sec * 0.35) else (YELLOW if remaining > 5 else RED)
            print(f"\r[{progress}] {label}: {color}{mins:02d}:{secs:02d}{RESET} (Ctrl+C p/ encerrar)...", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{CYAN}✓ Gravação encerrada pelo usuário ({elapsed}s).{RESET}")
    finally:
        if rec_proc.poll() is None:
            try:
                if rec_proc.stdin:
                    rec_proc.stdin.write(b"q\n")
                    rec_proc.stdin.flush()
            except Exception:
                pass
            time.sleep(0.4)
            if rec_proc.poll() is None:
                try:
                    rec_proc.terminate()
                except Exception:
                    pass
    print()
    return os.path.exists(output_path) and os.path.getsize(output_path) > 4000


def _extract_speak_model_sentence(feedback_text):
    """Extracts the SPEAK_MODEL target sentence from AI feedback if present."""
    if not feedback_text:
        return ""
    for line in feedback_text.splitlines():
        if "SPEAK_MODEL:" in line:
            return line.split("SPEAK_MODEL:", 1)[1].strip().strip('"').strip("*")
    return ""


def _offer_speaking_second_shot(prompt, ai_feedback, photo_path=None):
    """Interactive post-feedback loop: listen to native model sentence, shadow it, or re-record a Second Shot."""
    model_sent = _extract_speak_model_sentence(ai_feedback)
    while True:
        print(f"\n{MAGENTA}┌── 🔄 CICLO DE CONSOLIDAÇÃO ATIVA DA FALA (SECOND SHOT & SHADOWING) ───┐{RESET}")
        if model_sent:
            print(f"  🎯 {BOLD}Frase-Modelo C1:{RESET} {GREEN}\"{model_sent}\"{RESET}")
        print(f"  {BOLD}[O]{RESET} 🔊 Ouvir a frase-modelo C1 com pronúncia nativa (TTS)")
        print(f"  {BOLD}[S]{RESET} 🎙️  Treinar Shadowing (15s — repetir a frase-modelo em voz alta e checar pronúncia)")
        print(f"  {BOLD}[R]{RESET} 🔥 Second Shot (60s — regravar sua resposta aplicando as correções da IA)")
        print(f"  {BOLD}[ENTER]{RESET} Concluir e voltar")
        print(f"{MAGENTA}└───────────────────────────────────────────────────────────────────────┘{RESET}")
        try:
            act = input(f"{CYAN}Escolha [O / S / R / ENTER]: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if not act:
            break
        elif act == "o":
            text_to_speak = model_sent or "Although there are challenges, I contend that this approach is crucial. For instance, it significantly enhances efficiency. Ultimately, it fosters long-term progress."
            print(f"{CYAN}🔊 Reproduzindo pronúncia modelo...{RESET}")
            speak_text(text_to_speak)
        elif act == "s":
            target_s = model_sent or "Ultimately, provided that governments enforce strict regulations to mitigate potential risks, this innovation will foster long-term progress."
            print(f"\n{CYAN}🔊 Ouça com atenção o ritmo e a entonação:{RESET}")
            print(f"   {GREEN}{BOLD}\"{target_s}\"{RESET}")
            speak_text(target_s)
            print(f"\n{GREEN}{BOLD}>>> REPITA EM VOZ ALTA AGORA! (15s — Ctrl+C ao terminar) <<<{RESET}")
            sh_path = os.path.join(tempfile.gettempdir(), "det_shadow_quick.wav")
            if record_mic_clip(sh_path, 15, "Shadowing"):
                if get_gemini_key():
                    print(f"{CYAN}🤖 Avaliando sua pronúncia e ritmo na frase-modelo...{RESET}")
                    sh_sys = (
                        "Você é um Coach de Pronúncia e Prosódia do DET. O aluno acabou de fazer Shadowing da frase-alvo.\n"
                        "Forneça um feedback curto e direto (máximo 8 linhas):\n"
                        "1. 🎙️ Transcrição do que foi ouvido vs. Frase-Alvo\n"
                        "2. 🎯 Precisão Fonética (0 a 100%) e palavras que precisam de ajuste (com pronúncia figurada para brasileiros)\n"
                        "3. ⚡ Ritmo, linking sounds e entonação."
                    )
                    sh_fb = analyze_audio_with_gemini(sh_path, f"Target Sentence: {target_s}", custom_sys_inst=sh_sys)
                    if sh_fb:
                        print(f"\n{GREEN}── FEEDBACK DE SHADOWING ──{RESET}\n{sh_fb}")
        elif act == "r":
            print(f"\n{GREEN}{BOLD}>>> SECOND SHOT (60s): FALE SUA RESPOSTA REFINADA AGORA! <<<{RESET}")
            ss_path = os.path.join(tempfile.gettempdir(), "det_second_shot.wav")
            if record_mic_clip(ss_path, 60, "Second Shot"):
                if get_gemini_key():
                    print(f"{CYAN}🤖 Avaliando sua evolução na 2ª tentativa (Second Shot)...{RESET}")
                    ss_fb = analyze_audio_with_gemini(
                        ss_path,
                        f"SECOND SHOT ATTEMPT for prompt: {prompt}",
                        image_path=photo_path
                    )
                    if ss_fb:
                        print(f"\n{BOLD}{GREEN}🏆 AVALIAÇÃO DO SEU SECOND SHOT:{RESET}\n{ss_fb}")
                        c_sc, p_sc = extract_eval_scores(ss_fb, default_conv=90, default_prod=90)
                        record_skill_score("conversation", c_sc)
                        record_skill_score("production", p_sc)
                        print_speaking_coach_scorecard(c_sc, p_sc, mode_label="SECOND SHOT (REFINAMENTO)")


def run_speak_about_photo_official():
    """Official DET 'Speak About the Photo' Simulator (20s prep + 90s speaking + Multimodal Image & Audio evaluation)."""
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 8C: SPEAK ABOUT THE PHOTO — SIMULADOR OFICIAL (20s Prep + 90s Fala)]{RESET}")
    print(f"{DIM}Descreva a fotografia em voz alta por até 90 segundos usando a estrutura T-I-T (Visão Geral ➔ Planos ➔ Atmosfera/Hipótese).{RESET}\n")

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    unseen_live = get_unseen_live_photos()
    chosen_file = random.choice(unseen_live) if unseen_live else fetch_dynamic_real_photo()

    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    photo_files = [f for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(valid_exts)]
    if not photo_files:
        print(f"{RED}Nenhuma foto encontrada em {PHOTOS_DIR}.{RESET}")
        input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")
        return

    if not chosen_file:
        unseen_any = [f for f in photo_files if not is_item_seen("photo_speak", f)]
        chosen_file = random.choice(unseen_any) if unseen_any else random.choice(photo_files)
    mark_item_seen("photo_speak", chosen_file)

    photo_path = os.path.join(PHOTOS_DIR, chosen_file)
    photo_title = chosen_file.rsplit(".", 1)[0].replace("_", " ").title()
    mission = get_c1_lexical_mission(3)

    print_c1_mission_banner(mission)
    print(f"{BOLD}📐 Dica de Estrutura T-I-T para falar por 90s sem travar:{RESET}")
    print(f"  • {GREEN}[T]{RESET} This photograph captures a candid scene of [quem/o quê + -ing] in [ambiente]...")
    print(f"  • {GREEN}[I]{RESET} In the foreground, we can observe [...], whereas the background reveals [...]")
    print(f"  • {GREEN}[T]{RESET} The natural lighting conveys a sense of [...], suggesting that [...]\n")

    input(f"{GREEN}Pressione [ENTER] para abrir a foto e iniciar os 20s de PREPARAÇÃO...{RESET}")

    viewer_candidates = [
        os.path.join(SCRIPT_DIR, "det_photo_viewer.py"),
        os.path.join(SCRIPT_DIR, "det-photo-viewer"),
        os.path.expanduser("~/.local/bin/det-photo-viewer")
    ]
    viewer_tool = next((p for p in viewer_candidates if os.path.exists(p)), None)
    viewer_proc = None
    if viewer_tool:
        try:
            viewer_proc = subprocess.Popen(
                [sys.executable, viewer_tool, photo_path, "115", f"SPEAK ABOUT THE PHOTO: {photo_title}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    try:
        for remaining in range(20, 0, -1):
            print(f"\r{YELLOW}Observe a foto e planeje sua fala: {remaining:02d}s restantes...{RESET}", end="", flush=True)
            time.sleep(1)

        print(f"\a\n\n{GREEN}{BOLD}>>> DESCREVA A FOTO EM VOZ ALTA AGORA! MICROFONE ATIVO (90s) <<<{RESET}")
        print(f"{DIM}(Pressione [Ctrl+C] se terminar de falar antes dos 90 segundos){RESET}\n")

        audio_rec_path = os.path.join(tempfile.gettempdir(), "det_speak_photo_rec.wav")
        captured = record_mic_clip(audio_rec_path, 90, "Speak About Photo")
    finally:
        if viewer_proc:
            try:
                viewer_proc.terminate()
            except Exception:
                pass

    if captured and get_gemini_key():
        print(f"\n{CYAN}🤖 Enviando a FOTO REAL + SUA VOZ para o Google Gemini Multimodal...{RESET}")
        photo_sys = (
            "Você é um Examinador Sênior Oficial do Duolingo English Test (DET) avaliando a tarefa 'Speak About the Photo' (90 segundos).\n"
            "Você está recebendo a IMAGEM REAL da questão e o ÁUDIO da fala do candidato.\n"
            "Estruture sua avaliação em:\n"
            "1. 🎙️ TRANSCRIÇÃO EXATA DA FALA:\n"
            "2. 👁️ PRECISÃO VISUAL & DETALHAMENTO (O candidato descreveu elementos reais do primeiro plano, fundo, ação e atmosfera da foto? O que faltou mencionar?):\n"
            "3. ⚡ FLUÊNCIA, PRONÚNCIA & PROSÓDIA (Ritmo, pausas e palavras pronunciadas incorretamente com dica fonética):\n"
            "4. 📝 GRAMÁTICA & VOCABULÁRIO C1 (Correções das frases faladas):\n"
            "5. ✨ RESPOSTA MODELO B2/C1 FALADA (Usando a estrutura T-I-T fiel à foto):\n"
            "   Inclua também a frase-destaque em uma linha única após o marcador EXATO 'SPEAK_MODEL: '.\n"
            "Ao final absoluto, inclua obrigatoriamente:\n"
            "[DET_EVAL: CONVERSATION=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )
        ai_feedback = analyze_audio_with_gemini(
            audio_rec_path,
            f"Speak About the Photo ({photo_title})",
            image_path=photo_path,
            custom_sys_inst=photo_sys
        )
        if ai_feedback:
            print(f"\n{BOLD}{CYAN}AVALIAÇÃO MULTIMODAL (FOTO + VOZ — SPEAK ABOUT THE PHOTO):{RESET}")
            print(ai_feedback)
            evaluate_c1_mission_and_cliches(ai_feedback, mission)

            conv_score, prod_score = extract_eval_scores(ai_feedback)
            record_skill_score("conversation", conv_score)
            record_skill_score("production", prod_score)
            print_speaking_coach_scorecard(conv_score, prod_score, mode_label="SPEAK ABOUT THE PHOTO (90s)")

            model_s = _extract_speak_model_sentence(ai_feedback)
            push_to_anki(
                subdeck_name="Speaking Feedback",
                front_html=f"<b>[DET: Speak About the Photo]</b><br><br><b>Tema da Foto:</b> {photo_title}",
                back_html=f"<h3>Análise Multimodal ({conv_score}/160):</h3><div style='text-align:left;'>{ai_feedback.replace(chr(10), '<br>')}</div>",
                tags=["DET", "DET_SpeakPhoto"],
                audio_text=model_s or None
            )
            print(f"\n{YELLOW}📥 Card com feedback e áudio modelo enviado ao Anki!{RESET}")
            _offer_speaking_second_shot(f"Speak About the Photo: {photo_title}", ai_feedback, photo_path=photo_path)

    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")


def run_speaking_drill(force_ai=True):
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 8: SPEAKING SIMULATOR OFICIAL DET (90s)]{RESET}")
    print("Escolha a modalidade oficial de fala do DET que deseja simular:")
    print(f"  {BOLD}1){RESET} Read, Then Speak    {DIM}(Pergunta escrita visível na tela - 20s prep / 90s fala){RESET}")
    print(f"  {BOLD}2){RESET} Listen, Then Speak  {DIM}(Pergunta cega apenas em áudio - 20s prep / 90s fala){RESET}")
    print(f"  {BOLD}3){RESET} Speak About Photo   {DIM}(Fotografia real na tela + descrição falada em 90s){RESET}")
    print(f"  {BOLD}4){RESET} Ir para o {MAGENTA}{BOLD}Speaking Coach & Fluency Gym{RESET} {DIM}(Treino passo a passo p/ destravar){RESET}")
    try:
        mode_choice = input(f"\n{CYAN}Modalidade [1-4, padrão=1]: {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        return
    if mode_choice == "3":
        run_speak_about_photo_official()
        return
    if mode_choice == "4":
        run_speaking_coach()
        return
    blind_audio_mode = (mode_choice == "2")

    prompt = None
    if force_ai:
        prompt = get_unseen_speaking_prompt()
        if prompt:
            print(f"{GREEN}⚡ Pergunta inédita carregada do lote local (0ms / 0 requisição)!{RESET}")
        elif get_gemini_key():
            print(f"{CYAN}🤖 Gerando lote de perguntas de fala inéditas via IA...{RESET}")
            prompt = generate_dynamic_speaking_prompt_ai(4)
            if prompt:
                print(f"{GREEN}✓ Lote de perguntas gerado via IA!{RESET}")
            else:
                print(f"{YELLOW}⚠️ Não foi possível gerar pergunta via IA. Usando tema do banco...{RESET}")
        else:
            print(f"{YELLOW}⚠️ Chave do Gemini não configurada. Usando tema do banco...{RESET}")

    if not prompt:
        prompt = get_random_speaking_prompt_pool()

    mark_item_seen("speaking", prompt)
    mission = get_c1_lexical_mission(3)
    print()
    print_c1_mission_banner(mission)

    if blind_audio_mode:
        print(f"{BOLD}{YELLOW}🎧 MODO LISTEN, THEN SPEAK (Pergunta Cega em Áudio):{RESET}")
        print(f"{DIM}O texto da pergunta ficará oculto até você terminar de falar!{RESET}")
        replays = 2
        print(f"\n{CYAN}🔊 Reproduzindo pergunta em áudio...{RESET}")
        speak_text(prompt)
        while replays > 0:
            try:
                rep_q = input(f"Digite 'r' para ouvir a pergunta novamente ({replays} restantes) ou [ENTER] para iniciar os 20s de preparo: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return
            if rep_q == "r":
                replays -= 1
                speak_text(prompt)
            else:
                break
    else:
        print(f"{BOLD}PROMPT DE FALA:{RESET}")
        print(f"{YELLOW}{prompt}{RESET}\n")
        print("Estrutura recomendada (A-P-F-U adaptada para 90s de fala):")
        print("  1. Tese direta: 'Although..., I contend that...' (20s)")
        print("  2. Mecanismo + Exemplo: 'Primarily, this is because... For instance...' (45s)")
        print("  3. Conclusão: 'Ultimately, provided that...' (25s)\n")
        input(f"{GREEN}Pressione [ENTER] para iniciar os 20s de PREPARAÇÃO mental...{RESET}")

    for remaining in range(20, 0, -1):
        print(f"\r{YELLOW}Preparação: {remaining:02d}s restantes...{RESET}", end="", flush=True)
        time.sleep(1)

    print(f"\a\n\n{GREEN}{BOLD}>>> COMECE A FALAR AGORA! MICROFONE ATIVO! <<<{RESET}\n")
    print(f"{DIM}(Se terminar antes dos 90 segundos, pressione [Ctrl+C] para encerrar e enviar para análise){RESET}\n")

    audio_rec_path = os.path.join(tempfile.gettempdir(), "det_speaking_rec.wav")
    captured = record_mic_clip(audio_rec_path, 90, "Gravando áudio")

    print(f"\a\n{CYAN}{BOLD}ÁUDIO CAPTURADO COM SUCESSO!{RESET}")
    if blind_audio_mode:
        print(f"\n{BOLD}📜 Revelando a Pergunta Auditiva Original:{RESET}")
        print(f"{YELLOW}{prompt}{RESET}")

    gemini_key = get_gemini_key()
    if gemini_key and captured:
        print(f"\n{CYAN}🤖 Enviando seu áudio para a IA do Google Gemini (Análise Multimodal)...{RESET}")
        ai_feedback = analyze_audio_with_gemini(audio_rec_path, prompt)
        if ai_feedback:
            print(f"\n{BOLD}{CYAN}AVALIAÇÃO DA BANCA DET (SPEAKING):{RESET}")
            print(ai_feedback)
            evaluate_c1_mission_and_cliches(ai_feedback, mission)

            model_s = _extract_speak_model_sentence(ai_feedback)
            front = f"<b>[DET: Speaking Simulator]</b><br><br><b>Pergunta:</b> {prompt}<br><br><i>[Feedback da sua fala]</i>"
            back = f"<h3>Análise da IA:</h3><div style='text-align:left;'>{ai_feedback.replace(chr(10), '<br>')}</div>"
            push_to_anki(
                subdeck_name="Speaking Feedback",
                front_html=front,
                back_html=back,
                tags=["DET", "DET_Speaking"],
                audio_text=model_s or None
            )
            print(f"\n{YELLOW}📥 Análise de fala enviada ao Anki em segundo plano!{RESET}")

            conv_score, prod_score = extract_eval_scores(ai_feedback)
            record_skill_score("conversation", conv_score)
            record_skill_score("production", prod_score)
            print_speaking_coach_scorecard(conv_score, prod_score, mode_label="SPEAKING SIMULATOR (90s)")
            _offer_speaking_second_shot(prompt, ai_feedback)
        else:
            record_skill_progress(["conversation", "production"], 0, 1)
    else:
        print("Checklist de autoavaliação:")
        print("  [ ] Você falou sem pausas silenciosas maiores que 3 segundos?")
        print("  [ ] Usou conectivos como 'for instance', 'moreover', 'ultimately'?")
        print("  [ ] Falou até perto do fim do tempo?")
        record_skill_progress(["conversation", "production"], 0, 1)

    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 9. WRITE ABOUT THE PHOTO (DYNAMIC UNSEEN REAL PHOTOS + MULTIMODAL + C1 MISSION)
# ==============================================================================
DET_PHOTO_THEMES = [
    ("scientist working laboratory", "Scientific Laboratory Research"),
    ("street market vendor customers", "Bustling Outdoor Market"),
    ("students studying university library", "Academic Library Study"),
    ("chef cooking restaurant kitchen", "Professional Culinary Kitchen"),
    ("commuters busy train station", "Urban Public Transit"),
    ("construction workers building site", "Architecture & Construction"),
    ("farmers harvesting crops field", "Agricultural Harvesting"),
    ("musicians performing street concert", "Live Musical Performance"),
    ("doctor nurse hospital patient", "Clinical Healthcare Setting"),
    ("carpenter woodworking workshop", "Artisan Woodworking Studio"),
    ("family picnic outdoor park", "Outdoor Leisure & Community"),
    ("fisherman boat harbor nets", "Maritime Harbor & Fishing"),
    ("cyclists riding urban street", "Sustainable Urban Mobility"),
    ("passengers airport terminal luggage", "International Aviation Terminal"),
    ("barista preparing coffee cafe", "Modern Café Culture"),
    ("archaeologists digging excavation", "Archaeological Fieldwork"),
    ("children playing school playground", " Childhood Recreation"),
    ("artist painting canvas studio", "Fine Arts Workshop"),
    ("engineers inspecting wind turbine", "Renewable Energy Engineering"),
    ("firefighters emergency rescue", "Emergency Response Team"),
    ("bakers kneading dough bakery", "Traditional Artisan Bakery"),
    ("hikers mountain trail backpack", "Alpine Expedition & Nature"),
    ("mechanic repairing car garage", "Automotive Engineering Workshop"),
    ("orchestra conductor rehearsal", "Symphony Orchestra Rehearsal"),
    ("potter shaping clay wheel", "Ceramic Craftsmanship"),
    ("librarian organizing bookshelves", "Information & Archival Science"),
    ("florist arranging flowers shop", "Botanical & Floral Design"),
    ("photographers nature wildlife", "Wildlife Photography Fieldwork"),
    ("sailors sailboat ocean waves", "Maritime Navigation"),
    ("robotics engineer prototype", "Robotics & Mechatronics Lab")
]

def fetch_dynamic_real_photo():
    """Fetches a brand-new, unseen real documentary photograph from Wikimedia Commons / Unsplash Picsum (0 Gemini API cost)."""
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    catalog = {}
    if os.path.exists(PHOTO_CATALOG_FILE):
        try:
            with open(PHOTO_CATALOG_FILE, "r", encoding="utf-8") as f:
                catalog = json.load(f)
        except Exception:
            catalog = {}

    existing_files = set(os.listdir(PHOTOS_DIR))
    theme_query, scene_label = random.choice(DET_PHOTO_THEMES)

    # 1. Try Wikimedia Commons Thematic Documentary Photo Search
    try:
        api_url = (
            "https://commons.wikimedia.org/w/api.php?action=query&generator=search"
            f"&gsrsearch={urllib.parse.quote('filetype:bitmap ' + theme_query)}"
            "&gsrnamespace=6&gsrlimit=18&prop=imageinfo&iiprop=url|dimensions|mime&iiurlwidth=960&format=json"
        )
        req = urllib.request.Request(api_url, headers={"User-Agent": "DETDrillSuite/2.0 (Academic Preparation)"})
        with urllib.request.urlopen(req, timeout=4.0) as r:
            data = json.loads(r.read().decode("utf-8"))

        pages = list(data.get("query", {}).get("pages", {}).values())
        random.shuffle(pages)
        for p in pages:
            ii = (p.get("imageinfo") or [{}])[0]
            mime = ii.get("mime", "")
            thumb = ii.get("thumburl") or ii.get("url")
            w = ii.get("width", 0)
            h = ii.get("height", 0)
            if mime not in ["image/jpeg", "image/png"] or not thumb or w < 500 or h < 350:
                continue

            raw_title = p.get("title", "").replace("File:", "").rsplit(".", 1)[0]
            clean_slug = re.sub(r"[^a-zA-Z0-9]+", "_", raw_title.lower()).strip("_")[:36]
            url_hash = hashlib.md5(thumb.encode("utf-8")).hexdigest()[:8]
            ext = ".png" if mime == "image/png" else ".jpg"
            fname = f"live_{url_hash}_{clean_slug}{ext}"

            if fname in existing_files or is_item_seen("photo", fname):
                continue

            req_img = urllib.request.Request(thumb, headers={"User-Agent": "DETDrillSuite/2.0"})
            with urllib.request.urlopen(req_img, timeout=4.0) as ri:
                img_bytes = ri.read()

            if len(img_bytes) > 12000:
                target_path = os.path.join(PHOTOS_DIR, fname)
                with open(target_path, "wb") as out_f:
                    out_f.write(img_bytes)

                human_title = re.sub(r"[_\\-]+", " ", raw_title).strip().title()[:65]
                catalog[fname] = {
                    "title": human_title or scene_label,
                    "scene_type": scene_label,
                    "key_elements": [
                        f"Subject activity and environment ({scene_label})",
                        "Foreground subjects, posture, and interactions",
                        "Background context, lighting, and atmosphere"
                    ],
                    "useful_vocabulary": ["in the foreground", "in the background", "engaged in", "surrounded by", "suggesting that"]
                }
                try:
                    with open(PHOTO_CATALOG_FILE, "w", encoding="utf-8") as cf:
                        json.dump(catalog, cf, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                return fname
    except Exception:
        pass

    # 2. Fallback: High-res real photo from Unsplash Picsum
    try:
        req = urllib.request.Request("https://picsum.photos/960/640", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4.0) as r:
            img_bytes = r.read()
            final_url = r.geturl()
        if len(img_bytes) > 10000:
            url_hash = hashlib.md5(final_url.encode("utf-8")).hexdigest()[:10]
            fname = f"live_unsplash_{url_hash}.jpg"
            if fname not in existing_files:
                target_path = os.path.join(PHOTOS_DIR, fname)
                with open(target_path, "wb") as out_f:
                    out_f.write(img_bytes)
                catalog[fname] = {
                    "title": f"Documentary Scene #{url_hash[:5].upper()}",
                    "scene_type": "Real Documentary Photograph",
                    "key_elements": ["Main visual subject and setting", "Lighting, composition, and depth", "Implied context or action"],
                    "useful_vocabulary": ["in the foreground", "in the background", "bathed in", "conveying a sense of"]
                }
                try:
                    with open(PHOTO_CATALOG_FILE, "w", encoding="utf-8") as cf:
                        json.dump(catalog, cf, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                return fname
    except Exception:
        pass
    return None

def get_unseen_live_photos():
    """Returns a list of dynamically fetched real photos (live_*) that the student hasn't practiced yet."""
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    all_files = [f for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(valid_exts)]
    unseen_live = [f for f in all_files if f.startswith("live_") and not is_item_seen("photo", f)]
    return unseen_live

def run_photo_writing():
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 9: WRITE ABOUT THE PHOTO (1 MINUTO - FOTOS REAIS INÉDITAS)]{RESET}")
    print(f"{DIM}Fotografias documentais reais inéditas avaliadas com Visão Computacional Multimodal.{RESET}\n")

    os.makedirs(PHOTOS_DIR, exist_ok=True)

    # 1. Check for pre-fetched unseen dynamic real photos first (0ms latency)
    unseen_live = get_unseen_live_photos()
    chosen_file = None
    if unseen_live:
        chosen_file = random.choice(unseen_live)
        print(f"{GREEN}⚡ Fotografia real inédita carregada do buffer local (0ms)!{RESET}\n")
    else:
        print(f"{CYAN}📸 Baixando uma fotografia documental real e inédita para o seu treino...{RESET}")
        chosen_file = fetch_dynamic_real_photo()
        if chosen_file:
            print(f"{GREEN}✓ Nova fotografia real baixada com sucesso!{RESET}\n")
        else:
            print(f"{YELLOW}⚠️ Sem conexão no momento. Selecionando fotografia do acervo local...{RESET}\n")

    catalog = {}
    if os.path.exists(PHOTO_CATALOG_FILE):
        try:
            with open(PHOTO_CATALOG_FILE, "r", encoding="utf-8") as f:
                catalog = json.load(f)
        except Exception:
            catalog = {}

    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    photo_files = [f for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(valid_exts)]

    if not photo_files:
        print(f"{RED}Nenhuma foto encontrada em {PHOTOS_DIR}.{RESET}")
        input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")
        return

    if not chosen_file:
        unseen_any = [f for f in photo_files if not is_item_seen("photo", f)]
        chosen_file = random.choice(unseen_any) if unseen_any else random.choice(photo_files)

    mark_item_seen("photo", chosen_file)

    photo_path = os.path.join(PHOTOS_DIR, chosen_file)
    meta = catalog.get(chosen_file, {
        "title": chosen_file.rsplit(".", 1)[0].replace("_", " ").title(),
        "scene_type": "Real Photo Scene",
        "key_elements": ["Visual scene subject and environment", "Lighting and atmosphere", "Foreground and background details"],
        "useful_vocabulary": ["in the foreground", "in the background", "bathed in", "suggesting that"],
        "sample_c1": ""
    })

    photo_title = meta.get("title", chosen_file)
    scene_type = meta.get("scene_type", "General Scene")
    key_elements = meta.get("key_elements", [])
    useful_vocab = meta.get("useful_vocabulary", [])
    mission = get_c1_lexical_mission(3)

    print(f"{BOLD}CENÁRIO SELECIONADO:{RESET} {CYAN}{photo_title}{RESET} ({scene_type})")
    print(f"{DIM}Arquivo: {photo_path}{RESET}\n")
    print_c1_mission_banner(mission)
    print("Objetivo DET:")
    print("  • Uma janela externa será aberta com a foto e o cronômetro oficial de 60s.")
    print("  • Escreva de 1 a 3 frases completas descrevendo a imagem com precisão acadêmica (25-45 palavras).\n")

    input(f"{GREEN}Pressione [ENTER] para abrir a foto e iniciar os 60 segundos...{RESET}")

    viewer_candidates = [
        os.path.join(SCRIPT_DIR, "det_photo_viewer.py"),
        os.path.join(SCRIPT_DIR, "det-photo-viewer"),
        os.path.expanduser("~/.local/bin/det-photo-viewer")
    ]
    viewer_tool = next((p for p in viewer_candidates if os.path.exists(p)), None)
    viewer_proc = None
    if viewer_tool:
        try:
            viewer_proc = subprocess.Popen(
                [sys.executable, viewer_tool, photo_path, "60", photo_title],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass
    if not viewer_proc:
        try:
            if IS_WINDOWS:
                os.startfile(photo_path)
            else:
                open_cmd = "open" if IS_MACOS else "xdg-open"
                viewer_proc = subprocess.Popen(
                    [open_cmd, photo_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception:
            pass

    print(f"\n{GREEN}✓ Janela da foto aberta na tela!{RESET}")
    print(f"{YELLOW}Acompanhe o cronômetro na janela e digite sua descrição abaixo:{RESET}\n")

    try:
        user_input = input(f"{BOLD}Sua descrição: {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        if viewer_proc:
            try:
                viewer_proc.terminate()
            except Exception:
                pass
        return
    finally:
        if viewer_proc:
            try:
                viewer_proc.terminate()
            except Exception:
                pass

    words = len(user_input.split())
    print(f"\n• Total de palavras: {BOLD}{words}{RESET} (Alvo: 25-45 palavras)")
    evaluate_c1_mission_and_cliches(user_input, mission)

    gemini_key = get_gemini_key()
    scored_by_ai = False
    if gemini_key and words > 4:
        print(f"\n{CYAN}🤖 Enviando imagem real + sua descrição para o Gemini Multimodal...{RESET}")

        elements_str = ", ".join(key_elements) if key_elements else "elementos visuais da imagem anexada"
        vocab_str = ", ".join(useful_vocab) if useful_vocab else ""

        prompt = (
            f"Você é um Examinador Sênior do Duolingo English Test (DET) avaliando a questão 'Write About the Photo'.\n"
            f"Inspecione visualmente a imagem anexada (Título: {photo_title}, Cena: {scene_type}, Elementos: {elements_str}, Vocabulário sugerido: {vocab_str}).\n\n"
            f"RESPOSTA FORMULADA PELO CANDIDATO ({words} palavras):\n"
            f"\"{user_input}\"\n\n"
            f"Elabore uma avaliação pedagógica de alto nível, construtiva e prática, formatada nas seguintes 4 seções claras:\n"
            f"1. 🎯 O QUE VOCÊ FEZ BEM & PRECISÃO VISUAL:\n"
            f"Destaque acertos gramaticais e o quão bem a descrição corresponde aos elementos reais da foto.\n\n"
            f"2. 🔍 O QUE EXPLORAR NA IMAGEM & CORREÇÕES:\n"
            f"Aponte correções diretas e detalhes visuais reais desta imagem (foreground/background, iluminação, ações) que elevariam a nota.\n\n"
            f"3. ✨ VERSÃO REFINADA C1 / MODELO DE RESPOSTA (2 a 3 frases completas em inglês):\n"
            f"Apresente um modelo de resposta denso, natural e acadêmico para o padrão 105-125+ do DET.\n\n"
            f"4. 📚 VOCABULÁRIO & CONECTIVOS DE ALTO IMPACTO:\n"
            f"Liste 3 expressões avançadas em inglês aplicáveis a esta foto.\n\n"
            f"IMPORTANTE: Ao final absoluto da sua mensagem, inclua obrigatoriamente a tag de pontuação:\n"
            f"[DET_EVAL: LITERACY=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )

        resp = analyze_image_with_gemini(photo_path, prompt)
        if resp:
            print(f"\n{GREEN}{BOLD}═════════════════════════════════════════════════════════════════{RESET}")
            print(f"{GREEN}{BOLD}📋 AVALIAÇÃO MULTIMODAL DET & DESENVOLVIMENTO DA IMAGEM:{RESET}")
            print(f"{GREEN}{BOLD}═════════════════════════════════════════════════════════════════{RESET}\n")
            print(resp)
            print(f"\n{GREEN}{BOLD}═════════════════════════════════════════════════════════════════{RESET}\n")

            lit_score, prod_score = extract_writing_scores(resp)
            record_skill_score("literacy", lit_score)
            record_skill_score("production", prod_score)
            scored_by_ai = True
            print(f"{BOLD}📊 Subscores Oficiais Registrados no Dashboard DET:{RESET}")
            print(f"  • Literacy:   {CYAN}{lit_score}/160 pts{RESET}")
            print(f"  • Production: {CYAN}{prod_score}/160 pts{RESET}\n")

            audio_text = user_input
            lines = resp.split("\n")
            for i, line in enumerate(lines):
                if "VERSÃO REFINADA" in line.upper() or "MODELO" in line.upper():
                    for next_line in lines[i+1:i+6]:
                        clean_line = next_line.strip()
                        if clean_line and not clean_line.startswith("#") and not clean_line.startswith("4."):
                            audio_text = clean_line
                            break
                    break

            front = (
                f"<b>[DET: Write About the Photo]</b><br><br>"
                f"📸 <b>Cenário:</b> {photo_title} (<i>{scene_type}</i>)<br><br>"
                f"<b>Sua resposta:</b> {user_input}"
            )
            back = (
                f"<h3>Análise Multimodal ({lit_score}/160):</h3>"
                f"<div style='text-align: left; font-size: 15px; line-height: 1.5;'>"
                f"{resp.replace(chr(10), '<br>')}"
                f"</div>"
            )
            push_to_anki(
                subdeck_name="Writing Upgrades",
                front_html=front,
                back_html=back,
                tags=["DET", "DET_Photo", "WriteAboutPhoto"],
                audio_text=audio_text
            )
            print(f"{YELLOW}📥 Card de enriquecimento com áudio C1 enviado ao Anki em segundo plano!{RESET}")

            # Frente 2: Active Recall C1 Rewrite
            try:
                rewrite = input(f"\n{MAGENTA}{BOLD}✍️  FIXAÇÃO ATIVA C1:{RESET} Reescreva 1 frase aplicando um upgrade sugerido (ou [ENTER] para pular): ").strip()
                if rewrite:
                    print(f"{GREEN}✓ Excelente prática de consolidação ativa ({len(rewrite.split())} palavras)!{RESET}")
            except (KeyboardInterrupt, EOFError):
                pass
    elif words <= 4:
        print(f"{YELLOW}⚠️ Resposta muito curta para análise aprofundada (escreva pelo menos 1 frase completa).{RESET}")

    if not scored_by_ai:
        record_skill_progress(["literacy", "production"], 1 if words >= 25 else 0, 1)
    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 10. INTERACTIVE LISTENING + SUMMARIZE THE CONVERSATION (75s) [FRENTE 4]
# ==============================================================================
INTERACTIVE_LISTENING_BANK = [
    {
        "title": "Graduate Thesis Methodology Consultation",
        "scenario": "You are meeting with your thesis advisor, Dr. Evans, to discuss a sampling bias issue in your master's research dataset.",
        "turns": [
            {
                "speaker": "Professor Evans",
                "audio": "I reviewed your preliminary dataset, and I noticed that urban respondents are significantly overrepresented compared to rural participants.",
                "options": [
                    "I noticed that discrepancy as well. Would you recommend applying stratified weighting or extending our data collection in rural districts?",
                    "That is not a problem because statistics do not matter in graduate school.",
                    "I think I will cancel my registration in the university immediately.",
                    "Did you watch the basketball game on television last night?"
                ],
                "answer": 0,
                "explanation": "Demonstra postura acadêmica adequada, reconhecendo o viés amostral e propondo duas soluções metodológicas."
            },
            {
                "speaker": "Professor Evans",
                "audio": "Extending data collection would delay your defense deadline. Applying post-stratification weights is much more feasible given our timeline, provided you document the limitation transparently.",
                "options": [
                    "That makes complete sense. I will recalculate the demographic weights and add a methodological limitation subsection to chapter three.",
                    "I refuse to write chapter three because it takes too much effort.",
                    "Can you write the entire thesis for me by tomorrow morning?",
                    "Rural participants do not use computers anyway."
                ],
                "answer": 0,
                "explanation": "Confirma a orientação do orientador com precisão técnica ('post-stratification weights' e seção de limitações)."
            },
            {
                "speaker": "Professor Evans",
                "audio": "Excellent. Send me the revised regression tables by Thursday so we can verify the confidence intervals before submitting to the committee.",
                "options": [
                    "Will do, Dr. Evans. I will email you the updated tables and confidence intervals by Thursday afternoon.",
                    "Thursday is my favorite day of the week to go shopping.",
                    "I deleted all the regression tables from my computer.",
                    "The committee does not read academic papers."
                ],
                "answer": 0,
                "explanation": "Encerra o diálogo confirmando o prazo (quinta-feira) e o entregável técnico (tabelas de regressão e intervalos de confiança)."
            }
        ],
        "model_summary": (
            "In this conversation, my thesis advisor and I discussed how to address a sampling bias in my research dataset where urban participants were overrepresented. "
            "Specifically, Professor Evans advised me to apply post-stratification weighting rather than collecting new data in order to meet my defense deadline, while transparently documenting the limitation. "
            "Ultimately, we agreed that I would recalculate the regression tables with updated confidence intervals and send them for review by Thursday."
        )
    }
]

def save_interactive_listening_to_archive(item):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        archive = []
        if os.path.exists(INTERACTIVE_LISTENING_ARCHIVE_FILE):
            with open(INTERACTIVE_LISTENING_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archive = json.load(f)
        if not any(entry.get("title") == item.get("title") for entry in archive):
            archive.append(item)
            with open(INTERACTIVE_LISTENING_ARCHIVE_FILE, "w", encoding="utf-8") as f:
                json.dump(archive, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_unseen_interactive_listening():
    if os.path.exists(INTERACTIVE_LISTENING_ARCHIVE_FILE):
        try:
            with open(INTERACTIVE_LISTENING_ARCHIVE_FILE, "r", encoding="utf-8") as f:
                archived = json.load(f)
                if isinstance(archived, list):
                    unseen = [i for i in archived if "turns" in i and not is_item_seen("interactive_listening", i)]
                    if unseen:
                        return random.choice(unseen)
        except Exception:
            pass
    return None

def generate_dynamic_interactive_listening_ai():
    """Generates a complete 3-turn academic dialogue + Summarize the Conversation task in ONE JSON call."""
    topic = random.choice(C_TEST_AI_TOPICS)
    weak_hint = get_weak_words_hint(3)
    prompt = (
        f"You are an expert Duolingo English Test (DET) designer creating an 'Interactive Listening + Summarize the Conversation' simulation at CEFR B2/C1.{weak_hint}\n"
        f"Create an academic university conversation (e.g. student and professor/advisor or research colleague) discussing a research challenge, lab experiment, or paper revision related to '{topic}'.\n\n"
        "Requirements:\n"
        "1. 'title': Short title of the academic conversation.\n"
        "2. 'scenario': 1-2 sentences setting the context and your role in the conversation.\n"
        "3. 'turns': Array of 3 dialogue turns. Each turn has:\n"
        "   - 'speaker': E.g. 'Professor Miller' or 'Dr. Chen'.\n"
        "   - 'audio': What the speaker says to you (16-26 words).\n"
        "   - 'correct_option': Your best academic/pragmatic reply (14-24 words).\n"
        "   - 'distractor_1': Plausible but overly casual or pragmatically inappropriate reply.\n"
        "   - 'distractor_2': Reply that misunderstands the speaker's academic advice.\n"
        "   - 'distractor_3': Irrelevant or contradictory reply.\n"
        "   - 'explanation': Brief explanation in Portuguese of why the correct option fits.\n"
        "4. 'model_summary': A 3-sentence C1 model summary following the official DET formula (Sentence 1: main topic discussed; Sentence 2: specific advice/solution proposed; Sentence 3: final agreement/next step).\n\n"
        "Respond ONLY with valid JSON:\n"
        "{\n"
        '  "title": "Title",\n'
        '  "scenario": "Context...",\n'
        '  "turns": [\n'
        '    {"speaker": "Professor X", "audio": "...", "correct_option": "...", "distractor_1": "...", "distractor_2": "...", "distractor_3": "...", "explanation": "..."}\n'
        "  ],\n"
        '  "model_summary": "In this conversation... Specifically... Ultimately..."\n'
        "}"
    )
    raw = call_gemini(prompt, json_mode=True, max_tokens=1500)
    if raw:
        try:
            cleaned = re.search(r"\{.*\}", raw, re.DOTALL)
            if cleaned:
                data = json.loads(cleaned.group(0))
                if all(k in data for k in ["title", "scenario", "turns", "model_summary"]) and len(data["turns"]) >= 3:
                    turns_out = []
                    for t in data["turns"][:3]:
                        sq = _shuffle_question_dict(t)
                        if sq:
                            sq["speaker"] = t.get("speaker", "Professor")
                            sq["audio"] = t.get("audio", "")
                            turns_out.append(sq)
                    if len(turns_out) == 3:
                        item = {
                            "title": data["title"].strip(),
                            "scenario": data["scenario"].strip(),
                            "turns": turns_out,
                            "model_summary": data["model_summary"].strip()
                        }
                        save_interactive_listening_to_archive(item)
                        return item
        except Exception:
            pass
    return None

def run_interactive_listening(force_ai=True):
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 10: INTERACTIVE LISTENING + SUMMARIZE THE CONVERSATION (75s)]{RESET}")
    print("• Parte 1: Ouça as falas do professor/colega e escolha a melhor resposta acadêmica (3 turnos).")
    print("• Parte 2: Escreva um resumo estruturado da conversa em 75 segundos (Alto peso em Conversation & Production!).\n")

    item = None
    if force_ai:
        item = get_unseen_interactive_listening()
        if item:
            print(f"{GREEN}⚡ Diálogo inédito carregado do buffer local (0ms / 0 requisição)!{RESET}\n")
        elif get_gemini_key():
            print(f"{CYAN}🤖 Solicitando à IA (Gemini) um cenário acadêmico de Interactive Listening...{RESET}")
            item = generate_dynamic_interactive_listening_ai()
            if item:
                print(f"{GREEN}✓ Simulador Interactive Listening gerado via IA!{RESET}\n")
            else:
                print(f"{YELLOW}⚠️ Não foi possível gerar via IA no momento. Carregando do banco...{RESET}\n")

    if not item:
        item = random.choice(INTERACTIVE_LISTENING_BANK)

    mark_item_seen("interactive_listening", item)

    print(f"{BOLD}CENÁRIO:{RESET} {CYAN}{item['title']}{RESET}")
    print(f"\"{item['scenario']}\"\n")
    input(f"{GREEN}Pressione [ENTER] para iniciar o diálogo...{RESET}")

    dialogue_transcript = []
    correct_turns = 0
    total_turns = len(item["turns"])

    for idx, turn in enumerate(item["turns"], 1):
        speaker = turn.get("speaker", "Professor")
        audio_line = turn.get("audio", "")
        print(f"\n{BOLD}{MAGENTA}── TURNO {idx}/{total_turns}: {speaker} está falando... ──{RESET}")
        speak_text(audio_line)

        while True:
            rep = input(f"{DIM}(Digite 'r' para ouvir novamente ou [ENTER] para ver as opções de resposta): {RESET}").strip().lower()
            if rep == "r":
                speak_text(audio_line)
            else:
                break

        print(f"\n{YELLOW}Escolha a melhor resposta para dar a {speaker}:{RESET}\n")
        for o_idx, opt in enumerate(turn["options"], 1):
            print(f"  {BOLD}{o_idx}){RESET} {opt}")

        while True:
            try:
                ans = input("\nSua resposta (1-4): ").strip()
            except (KeyboardInterrupt, EOFError):
                return
            if ans in ["1", "2", "3", "4"]:
                u_idx = int(ans) - 1
                break
            print("Digite 1, 2, 3 ou 4.")

        corr_opt = turn["options"][turn["answer"]]
        print(f"\n{DIM}Fala de {speaker}: \"{audio_line}\"{RESET}")
        if u_idx == turn["answer"]:
            print(f"{GREEN}✓ Resposta adequada!{RESET} {turn['explanation']}")
            correct_turns += 1
        else:
            print(f"{RED}✗ Inadequado.{RESET} A resposta ideal era ({turn['answer']+1}): {BOLD}{corr_opt}{RESET}")
            print(f"{DIM}Por que: {turn['explanation']}{RESET}")

        dialogue_transcript.append(f"{speaker}: {audio_line}\nYou: {corr_opt}")

    # PART 2: SUMMARIZE THE CONVERSATION (75 SECONDS)
    print("\n" + "=" * 75)
    print(f"{BOLD}{MAGENTA}── PARTE 2: SUMMARIZE THE CONVERSATION (75 SEGUNDOS OFICIAIS) ──{RESET}")
    print("Fórmula de Ouro DET C1 (3 Frases):")
    print(f"  1. {CYAN}Contexto:{RESET}   \"In this conversation, my professor/colleague and I discussed...\"")
    print(f"  2. {CYAN}Conselho:{RESET}   \"Specifically, they advised/suggested that... in order to...\"")
    print(f"  3. {CYAN}Conclusão:{RESET}  \"Ultimately, we agreed that I would...\"")
    print("=" * 75)

    mission = get_c1_lexical_mission(3)
    print_c1_mission_banner(mission)

    input(f"{GREEN}Pressione [ENTER] para iniciar os 75 segundos do resumo...{RESET}")
    start_s = time.time()
    try:
        summary_input = input(f"\n{BOLD}Seu resumo (75s): {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        return
    elapsed_s = int(time.time() - start_s)
    s_words = len(summary_input.split())

    print(f"\n• Tempo utilizado: {BOLD}{elapsed_s}s / 75s{RESET} | Palavras: {BOLD}{s_words}{RESET} (Alvo: 40-70 palavras)")
    evaluate_c1_mission_and_cliches(summary_input, mission)

    full_dialogue_str = "\n\n".join(dialogue_transcript)
    if get_gemini_key() and s_words >= 8:
        print(f"\n{CYAN}🤖 Avaliando seu resumo com as rubricas oficiais de Summarize the Conversation...{RESET}")
        eval_prompt = (
            f"Scenario: {item['scenario']}\nDialogue Transcript:\n{full_dialogue_str}\n\n"
            f"Candidate's 75-second Summary ({s_words} words, {elapsed_s}s):\n\"{summary_input}\"\n\n"
            "Avalie em português como Examinador Oficial do DET:\n"
            "1. 🎯 COBERTURA DOS 3 PONTOS (Contexto, Solução/Conselho e Decisão Final).\n"
            "2. 📝 CORREÇÕES GRAMATICAIS & UPGRADES C1.\n"
            f"3. ✨ COMPARAÇÃO COM O MODELO C1:\n\"{item['model_summary']}\"\n\n"
            "Ao final absoluto, inclua obrigatoriamente:\n"
            "[DET_EVAL: CONVERSATION=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )
        ai_fb = call_gemini(eval_prompt)
        if ai_fb:
            print(f"\n{BOLD}{CYAN}AVALIAÇÃO DO RESUMO (GEMINI AI):{RESET}")
            print(ai_fb)
            c_sc, p_sc = extract_eval_scores(ai_fb, default_conv=90, default_prod=90)
            record_skill_score("conversation", c_sc)
            record_skill_score("production", p_sc)
            print(f"\n{BOLD}📊 Subscores Oficiais Registrados no Dashboard DET:{RESET}")
            print(f"  • Conversation: {CYAN}{c_sc}/160 pts{RESET} (Turnos: {correct_turns}/{total_turns})")
            print(f"  • Production:   {CYAN}{p_sc}/160 pts{RESET}")

            front = f"<b>[DET: Summarize the Conversation (75s)]</b><br><br><b>Cenário:</b> {item['scenario']}<br><br><b>Seu resumo:</b> {summary_input}"
            back = f"<h3>Modelo C1 Oficial:</h3><p style='color:#10b981;'><i>{item['model_summary']}</i></p><hr><div>{ai_fb.replace(chr(10), '<br>')}</div>"
            push_to_anki(
                subdeck_name="Interactive Listening",
                front_html=front,
                back_html=back,
                tags=["DET", "DET_InteractiveListening"],
                audio_text=item["model_summary"]
            )
            print(f"{YELLOW}📥 Card com modelo C1 e áudio enviado ao Anki em segundo plano!{RESET}")
    else:
        print(f"\n{GREEN}{BOLD}✨ MODELO DE RESUMO C1 OFICIAL:{RESET}")
        print(f"\"{item['model_summary']}\"")

    record_skill_progress(["comprehension", "conversation"], correct_turns, total_turns)
    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 11. WRITING COACH & SENTENCE BUILDER (SCAFFOLDED B1/PT -> C1 DESTRAVAR ESCRITA)
# ==============================================================================
def _run_scaffolded_essay_coach():
    header()
    print(f"\n{BOLD}{GREEN}[WRITING COACH: CONSTRUTOR DE REDAÇÃO 4 FRASES (PASSO A PASSO SEM PRESSÃO)]{RESET}")
    print(f"{DIM}Destrave a escrita quebrando o texto de 5 minutos em 4 blocos lógicos guiados.{RESET}")
    print(f"{DIM}💡 Dica: Se faltar uma palavra em inglês no meio da frase, escreva em PORTUGUÊS mesmo!{RESET}\n")

    prompt = get_unseen_writing_prompt()
    if not prompt and get_gemini_key():
        print(f"{CYAN}🤖 Gerando tema acadêmico inédito...{RESET}")
        prompt = generate_dynamic_writing_prompt_ai(4)
    if not prompt:
        prompt = get_random_writing_prompt_pool()
    mark_item_seen("writing", prompt)

    mission = get_c1_lexical_mission(3)

    print(f"{BOLD}TEMA DA REDAÇÃO:{RESET}")
    print(f"{YELLOW}{prompt}{RESET}\n")
    print_c1_mission_banner(mission)

    # Optional AI Idea Hints if user feels blank on arguments
    if get_gemini_key():
        try:
            want_hint = input(f"{CYAN}💡 Quer ver 2 ideias rápidas de argumentos (a favor/contra) antes de começar? [s/N]: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return
        if want_hint in ["s", "sim", "y", "yes"]:
            print(f"{CYAN}🤖 Gerando gatilhos de ideias para destravar seu argumento...{RESET}")
            hint_req = (
                f"Prompt: {prompt}\n\n"
                "Forneça em português um resumo ultra-curto (máximo 4 linhas) com:\n"
                "- Argumento Principal + Exemplo prático que o aluno pode usar\n"
                "- Contra-argumento / Cuidado necessário + 3 collocations em inglês (com tradução) específicas para este tema."
            )
            hint_resp = call_gemini(hint_req, max_tokens=280)
            if hint_resp:
                print(f"\n{MAGENTA}┌── GATILHOS DE ARGUMENTAÇÃO ──────────────────────────────────────────┐{RESET}")
                print(hint_resp.strip())
                print(f"{MAGENTA}└──────────────────────────────────────────────────────────────────────┘{RESET}\n")

    steps = [
        (
            "FRASE 1/4 — TESE + CONCESSÃO (Apresente os dois lados e sua posição)",
            "Although [benefício ou risco do tema], I contend that [sua opinião principal] because [motivo central].",
            "Ex: Although nanotechnology has unknown risks, I contend that its medical benefits outweigh the dangers because it saves lives."
        ),
        (
            "FRASE 2/4 — MECANISMO / CAUSA E EFEITO (Explique o 'porquê' do seu argumento)",
            "Primarily, this is because [como isso funciona na prática], which significantly [verbo: reduces / enhances / mitigates] [resultado].",
            "Ex: Primarily, this is because targeted nanoparticles attack only tumors, which significantly reduces damage to healthy cells."
        ),
        (
            "FRASE 3/4 — EXEMPLO CONCRETO OU CONTRASTE (Ancore com um caso real)",
            "For instance, in the field of [área/setor], [exemplo concreto ou consequência prática].",
            "Ex: For instance, in the field of oncology, patients recover much faster than with traditional chemotherapy."
        ),
        (
            "FRASE 4/4 — CONCLUSÃO CONDICIONAL / RECOMENDAÇÃO (Feche com chave de ouro)",
            "Ultimately, provided that governments enforce strict regulations to mitigate potential risks, [conclusão final].",
            "Ex: Ultimately, provided that governments enforce strict safety regulations, this technology will revolutionize modern medicine."
        )
    ]

    user_sentences = []
    for idx, (step_title, template_str, example_str) in enumerate(steps, 1):
        print(f"{BOLD}{CYAN}── {step_title} ──{RESET}")
        print(f"  📐 {BOLD}Esqueleto sugerido:{RESET} {GREEN}{template_str}{RESET}")
        print(f"  💬 {DIM}{example_str}{RESET}")
        print(f"  {DIM}(Pode usar o esqueleto acima e escrever em português qualquer palavra que não souber){RESET}")
        while True:
            try:
                ans = input(f"\n  ✍️  {BOLD}Sua Frase {idx}:{RESET} ").strip()
            except (KeyboardInterrupt, EOFError):
                return
            if ans:
                user_sentences.append(ans)
                print()
                break
            print(f"  {YELLOW}Digite pelo menos um rascunho da frase {idx} (mesmo em português/inglês simples).{RESET}")

    full_draft = " ".join(user_sentences)
    word_count = len(full_draft.split())

    print("=" * 70)
    print(f"{BOLD}📝 SEU TEXTO COMPLETO MONTADO ({word_count} palavras):{RESET}")
    print(f"{YELLOW}\"{full_draft}\"{RESET}")
    print("=" * 70)
    evaluate_c1_mission_and_cliches(full_draft, mission)
    breakdown = compute_local_writing_breakdown(full_draft, mission, target_words=80)
    scored_by_ai = False

    if get_gemini_key():
        print(f"\n{CYAN}🤖 Analisando suas 4 frases, calculando sua pontuação DET e construindo a ponte B2/C1...{RESET}")
        sys_inst = (
            "Você é um Coach de Escrita Acadêmica do Duolingo English Test (DET). "
            "O aluno construiu uma redação em 4 frases usando andaimes (podendo conter palavras em português ou inglês B1). "
            "Responda de forma prática e didática seguindo EXATAMENTE estas seções:\n"
            "0. 📊 DIAGNÓSTICO DE PONTUAÇÃO DO SEU RASCUNHO (Avalie o rascunho original do aluno na escala DET 10-160, "
            "dando nota para Estrutura/Argumentação, Gramática e Vocabulário, e dizendo quantos pontos ele ganha ao aplicar a versão C1).\n"
            "1. 🔄 PONTE FRASE POR FRASE (Para cada uma das 4 frases do aluno, mostre:\n"
            "   - Sua frase original\n"
            "   - Versão Corrigida Natural (B2 - mantendo exatamente a ideia do aluno e traduzindo qualquer trecho em português)\n"
            "   - Versão Acadêmica Elevada (C1 - padrão 115+ DET))\n"
            "2. 🏆 TEXTO UNIFICADO B2/C1 PRONTO PARA A PROVA (As 4 frases unidas em um parágrafo fluido de 100-130 palavras).\n"
            "3. 🎯 FRASE-CHAVE PARA FIXAÇÃO MOTORA: Escolha a frase mais importante corrigida e coloque-a sozinha após o marcador "
            "EXATO 'REWRITE_TARGET: ' em uma única linha.\n"
            "4. Ao final absoluto, inclua a tag: [DET_EVAL: LITERACY=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )
        numbered_draft = "\n".join([f"Sentence {i+1}: {s}" for i, s in enumerate(user_sentences)])
        ai_prompt = f"Prompt: {prompt}\n\nStudent's 4 Scaffolded Sentences:\n{numbered_draft}"
        ai_resp = call_gemini(ai_prompt, sys_inst)
        if ai_resp:
            print(f"\n{BOLD}{GREEN}══════════════════════════════════════════════════════════════════════{RESET}")
            print(f"{BOLD}{GREEN}🎓 COACHING FRASE POR FRASE (SEU RASCUNHO ➔ B2 ➔ C1):{RESET}")
            print(f"{BOLD}{GREEN}══════════════════════════════════════════════════════════════════════{RESET}\n")
            print(ai_resp)

            lit_score, prod_score = extract_writing_scores(
                ai_resp,
                default_lit=breakdown["local_lit"],
                default_prod=breakdown["local_prod"]
            )
            record_skill_score("literacy", lit_score)
            record_skill_score("production", prod_score)
            print_writing_coach_scorecard(lit_score, prod_score, breakdown, mode_label="REDAÇÃO 4 FRASES")
            scored_by_ai = True

            rewrite_target = ""
            for line in ai_resp.splitlines():
                if "REWRITE_TARGET:" in line:
                    rewrite_target = line.split("REWRITE_TARGET:", 1)[1].strip().strip('"')
                    break

            front = (
                f"<b>[DET Writing Coach: 4-Sentence Builder]</b><br><br>"
                f"<b>Prompt:</b> {prompt}<br><br>"
                f"<b>Seu Rascunho ({word_count} palavras):</b><br><pre>{full_draft}</pre>"
            )
            back = f"<h3>Upgrade Frase a Frase ({lit_score}/160):</h3><div style='text-align:left;'>{ai_resp.replace(chr(10), '<br>')}</div>"
            push_to_anki(
                subdeck_name="Writing Upgrades",
                front_html=front,
                back_html=back,
                tags=["DET", "DET_WritingCoach"],
                audio_text=rewrite_target or None
            )
            print(f"\n{YELLOW}📥 Card com o upgrade frase por frase enviado ao Anki em segundo plano!{RESET}")

            # Active Motor Memory Consolidation
            print(f"\n{MAGENTA}┌── ✍️  PASSO FINAL: MEMÓRIA MOTORA (CONSOLIDAÇÃO ATIVA) ───────────────┐{RESET}")
            if rewrite_target:
                print(f"  Para fixar a estrutura no cérebro, redigite em inglês a versão refinada abaixo:")
                print(f"  🎯 {GREEN}{BOLD}{rewrite_target}{RESET}")
            else:
                print(f"  Reescreva 1 das suas frases acima aplicando a correção B2/C1 que você aprendeu:")
            print(f"{MAGENTA}└──────────────────────────────────────────────────────────────────────┘{RESET}")
            try:
                typed = input(f"\n  ⌨️  {BOLD}Digite a frase refinada (ou [ENTER] para pular):{RESET} ").strip()
                if typed:
                    print(f"  {GREEN}{BOLD}✓ Excelente! Você acabou de treinar a memória muscular da estrutura C1!{RESET}")
            except (KeyboardInterrupt, EOFError):
                pass

    if not scored_by_ai:
        lit_score, prod_score = breakdown["local_lit"], breakdown["local_prod"]
        record_skill_score("literacy", lit_score)
        record_skill_score("production", prod_score)
        print_writing_coach_scorecard(lit_score, prod_score, breakdown, mode_label="REDAÇÃO 4 FRASES (LOCAL)")

    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")


def _run_scaffolded_photo_coach():
    header()
    print(f"\n{BOLD}{GREEN}[WRITING COACH: FÓRMULA DE 3 FRASES PARA FOTOS (SEM CRONÔMETRO)]{RESET}")
    print(f"{DIM}Aprenda a descrever qualquer foto em 3 camadas fixas: Visão Geral ➔ Planos ➔ Atmosfera/Hipótese.{RESET}\n")

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    unseen_live = get_unseen_live_photos()
    chosen_file = random.choice(unseen_live) if unseen_live else fetch_dynamic_real_photo()

    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    photo_files = [f for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(valid_exts)]
    if not photo_files:
        print(f"{RED}Nenhuma foto encontrada em {PHOTOS_DIR}.{RESET}")
        input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")
        return

    if not chosen_file:
        unseen_any = [f for f in photo_files if not is_item_seen("photo", f)]
        chosen_file = random.choice(unseen_any) if unseen_any else random.choice(photo_files)
    mark_item_seen("photo", chosen_file)

    photo_path = os.path.join(PHOTOS_DIR, chosen_file)
    photo_title = chosen_file.rsplit(".", 1)[0].replace("_", " ").title()
    mission = get_c1_lexical_mission(3)

    print_c1_mission_banner(mission)
    input(f"{GREEN}Pressione [ENTER] para abrir a foto (sem limite de tempo) e construir as 3 frases...{RESET}")

    viewer_candidates = [
        os.path.join(SCRIPT_DIR, "det_photo_viewer.py"),
        os.path.join(SCRIPT_DIR, "det-photo-viewer"),
        os.path.expanduser("~/.local/bin/det-photo-viewer")
    ]
    viewer_tool = next((p for p in viewer_candidates if os.path.exists(p)), None)
    viewer_proc = None
    if viewer_tool:
        try:
            viewer_proc = subprocess.Popen(
                [sys.executable, viewer_tool, photo_path, "300", f"COACH: {photo_title}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    photo_steps = [
        (
            "FRASE 1/3 — AÇÃO PRINCIPAL & CENÁRIO (O que a foto mostra no geral?)",
            "This photograph captures a [adjetivo] scene of [quem/o quê] [ação com -ing] in [lugar/ambiente].",
            "Ex: This photograph captures a candid scene of an artisan working diligently in a dimly lit workshop."
        ),
        (
            "FRASE 2/3 — PRIMEIRO PLANO vs. PLANO DE FUNDO (Contraste espacial)",
            "In the foreground, [detalhe da frente], whereas the background reveals [detalhe do fundo].",
            "Ex: In the foreground, wooden tools are scattered across a table, whereas the background reveals shelves full of pottery."
        ),
        (
            "FRASE 3/3 — ILUMINAÇÃO, ATMOSFERA & INFERÊNCIA (O que a cena transmite?)",
            "The natural lighting and composition convey a sense of [foco/calma/urgência], suggesting that [hipótese].",
            "Ex: The warm lighting conveys a sense of deep concentration, suggesting that the craftsman is finishing a delicate piece."
        )
    ]

    user_sentences = []
    try:
        print()
        for idx, (stitle, stemplate, sexample) in enumerate(photo_steps, 1):
            print(f"{BOLD}{CYAN}── {stitle} ──{RESET}")
            print(f"  📐 {BOLD}Fórmula:{RESET} {GREEN}{stemplate}{RESET}")
            print(f"  💬 {DIM}{sexample}{RESET}")
            while True:
                ans = input(f"\n  ✍️  {BOLD}Sua Frase {idx} (pode misturar português se travar):{RESET} ").strip()
                if ans:
                    user_sentences.append(ans)
                    print()
                    break
    except (KeyboardInterrupt, EOFError):
        return
    finally:
        if viewer_proc:
            try:
                viewer_proc.terminate()
            except Exception:
                pass

    full_desc = " ".join(user_sentences)
    words = len(full_desc.split())
    print("=" * 70)
    print(f"{BOLD}📸 SUA DESCRIÇÃO COMPLETA ({words} palavras):{RESET}")
    print(f"{YELLOW}\"{full_desc}\"{RESET}")
    print("=" * 70)
    evaluate_c1_mission_and_cliches(full_desc, mission)
    breakdown = compute_local_writing_breakdown(full_desc, mission, target_words=45)
    scored_by_ai = False

    if get_gemini_key():
        print(f"\n{CYAN}🤖 Avaliando a foto real + suas 3 frases e calculando sua nota no Gemini Multimodal...{RESET}")
        prompt = (
            f"Você é um Coach Sênior do Duolingo English Test avaliando o treino guiado de 'Write About the Photo'.\n"
            f"O aluno escreveu 3 frases estruturadas (Visão Geral, Foreground/Background, Atmosfera/Inferência), podendo ter usado palavras em português:\n"
            f"Frase 1: {user_sentences[0]}\n"
            f"Frase 2: {user_sentences[1]}\n"
            f"Frase 3: {user_sentences[2]}\n\n"
            f"Olhando para a imagem real anexada, forneça:\n"
            f"0. 📊 DIAGNÓSTICO DE PONTUAÇÃO (Avalie o rascunho na escala DET 10-160 em Precisão Visual, Gramática e Vocabulário).\n"
            f"1. 🔄 CORREÇÃO & UPGRADE DAS 3 FRASES (Mostre cada frase do aluno transformada em B2 natural e depois em C1 avançado fiel à foto real).\n"
            f"2. ✨ PARÁGRAFO MODELO UNIFICADO (35-50 palavras unindo as 3 camadas com perfeição visual).\n"
            f"3. 🎯 Coloque a melhor frase C1 sozinha após o marcador EXATO 'REWRITE_TARGET: '.\n"
            f"4. Inclua ao final: [DET_EVAL: LITERACY=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )
        resp = analyze_image_with_gemini(photo_path, prompt)
        if resp:
            print(f"\n{GREEN}{BOLD}══════════════════════════════════════════════════════════════════════{RESET}")
            print(resp)
            print(f"{GREEN}{BOLD}══════════════════════════════════════════════════════════════════════{RESET}\n")

            lit_score, prod_score = extract_writing_scores(
                resp,
                default_lit=breakdown["local_lit"],
                default_prod=breakdown["local_prod"]
            )
            record_skill_score("literacy", lit_score)
            record_skill_score("production", prod_score)
            print_writing_coach_scorecard(lit_score, prod_score, breakdown, mode_label="FOTO 3 FRASES")
            scored_by_ai = True

            rewrite_target = ""
            for line in resp.splitlines():
                if "REWRITE_TARGET:" in line:
                    rewrite_target = line.split("REWRITE_TARGET:", 1)[1].strip().strip('"')
                    break

            push_to_anki(
                subdeck_name="Writing Upgrades",
                front_html=f"<b>[DET Photo Coach: 3-Sentence Formula]</b><br><br><b>Foto:</b> {photo_title}<br><br><b>Seu Rascunho:</b> {full_desc}",
                back_html=f"<h3>Coaching Multimodal ({lit_score}/160):</h3><div style='text-align:left;'>{resp.replace(chr(10), '<br>')}</div>",
                tags=["DET", "DET_PhotoCoach"],
                audio_text=rewrite_target or full_desc
            )

            if rewrite_target:
                print(f"\n{MAGENTA}✍️  FIXAÇÃO ATIVA:{RESET} Redigite a frase C1 abaixo para gravar na memória motora:")
                print(f"🎯 {GREEN}{BOLD}{rewrite_target}{RESET}")
                try:
                    typed = input(f"\n⌨️  {BOLD}Sua redigitação:{RESET} ").strip()
                    if typed:
                        print(f"{GREEN}✓ Perfeito! Estrutura visual fixada!{RESET}")
                except (KeyboardInterrupt, EOFError):
                    pass

    if not scored_by_ai:
        lit_score, prod_score = breakdown["local_lit"], breakdown["local_prod"]
        record_skill_score("literacy", lit_score)
        record_skill_score("production", prod_score)
        print_writing_coach_scorecard(lit_score, prod_score, breakdown, mode_label="FOTO 3 FRASES (LOCAL)")

    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")


def _run_pt_to_c1_bridge_coach():
    header()
    print(f"\n{BOLD}{GREEN}[WRITING COACH: TRADUTOR DE IDEIAS (PORTUGUÊS / B1 ➔ INGLÊS B2 & C1)]{RESET}")
    print(f"{DIM}Travou para expressar um pensamento? Escreva sua ideia em português (ou inglês básico){RESET}")
    print(f"{DIM}e veja como construir essa exata ideia em inglês natural (B2) e acadêmico (C1), com treino ativo.{RESET}\n")

    if not get_gemini_key():
        print(f"{YELLOW}⚠️ Configure sua chave do Gemini na opção S) Configurações para usar o Tradutor de Ideias IA.{RESET}")
        input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")
        return

    while True:
        try:
            raw_idea = input(f"{CYAN}💭 Digite sua ideia ou parágrafo (em Português, Inglês simples ou misturado) [ou ENTER para sair]:\n> {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not raw_idea:
            break

        print(f"\n{CYAN}🤖 Transformando sua ideia em estruturas B2 e C1 do DET...{RESET}")
        req = (
            f"Ideia original do aluno: \"{raw_idea}\"\n\n"
            "Como Coach Oficial do Duolingo English Test, transforme essa exata ideia nas seguintes etapas claras:\n"
            "0. 📊 NÍVEL ATUAL DO SEU RASCUNHO (Avalie a frase original enviada na escala DET 10-160 / CEFR, "
            "ou indique o ganho de pontuação ao passar do Português/B1 para B2: ~100 pts e C1: ~130+ pts):\n"
            "1. 🟢 NÍVEL B2 (Inglês claro, correto e natural — fácil de lembrar sob pressão):\n"
            "2. 🚀 NÍVEL C1 ACADÊMICO (Padrão 115-130+ no DET, com conectivos e collocations fortes):\n"
            "3. 🧩 BLOCOS DE CONSTRUÇÃO (Explique os 3 principais chunks/estruturas usados na versão B2/C1 e por que funcionam):\n"
            "4. Coloque a versão B2/C1 recomendada em uma única linha após o marcador EXATO 'REWRITE_TARGET: '.\n"
            "5. Ao final absoluto, inclua a tag avaliando a frase original do aluno (se foi 100% em português, dê 55/55; se já tentou em inglês, dê a nota real 10-160): "
            "[DET_EVAL: LITERACY=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )
        resp = call_gemini(req, max_tokens=650)
        if resp:
            print(f"\n{GREEN}{BOLD}──────────────────────────────────────────────────────────────────────{RESET}")
            print(resp)
            print(f"{GREEN}{BOLD}──────────────────────────────────────────────────────────────────────{RESET}\n")

            breakdown = compute_local_writing_breakdown(raw_idea, mission=None, target_words=20)
            lit_score, prod_score = extract_writing_scores(
                resp,
                default_lit=breakdown["local_lit"],
                default_prod=breakdown["local_prod"]
            )
            print_writing_coach_scorecard(lit_score, prod_score, breakdown, mode_label="PONTE DE IDEIAS (PT/B1 ➔ C1)")

            rewrite_target = ""
            for line in resp.splitlines():
                if "REWRITE_TARGET:" in line:
                    rewrite_target = line.split("REWRITE_TARGET:", 1)[1].strip().strip('"')
                    break

            if rewrite_target:
                push_to_anki(
                    subdeck_name="Writing Upgrades",
                    front_html=f"<b>[DET Idea Bridge: Como expressar em Inglês B2/C1?]</b><br><br>💭 <b>Ideia:</b> {raw_idea}",
                    back_html=f"<div style='text-align:left;'>{resp.replace(chr(10), '<br>')}</div>",
                    tags=["DET", "DET_IdeaBridge"],
                    audio_text=rewrite_target
                )
                print(f"{YELLOW}📥 Expressão e áudio salvos automaticamente no seu Anki!{RESET}")
                speak_text(rewrite_target)
                try:
                    practice = input(f"\n✍️  {BOLD}Treine digitar a frase em inglês para fixar:{RESET}\n   🎯 {GREEN}{rewrite_target}{RESET}\n   ⌨️  > ").strip()
                    if practice:
                        # Accuracy check on motor practice
                        sim_words = set(re.findall(r'\w+', practice.lower()))
                        tgt_words = set(re.findall(r'\w+', rewrite_target.lower()))
                        overlap = int((len(sim_words & tgt_words) / max(1, len(tgt_words))) * 100)
                        print(f"   {GREEN}✓ Ótimo! Precisão da fixação motora: {BOLD}{overlap}%{RESET}{GREEN} — estrutura C1 ativada!{RESET}\n")
                except (KeyboardInterrupt, EOFError):
                    break


# ==============================================================================
# 11B. STRUCTURE MEMORY GYM (LACUNAS PROGRESSIVAS + DRILL RELÂMPAGO A-P-F-U / T-I-T)
# ==============================================================================
C1_STRUCTURE_DECK = [
    {
        "group": "essay",
        "acronym": "A",
        "code": "A-P-F-U (1/4)",
        "title": "FRASE 1/4 (REDAÇÃO) — Tese + Concessão",
        "trigger_pt": "Apresentar os dois lados do tema e cravar sua opinião principal",
        "chassis_display": "Although [risco/benefício], I contend that [sua tese] because [motivo].",
        "chassis_clean": "Although ..., I contend that ... because ...",
        "keywords": ["although", "i", "contend", "that", "because"],
        "hint_lvl1": "A_______ [...], I c______ t___ [...] b______ [...].",
        "hint_lvl2": "________ [...], _ _______ ____ [...] _______ [...].",
        "chunks": [
            "Although [risco/benefício],",
            "I contend that",
            "[sua tese principal]",
            "because [motivo central]."
        ],
        "example": "Although artificial intelligence poses privacy risks, I contend that its educational benefits outweigh the drawbacks because it personalizes learning."
    },
    {
        "group": "essay",
        "acronym": "P",
        "code": "A-P-F-U (2/4)",
        "title": "FRASE 2/4 (REDAÇÃO) — Mecanismo / Causa e Efeito",
        "trigger_pt": "Explicar como o seu argumento funciona na prática e qual o impacto dele",
        "chassis_display": "Primarily, this is because [mecanismo], which significantly mitigates [problema].",
        "chassis_clean": "Primarily, this is because ..., which significantly mitigates ...",
        "keywords": ["primarily", "this", "is", "because", "which", "significantly", "mitigates"],
        "alt_keywords": {"mitigates": ["reduces", "enhances", "improves"]},
        "hint_lvl1": "P________, t___ i_ b______ [...], w____ s____________ m________ [...].",
        "hint_lvl2": "_________, ____ __ _______ [...], _____ _____________ _________ [...].",
        "chunks": [
            "Primarily,",
            "this is because [como funciona],",
            "which significantly",
            "mitigates [o problema/resultado]."
        ],
        "example": "Primarily, this is because adaptive algorithms identify knowledge gaps instantly, which significantly mitigates student frustration."
    },
    {
        "group": "essay",
        "acronym": "F",
        "code": "A-P-F-U (3/4)",
        "title": "FRASE 3/4 (REDAÇÃO) — Exemplo Concreto de Área",
        "trigger_pt": "Ancorar seu argumento com um exemplo real de um setor ou área",
        "chassis_display": "For instance, in the field of [área/setor], [exemplo concreto].",
        "chassis_clean": "For instance, in the field of ..., ...",
        "keywords": ["for", "instance", "in", "the", "field", "of"],
        "hint_lvl1": "F__ i_______, i_ t__ f____ o_ [área], [exemplo concreto].",
        "hint_lvl2": "___ ________, __ ___ _____ __ [área], [exemplo concreto].",
        "chunks": [
            "For instance,",
            "in the field of",
            "[educação / medicina / tecnologia],",
            "[exemplo prático real]."
        ],
        "example": "For instance, in the field of higher education, virtual tutors allow struggling students to master complex concepts at their own pace."
    },
    {
        "group": "essay",
        "acronym": "U",
        "code": "A-P-F-U (4/4)",
        "title": "FRASE 4/4 (REDAÇÃO) — Conclusão Condicional C1",
        "trigger_pt": "Fechar a redação com chave de ouro impondo uma condição inteligente",
        "chassis_display": "Ultimately, provided that governments enforce strict regulations to mitigate potential risks, [conclusão].",
        "chassis_clean": "Ultimately, provided that governments enforce strict regulations to mitigate potential risks, ...",
        "keywords": ["ultimately", "provided", "that", "governments", "enforce", "strict", "regulations", "to", "mitigate", "potential", "risks"],
        "hint_lvl1": "U_________, p_______ t___ g__________ e______ s_____ r__________ t_ m_______ p________ r____, [conclusão].",
        "hint_lvl2": "__________, ________ ____ ___________ _______ ______ ___________ __ ________ _________ _____, [conclusão].",
        "chunks": [
            "Ultimately,",
            "provided that governments enforce",
            "strict regulations",
            "to mitigate potential risks, [conclusão]."
        ],
        "example": "Ultimately, provided that governments enforce strict regulations to mitigate potential risks, this innovation will foster long-term progress."
    },
    {
        "group": "photo",
        "acronym": "T",
        "code": "T-I-T (1/3)",
        "title": "FRASE 1/3 (FOTO) — Visão Geral & Ação Principal",
        "trigger_pt": "Abrir a descrição da foto dizendo o que a cena captura no geral",
        "chassis_display": "This photograph captures a candid scene of [quem/o quê] in [ambiente].",
        "chassis_clean": "This photograph captures a candid scene of ... in ...",
        "keywords": ["this", "photograph", "captures", "a", "candid", "scene", "of", "in"],
        "hint_lvl1": "T___ p_________ c_______ a c_____ s____ o_ [sujeito + -ing] i_ [lugar].",
        "hint_lvl2": "____ __________ ________ _ ______ _____ __ [sujeito + -ing] __ [lugar].",
        "chunks": [
            "This photograph",
            "captures a candid scene of",
            "[sujeito + verbo com -ing]",
            "in [ambiente/lugar]."
        ],
        "example": "This photograph captures a candid scene of a concentrated engineer inspecting equipment in a modern laboratory."
    },
    {
        "group": "photo",
        "acronym": "I",
        "code": "T-I-T (2/3)",
        "title": "FRASE 2/3 (FOTO) — Primeiro Plano vs. Plano de Fundo",
        "trigger_pt": "Contrastar o que está na frente da imagem com o que aparece atrás",
        "chassis_display": "In the foreground, [detalhe da frente], whereas the background reveals [detalhe do fundo].",
        "chassis_clean": "In the foreground, ..., whereas the background reveals ...",
        "keywords": ["in", "the", "foreground", "whereas", "the", "background", "reveals"],
        "hint_lvl1": "I_ t__ f_________, [frente], w______ t__ b_________ r______ [fundo].",
        "hint_lvl2": "__ ___ __________, [frente], _______ ___ __________ _______ [fundo].",
        "chunks": [
            "In the foreground,",
            "[detalhe da frente],",
            "whereas the background",
            "reveals [detalhe do fundo]."
        ],
        "example": "In the foreground, technical blueprints are spread across a desk, whereas the background reveals bright industrial machinery."
    },
    {
        "group": "photo",
        "acronym": "T",
        "code": "T-I-T (3/3)",
        "title": "FRASE 3/3 (FOTO) — Iluminação, Atmosfera & Hipótese",
        "trigger_pt": "Descrever a sensação que a luz transmite e fazer uma inferência final",
        "chassis_display": "The natural lighting conveys a sense of [emoção/foco], suggesting that [hipótese].",
        "chassis_clean": "The natural lighting conveys a sense of ..., suggesting that ...",
        "keywords": ["the", "natural", "lighting", "conveys", "a", "sense", "of", "suggesting", "that"],
        "hint_lvl1": "T__ n______ l_______ c______ a s____ o_ [foco/calma], s_________ t___ [hipótese].",
        "hint_lvl2": "___ _______ ________ _______ _ _____ __ [foco/calma], __________ ____ [hipótese].",
        "chunks": [
            "The natural lighting",
            "conveys a sense of [foco/calma],",
            "suggesting that",
            "[hipótese sobre a cena]."
        ],
        "example": "The natural lighting conveys a sense of deep focus, suggesting that the team is preparing for an important project launch."
    }
]


def _evaluate_structure_attempt(user_text, item):
    """Evaluates whether the user typed the core structural connectors of an item."""
    # Remove bracketed placeholders if the user typed them
    cleaned_user = re.sub(r"\[[^\]]*\]", " ", user_text.lower())
    user_tokens = re.findall(r"[a-z]+", cleaned_user)
    user_set = set(user_tokens)
    alt_map = item.get("alt_keywords", {})

    matched = 0
    feedback_parts = []
    used_indices = set()

    for kw in item["keywords"]:
        candidates = [kw] + alt_map.get(kw, [])
        found = False
        for idx, tok in enumerate(user_tokens):
            if idx not in used_indices and tok in candidates:
                found = True
                used_indices.add(idx)
                break
        if not found and any(c in user_set for c in candidates):
            found = True

        if found:
            matched += 1
            feedback_parts.append(f"{GREEN}{BOLD}{kw}{RESET}")
        else:
            feedback_parts.append(f"{RED}{BOLD}[{kw}]{RESET}")

    total_kw = max(1, len(item["keywords"]))
    pct = int(round((matched / total_kw) * 100))
    return pct, " ".join(feedback_parts), matched, total_kw


def _run_progressive_cloze_drill():
    header()
    print(f"\n{BOLD}{GREEN}[TREINO 1: LACUNAS PROGRESSIVAS (TIRANDO AS RODINHAS EM 3 NÍVEIS)]{RESET}")
    print(f"{DIM}Você vai digitar apenas o ESQUELETO (conectivos C1). Não precisa inventar redação inteira!{RESET}")
    print(f"{DIM}Pode colocar '...' nos buracos das ideias (ex: Although ..., I contend that ... because ...){RESET}\n")

    print(f"  {BOLD}1){RESET} 🏗️  Kit Redação 4 Frases — Fórmula {GREEN}{BOLD}A-P-F-U{RESET} (Although ➔ Primarily ➔ For instance ➔ Ultimately)")
    print(f"  {BOLD}2){RESET} 📸 Kit Foto 3 Frases    — Fórmula {CYAN}{BOLD}T-I-T{RESET}   (This photograph ➔ In the foreground ➔ The natural lighting)")
    print(f"  {BOLD}3){RESET} 🔥 Combo Completo       — Todas as 7 Estruturas (Redação + Foto)")

    try:
        kit_choice = input(f"\n{CYAN}Escolha o kit para decorar [1-3, padrão=1]: {RESET}").strip() or "1"
    except (KeyboardInterrupt, EOFError):
        return

    if kit_choice == "2":
        items = [x for x in C1_STRUCTURE_DECK if x["group"] == "photo"]
    elif kit_choice == "3":
        items = list(C1_STRUCTURE_DECK)
    else:
        items = [x for x in C1_STRUCTURE_DECK if x["group"] == "essay"]

    print(f"\n{BOLD}Escolha o Nível de Retirada de Dicas:{RESET}")
    print(f"  {BOLD}1){RESET} 🟢 {BOLD}Nível 1 (Com Iniciais){RESET}  — Mostra a 1ª letra de cada conectivo (ex: A_______ ..., I c______ t___ ...)")
    print(f"  {BOLD}2){RESET} 🟡 {BOLD}Nível 2 (Lacuna Cega){RESET}   — Mostra apenas os traços (ex: ________ ..., _ _______ ____ ...)")
    print(f"  {BOLD}3){RESET} 🔴 {BOLD}Nível 3 (De Cabeça!){RESET}    — Sem dica visual! Só o objetivo da frase e a letra-gatilho")
    print(f"  {BOLD}4){RESET} 🚀 {BOLD}Escada Completa (1➔2➔3){RESET} — Passa a mesma frase pelo Nível 1, depois 2 e depois 3 na sequência!")

    try:
        lvl_choice = input(f"\n{CYAN}Escolha o nível [1-4, padrão=4 (Escada Completa)]: {RESET}").strip() or "4"
    except (KeyboardInterrupt, EOFError):
        return

    levels_to_run = [1, 2, 3] if lvl_choice == "4" else ([int(lvl_choice)] if lvl_choice in ["1", "2", "3"] else [1, 2, 3])

    total_pct_acc = []
    for idx, item in enumerate(items, 1):
        print("\n" + "═" * 74)
        print(f"{BOLD}{MAGENTA}🎯 ESTRUTURA {idx}/{len(items)}: [{item['code']}] — {item['title']}{RESET}")
        print(f"   💡 {BOLD}Quando usar:{RESET} {item['trigger_pt']}")
        if len(levels_to_run) > 1:
            print(f"   📐 {DIM}Alvo completo: {item['chassis_display']}{RESET}")
        print("═" * 74)

        for lvl in levels_to_run:
            if lvl == 1:
                badge = f"{GREEN}[NÍVEL 1/3 — COM INICIAIS]{RESET}"
                cue = f"   🧩 {BOLD}Complete o chassi:{RESET} {YELLOW}{item['hint_lvl1']}{RESET}"
            elif lvl == 2:
                badge = f"{YELLOW}[NÍVEL 2/3 — LACUNAS CEGAS]{RESET}"
                cue = f"   🧩 {BOLD}Lembre os conectivos:{RESET} {YELLOW}{item['hint_lvl2']}{RESET}"
            else:
                badge = f"{RED}{BOLD}[NÍVEL 3/3 — DE CABEÇA SEM COLA!]{RESET}"
                cue = f"   🧠 {BOLD}Letra-Gatilho [{item['acronym']}]:{RESET} Digite o chassi completo de memória!"

            print(f"\n  {badge}")
            print(cue)
            try:
                ans = input(f"   ✍️  {BOLD}Digite o chassi:{RESET} ").strip()
            except (KeyboardInterrupt, EOFError):
                return

            if not ans:
                print(f"   {YELLOW}⏭️  Pulando... O chassi correto é:{RESET} {GREEN}{item['chassis_clean']}{RESET}")
                continue

            pct, diff_str, matched, total_kw = _evaluate_structure_attempt(ans, item)
            total_pct_acc.append(pct)

            if pct == 100:
                print(f"   {GREEN}{BOLD}✓ PERFEITO (100%)!{RESET} Todos os {total_kw} conectivos do chassi cravados: {diff_str}")
            else:
                print(f"   {YELLOW}📊 Precisão do chassi: {BOLD}{pct}% ({matched}/{total_kw} palavras-chave){RESET}")
                print(f"   🔍 {BOLD}Raio-X:{RESET} {diff_str}  {DIM}(em vermelho = faltou ou trocou){RESET}")
                print(f"   📐 {BOLD}Gabarito Limpo:{RESET} {GREEN}{BOLD}{item['chassis_clean']}{RESET}")
                try:
                    fix = input(f"   ⌨️  {CYAN}Redigite o gabarito limpo acima 1x para corrigir a memória motora:{RESET}\n      > ").strip()
                    if fix:
                        print(f"      {GREEN}✓ Gravado nos dedos!{RESET}")
                except (KeyboardInterrupt, EOFError):
                    return

        speak_text(item["example"])

    if total_pct_acc:
        avg_ret = int(sum(total_pct_acc) / len(total_pct_acc))
        lit_eq = min(145, max(70, int(65 + (avg_ret * 0.7))))
        record_skill_score("literacy", lit_eq)
        record_skill_score("production", lit_eq)
        print("\n" + "═" * 74)
        print(f"🏆 {BOLD}RESUMO DO TREINO DE MEMORIZAÇÃO:{RESET} Retenção Média dos Chassis = {GREEN}{BOLD}{avg_ret}%{RESET}")
        if avg_ret >= 90:
            print(f"{GREEN}🔥 Excelente! Essas estruturas já estão prontas para sair no automático na prova!{RESET}")
        else:
            print(f"{YELLOW}💡 Dica: Repita o Nível 3 amanhã até bater 95%+ sem olhar a cola.{RESET}")
        print("═" * 74)
        update_streak()

    input(f"\n{DIM}Pressione [ENTER] para voltar à Academia de Estruturas...{RESET}")


def _run_lightning_chassis_drill():
    header()
    print(f"\n{BOLD}{GREEN}[TREINO 2: ⚡ DRILL RELÂMPAGO DE CHASSIS (SIMULADOR DOS PRIMEIROS 15s DA PROVA)]{RESET}")
    print(f"{DIM}Na prova real, seu objetivo é despejar os 4 esqueletos na caixa de texto nos primeiros 20 segundos.{RESET}")
    print(f"{DIM}Responda a cada missão digitando apenas o chassi em inglês o mais rápido que conseguir!{RESET}\n")

    pool = list(C1_STRUCTURE_DECK)
    random.shuffle(pool)

    input(f"{GREEN}Pressione [ENTER] para disparar a bateria relâmpago ({len(pool)} gatilhos)...{RESET}")

    times = []
    scores = []
    for idx, item in enumerate(pool, 1):
        print(f"\n{BOLD}{CYAN}⚡ DESAFIO {idx}/{len(pool)} — [{item['code']}]{RESET}")
        print(f"   🎯 {BOLD}Missão:{RESET} {YELLOW}{item['trigger_pt']}{RESET}")
        print(f"   🔑 {BOLD}Letra-Gatilho:{RESET} Começa com {GREEN}{BOLD}\"{item['acronym']}...\"{RESET}")

        t0 = time.time()
        try:
            ans = input(f"\n   ⌨️  {BOLD}Chassi em inglês:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        elapsed = round(time.time() - t0, 1)

        if not ans:
            print(f"   {RED}✗ Em branco!{RESET} Gabarito: {GREEN}{BOLD}{item['chassis_clean']}{RESET}")
            scores.append(0)
            continue

        pct, diff_str, matched, total_kw = _evaluate_structure_attempt(ans, item)
        times.append(elapsed)
        scores.append(pct)

        speed_badge = f"{GREEN}⚡ {elapsed}s (Rápido!){RESET}" if elapsed <= 15 else f"{YELLOW}⏱️ {elapsed}s{RESET}"
        if pct >= 85:
            print(f"   {GREEN}{BOLD}✓ MANDOU BEM ({pct}%)!{RESET} Tempo: {speed_badge}")
            print(f"   🔍 {diff_str}")
        else:
            print(f"   {YELLOW}⚠️ Quase ({pct}%)!{RESET} Tempo: {speed_badge}")
            print(f"   🔍 {diff_str}")
            print(f"   📐 {BOLD}Chassi Exato:{RESET} {GREEN}{BOLD}{item['chassis_clean']}{RESET}")
            try:
                _ = input(f"   ✍️  {CYAN}Digite o chassi exato 1x para destravar:{RESET} ")
            except (KeyboardInterrupt, EOFError):
                return

    if scores:
        avg_s = int(sum(scores) / len(scores))
        avg_t = round(sum(times) / max(1, len(times)), 1) if times else 0
        print("\n" + "═" * 74)
        print(f"⚡ {BOLD}RESULTADO DO DRILL RELÂMPAGO:{RESET}")
        print(f"   • Precisão Média dos Esqueletos: {GREEN if avg_s >= 85 else YELLOW}{BOLD}{avg_s}%{RESET}")
        print(f"   • Velocidade Média de Reação:    {CYAN}{BOLD}{avg_t}s por frase{RESET} (Meta de prova: < 15s)")
        print("═" * 74)
        update_streak()

    input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")


def _run_chunk_unscramble_drill():
    header()
    print(f"\n{BOLD}{GREEN}[TREINO 3: 🔀 LEGO DE ESTRUTURAS C1 (ORDENAR BLOCOS + MEMÓRIA MOTORA)]{RESET}")
    print(f"{DIM}Monte a ordem lógica dos blocos de cada estrutura C1 e depois digite a frase inteira.{RESET}\n")

    for idx, item in enumerate(C1_STRUCTURE_DECK, 1):
        chunks = list(item["chunks"])
        indexed_chunks = list(enumerate(chunks, 1))
        shuffled = list(indexed_chunks)
        while shuffled == indexed_chunks and len(shuffled) > 1:
            random.shuffle(shuffled)

        correct_seq = [str(i + 1) for i in range(len(shuffled))]
        # Map from displayed number (1..N) to original order
        correct_disp_order = []
        for orig_idx in range(1, len(chunks) + 1):
            for disp_idx, (o_idx, _) in enumerate(shuffled, 1):
                if o_idx == orig_idx:
                    correct_disp_order.append(str(disp_idx))
                    break

        print("─" * 74)
        print(f"{BOLD}{MAGENTA}🧩 LEGO {idx}/{len(C1_STRUCTURE_DECK)}: [{item['code']}] — {item['title']}{RESET}")
        print(f"   💡 {DIM}{item['trigger_pt']}{RESET}\n")

        for disp_idx, (_, chunk_text) in enumerate(shuffled, 1):
            print(f"    {BOLD}{CYAN}[{disp_idx}]{RESET} {chunk_text}")

        expected_str = " ".join(correct_disp_order)
        expected_compact = "".join(correct_disp_order)

        try:
            user_order = input(f"\n   🔢 {BOLD}Digite a ordem correta dos números (ex: 2 1 4 3) [ou ENTER p/ sair]:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if not user_order:
            break

        user_digits = re.findall(r"\d+", user_order)
        if "".join(user_digits) == expected_compact:
            print(f"   {GREEN}{BOLD}✓ Ordem 100% exata!{RESET}")
        else:
            print(f"   {YELLOW}✗ A ordem correta era:{RESET} {BOLD}{expected_str}{RESET}")

        print(f"   📐 {BOLD}Estrutura Montada:{RESET} {GREEN}{BOLD}{item['chassis_display']}{RESET}")
        try:
            _ = input(f"   ⌨️  {CYAN}Agora digite o chassi limpo ({item['chassis_clean']}) para gravar nos dedos:{RESET}\n      > ")
        except (KeyboardInterrupt, EOFError):
            return
        print()

    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")


def _show_acronym_cheatsheet_and_anki():
    header()
    print(f"\n{BOLD}{GREEN}[MAPA MENTAL DE PROVA: ACRÔNIMOS 'A-P-F-U' (REDAÇÃO) & 'T-I-T' (FOTO)]{RESET}")
    print(f"{DIM}Na prova real, decore apenas as letras-gatilho abaixo. Quando o cronômetro abrir,{RESET}")
    print(f"{DIM}digite as 4 linhas do esqueleto primeiro (leva 15s) e depois só preencha o recheio!{RESET}\n")

    print(f"{BOLD}{MAGENTA}┌── 🏗️  FÓRMULA 'A-P-F-U' — INTERACTIVE WRITING (5 MINUTOS) ───────────────┐{RESET}")
    for item in C1_STRUCTURE_DECK:
        if item["group"] == "essay":
            print(f"  {GREEN}{BOLD}[{item['acronym']}]{RESET} {BOLD}{item['title'].split('—')[1].strip()}:{RESET}")
            print(f"      📐 {CYAN}{item['chassis_display']}{RESET}")
            print(f"      💬 {DIM}Ex: {item['example']}{RESET}\n")
    print(f"{BOLD}{MAGENTA}└── 💡 Follow-up (3 min): \"Building upon my previous point, it is worth noting that..., therefore...\" ┘{RESET}\n")

    print(f"{BOLD}{CYAN}┌── 📸 FÓRMULA 'T-I-T' — WRITE ABOUT THE PHOTO (1 MINUTO) ─────────────────┐{RESET}")
    for item in C1_STRUCTURE_DECK:
        if item["group"] == "photo":
            print(f"  {GREEN}{BOLD}[{item['acronym']}]{RESET} {BOLD}{item['title'].split('—')[1].strip()}:{RESET}")
            print(f"      📐 {CYAN}{item['chassis_display']}{RESET}")
            print(f"      💬 {DIM}Ex: {item['example']}{RESET}\n")
    print(f"{BOLD}{CYAN}└──────────────────────────────────────────────────────────────────────────┘{RESET}\n")

    try:
        act = input(f"{YELLOW}Deseja [A] Enviar os 7 Flashcards de Estruturas com Áudio para o Anki, [O] Ouvir todas em voz alta, ou [ENTER] Voltar? {RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return

    if act == "a":
        for item in C1_STRUCTURE_DECK:
            front = (
                f"<b>[DET Estrutura C1 — Gatilho {item['code']}]</b><br><br>"
                f"🎯 <b>Missão:</b> {item['trigger_pt']}<br>"
                f"🔑 <b>Letra-Gatilho:</b> Começa com <b>\"{item['acronym']}...\"</b><br><br>"
                f"<i>Qual é o esqueleto (chassi) C1 completo em inglês?</i>"
            )
            back = (
                f"<h3>📐 Chassi Oficial:</h3>"
                f"<p style='font-size:1.15em;color:#10b981;'><b>{item['chassis_display']}</b></p>"
                f"<hr><b>Exemplo Real C1:</b><br><i>{item['example']}</i>"
            )
            push_to_anki(
                subdeck_name="Writing Upgrades",
                front_html=front,
                back_html=back,
                tags=["DET", "DET_Structures_C1"],
                audio_text=item["example"]
            )
        print(f"\n{GREEN}{BOLD}✓ Todos os 7 Flashcards de Estruturas C1 (+ áudio) foram enviados para o seu Anki (Subdeck: Writing Upgrades)!{RESET}")
        input(f"\n{DIM}Pressione [ENTER] para continuar...{RESET}")
    elif act == "o":
        for item in C1_STRUCTURE_DECK:
            print(f"\n🔊 {BOLD}[{item['code']}]{RESET} {GREEN}{item['chassis_clean']}{RESET}")
            print(f"   {DIM}Ex: {item['example']}{RESET}")
            speak_text(item["example"])
        input(f"\n{DIM}Pressione [ENTER] para continuar...{RESET}")


def _run_structure_memory_gym():
    while True:
        header()
        print(f"\n{BOLD}{MAGENTA}[🏋️  ACADEMIA DE MEMORIZAÇÃO DE ESTRUTURAS C1 (A-P-F-U & T-I-T)]{RESET}")
        print(f"{DIM}Treine até digitar os esqueletos da Redação e da Foto no piloto automático e sem olhar a cola!{RESET}\n")

        print(f"  {BOLD}1){RESET} 🧩 {BOLD}Lacunas Progressivas (3 Níveis){RESET}    {DIM}(Iniciais ➔ Lacunas Cegas ➔ 100% De Cabeça + Diff Colorido){RESET}")
        print(f"  {BOLD}2){RESET} ⚡ {BOLD}Drill Relâmpago de Chassis (15s){RESET}   {DIM}(Treino de velocidade para despejar o esqueleto no início da prova){RESET}")
        print(f"  {BOLD}3){RESET} 🔀 {BOLD}Lego de Estruturas C1{RESET}              {DIM}(Desembaralhar os blocos da frase + fixação motora){RESET}")
        print(f"  {BOLD}4){RESET} 🧠 {BOLD}Cola Mental A-P-F-U & T-I-T + Anki{RESET} {DIM}(Ver mapa completo de acrônimos, ouvir áudio e mandar pro Anki){RESET}")
        print(f"  {BOLD}0){RESET} Voltar ao Writing Coach")

        try:
            choice = input(f"\n{CYAN}Escolha o treino de memorização (0-4): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            _run_progressive_cloze_drill()
        elif choice == "2":
            _run_lightning_chassis_drill()
        elif choice == "3":
            _run_chunk_unscramble_drill()
        elif choice == "4":
            _show_acronym_cheatsheet_and_anki()
        elif choice == "0":
            break


def run_writing_coach():
    while True:
        header()
        stats = load_stats()
        coach_hist = stats.get("coach_scores", [])
        skills = stats.get("skills", {})
        lit_scores = skills.get("literacy", {}).get("scores", [])
        prod_scores = skills.get("production", {}).get("scores", [])

        print(f"\n{BOLD}{GREEN}[MÓDULO W: WRITING COACH & DESTRAVAR ESCRITA (PASSO A PASSO)]{RESET}")
        print(f"{DIM}Elimine o bloqueio da tela em branco treinando a escrita em blocos guiados sem pressão.{RESET}")

        if coach_hist:
            last_entry = coach_hist[-1]
            avg_coach = int(sum(x.get("overall", 80) for x in coach_hist[-5:]) / len(coach_hist[-5:]))
            recent_trail = " ➔ ".join(str(x.get("overall", 80)) for x in coach_hist[-5:])
            c_col = GREEN if avg_coach >= 95 else (YELLOW if avg_coach >= 80 else RED)
            print(f"{CYAN}📊 {BOLD}Seu Desempenho no Writing Coach:{RESET} Última Nota: {BOLD}{last_entry.get('overall')}/160{RESET} ({last_entry.get('mode')}) | Média Recente: {c_col}{BOLD}{avg_coach}/160 pts{RESET}")
            print(f"{DIM}   Histórico recente: {recent_trail} pts (Meta UFRJ: 95-105 pts){RESET}\n")
        elif lit_scores or prod_scores:
            l_avg = int(sum(lit_scores[-3:]) / len(lit_scores[-3:])) if lit_scores else 85
            p_avg = int(sum(prod_scores[-3:]) / len(prod_scores[-3:])) if prod_scores else 85
            w_est = int((l_avg + p_avg) / 2)
            print(f"{CYAN}📊 {BOLD}Nível Atual de Escrita (Dashboard):{RESET} ~{BOLD}{w_est}/160 pts{RESET} (Literacy: {l_avg} | Production: {p_avg}) — {DIM}Faça um treino abaixo para gerar seu Scorecard!{RESET}\n")
        else:
            print()

        print(f"  {BOLD}1){RESET} 🏗️  {BOLD}Construtor de Redação em 4 Frases{RESET}   {DIM}(Tese ➔ Explicação ➔ Exemplo ➔ Conclusão + Nota DET){RESET}")
        print(f"  {BOLD}2){RESET} 📸 {BOLD}Fórmula de 3 Frases para Fotos{RESET}       {DIM}(Visão Geral ➔ Primeiro/Segundo Plano ➔ Atmosfera + Nota DET){RESET}")
        print(f"  {BOLD}3){RESET} 🌉 {BOLD}Ponte de Ideias (Português/B1 ➔ C1){RESET} {DIM}(Escreva o que quer dizer em PT e veja sua nota + estrutura C1){RESET}")
        print(f"  {BOLD}4){RESET} 🏋️  {MAGENTA}{BOLD}Memorizar Estruturas (A-P-F-U/T-I-T){RESET} {DIM}(Lacunas Progressivas + Drill Relâmpago 15s + Lego C1 + Anki){RESET}")
        print(f"  {BOLD}5){RESET} ⏱️  Ir para o Simulador Oficial Cronometrado (5 min Interactive Writing)")
        print(f"  {BOLD}0){RESET} Voltar ao Menu Principal")

        try:
            sub = input(f"\n{CYAN}Escolha o modo do Writing Coach (0-5): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if sub == "1":
            _run_scaffolded_essay_coach()
        elif sub == "2":
            _run_scaffolded_photo_coach()
        elif sub == "3":
            _run_pt_to_c1_bridge_coach()
        elif sub == "4":
            _run_structure_memory_gym()
        elif sub == "5":
            run_writing_prompt()
        elif sub == "0":
            break


# ==============================================================================
# 11C. SPEAKING COACH & FLUENCY GYM (SCAFFOLDED SPEAKING + PHOTO + SHADOWING + VOICE BRIDGE)
# ==============================================================================
def _run_scaffolded_speaking_coach():
    """Breaks a 90-second speaking prompt into 3 low-pressure 25-35s guided audio blocks (allows PT words if stuck)."""
    header()
    print(f"\n{BOLD}{MAGENTA}[SPEAKING COACH: CONSTRUTOR DE FALA EM 3 BLOCOS (PASSO A PASSO SEM PRESSÃO)]{RESET}")
    print(f"{DIM}Destrave a fala dividindo a resposta de 90s em 3 micro-gravações guiadas com o esqueleto na tela.{RESET}")
    print(f"{DIM}💡 Dica de Ouro: Se esquecer uma palavra em inglês no meio da frase, FALE EM PORTUGUÊS mesmo e continue o ritmo!{RESET}\n")

    prompt = get_unseen_speaking_prompt()
    if not prompt and get_gemini_key():
        print(f"{CYAN}🤖 Gerando tema de fala inédito...{RESET}")
        prompt = generate_dynamic_speaking_prompt_ai(4)
    if not prompt:
        prompt = get_random_speaking_prompt_pool()
    mark_item_seen("speaking", prompt)

    mission = get_c1_lexical_mission(3)
    print(f"{BOLD}TEMA DE FALA:{RESET}")
    print(f"{YELLOW}{prompt}{RESET}\n")
    print_c1_mission_banner(mission)

    try:
        hear_opt = input(f"{CYAN}🔊 Deseja ouvir a pergunta falada antes de começar? [s/N]: {RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return
    if hear_opt in ["s", "sim", "y", "yes"]:
        speak_text(prompt)

    blocks = [
        (
            "BLOCO 1/3 — TESE + CONCESSÃO (25 segundos)",
            "Although [benefício ou desafio do tema], I contend that [sua opinião principal] because [motivo central].",
            "Ex: Although remote work can cause isolation, I contend that it boosts productivity because it eliminates commuting.",
            25
        ),
        (
            "BLOCO 2/3 — MECANISMO + EXEMPLO CONCRETO (35 segundos)",
            "Primarily, this is because [como funciona], which significantly mitigates [problema]. For instance, in the field of [área], [exemplo].",
            "Ex: Primarily, this is because flexible schedules reduce stress. For instance, in the field of software engineering, teams deliver faster.",
            35
        ),
        (
            "BLOCO 3/3 — CONCLUSÃO CONDICIONAL C1 (25 segundos)",
            "Ultimately, provided that organizations enforce clear guidelines to mitigate potential risks, [conclusão final].",
            "Ex: Ultimately, provided that organizations enforce clear communication guidelines, this approach will foster long-term success.",
            25
        )
    ]

    recorded_paths = []
    for idx, (b_title, b_chassis, b_example, b_dur) in enumerate(blocks, 1):
        print(f"\n{BOLD}{CYAN}── {b_title} ──{RESET}")
        print(f"  📐 {BOLD}Esqueleto na tela (leia e preencha falando):{RESET}")
        print(f"     {GREEN}{BOLD}{b_chassis}{RESET}")
        print(f"  💬 {DIM}{b_example}{RESET}")
        print(f"  {DIM}(Se travar numa palavra, fale em português e siga em frente sem parar!){RESET}")
        while True:
            try:
                cmd = input(f"\n  🎙️  Pressione {GREEN}{BOLD}[ENTER]{RESET} para gravar o Bloco {idx} ({b_dur}s) ou 'o' para ouvir o exemplo: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return
            if cmd == "o":
                speak_text(b_example.replace("Ex: ", ""))
                continue
            break

        b_path = os.path.join(tempfile.gettempdir(), f"det_speak_block_{idx}.wav")
        print(f"\n  {GREEN}{BOLD}>>> FALE O BLOCO {idx} AGORA! (Ctrl+C quando terminar a frase) <<<{RESET}")
        if record_mic_clip(b_path, b_dur, f"Bloco {idx}/3"):
            recorded_paths.append(b_path)
            print(f"  {GREEN}✓ Bloco {idx} capturado!{RESET}")
        else:
            print(f"  {YELLOW}⚠️ Áudio muito curto ou vazio no Bloco {idx}.{RESET}")

    if not recorded_paths:
        print(f"\n{YELLOW}Nenhum bloco de áudio foi gravado.{RESET}")
        input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")
        return

    if get_gemini_key():
        print(f"\n{CYAN}🤖 Analisando seus {len(recorded_paths)} blocos de voz no Gemini Multimodal (Transcrição + Tradução PT➔C1 + Pronúncia)...{RESET}")
        sys_inst = (
            "Você é um Coach Sênior de Fala e Pronúncia do Duolingo English Test (DET).\n"
            "O aluno respondeu ao tema gravando 3 blocos guiados (Tese, Mecanismo/Exemplo e Conclusão), podendo ter falado palavras em português quando travou.\n"
            "Avalie os áudios enviados e responda EXATAMENTE nestas seções:\n"
            "0. 📊 DIAGNÓSTICO DE PONTUAÇÃO DA SUA FALA (Nota DET 10-160 para Fluência/Pronúncia e Léxico/Estrutura, mostrando o quanto ele ganha aplicando a versão C1):\n"
            "1. 🔄 PONTE DE FALA BLOCO A BLOCO (Para cada bloco gravado:\n"
            "   - 🎙️ O que você falou (transcrição exata, destacando entre colchetes qualquer palavra dita em português ou hesitação)\n"
            "   - 🟢 Versão Falada Natural (B2 — fluida, corrigindo a gramática e traduzindo os termos em português)\n"
            "   - 🚀 Versão Acadêmica Elevada (C1 — padrão 115+ DET))\n"
            "2. 👄 RAIO-X DE PRONÚNCIA & PROSÓDIA (Liste as palavras que o aluno pronunciou com dificuldade ou sotaque forte que pode afetar a compreensão, mostrando a pronúncia figurada fácil para brasileiros e onde colocar a sílaba tônica):\n"
            "3. 🏆 DISCURSO UNIFICADO PRONTO PARA FALAR EM 90s (Os 3 blocos unidos em uma fala natural de ~110 palavras):\n"
            "4. 🎯 Coloque a frase mais importante corrigida sozinha em uma linha após o marcador EXATO 'SPEAK_MODEL: '.\n"
            "5. Ao final absoluto, inclua obrigatoriamente: [DET_EVAL: CONVERSATION=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )
        ai_resp = analyze_multiple_audios_with_gemini(recorded_paths, prompt, sys_inst)
        if ai_resp:
            print(f"\n{BOLD}{MAGENTA}══════════════════════════════════════════════════════════════════════{RESET}")
            print(f"{BOLD}{MAGENTA}🎓 COACHING DE FALA BLOCO A BLOCO (SUA VOZ ➔ B2 ➔ C1):{RESET}")
            print(f"{BOLD}{MAGENTA}══════════════════════════════════════════════════════════════════════{RESET}\n")
            print(ai_resp)
            evaluate_c1_mission_and_cliches(ai_resp, mission)

            conv_score, prod_score = extract_eval_scores(ai_resp, default_conv=80, default_prod=80)
            record_skill_score("conversation", conv_score)
            record_skill_score("production", prod_score)
            print_speaking_coach_scorecard(conv_score, prod_score, mode_label="FALA EM 3 BLOCOS")

            model_s = _extract_speak_model_sentence(ai_resp)
            push_to_anki(
                subdeck_name="Speaking Feedback",
                front_html=f"<b>[DET Speaking Coach: 3-Block Builder]</b><br><br><b>Prompt:</b> {prompt}",
                back_html=f"<h3>Upgrade Bloco a Bloco ({conv_score}/160):</h3><div style='text-align:left;'>{ai_resp.replace(chr(10), '<br>')}</div>",
                tags=["DET", "DET_SpeakingCoach"],
                audio_text=model_s or None
            )
            print(f"\n{YELLOW}📥 Card de fala + áudio nativo enviado ao Anki em segundo plano!{RESET}")
            _offer_speaking_second_shot(prompt, ai_resp)

    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")


def _run_scaffolded_photo_speaking_coach():
    """Guided 3-Layer Photo Speaking Coach (T-I-T formula spoken step by step or all together without timer panic)."""
    header()
    print(f"\n{BOLD}{MAGENTA}[SPEAKING COACH: FALA GUIADA SOBRE FOTO (FÓRMULA T-I-T PASSO A PASSO)]{RESET}")
    print(f"{DIM}Destrave o 'Speak About the Photo' descrevendo a imagem com a fórmula T-I-T na tela e feedback multimodal (Foto + Voz).{RESET}\n")

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    unseen_live = get_unseen_live_photos()
    chosen_file = random.choice(unseen_live) if unseen_live else fetch_dynamic_real_photo()

    valid_exts = (".jpg", ".jpeg", ".png", ".webp")
    photo_files = [f for f in os.listdir(PHOTOS_DIR) if f.lower().endswith(valid_exts)]
    if not photo_files:
        print(f"{RED}Nenhuma foto encontrada em {PHOTOS_DIR}.{RESET}")
        input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")
        return

    if not chosen_file:
        unseen_any = [f for f in photo_files if not is_item_seen("photo_speak_coach", f)]
        chosen_file = random.choice(unseen_any) if unseen_any else random.choice(photo_files)
    mark_item_seen("photo_speak_coach", chosen_file)

    photo_path = os.path.join(PHOTOS_DIR, chosen_file)
    photo_title = chosen_file.rsplit(".", 1)[0].replace("_", " ").title()
    mission = get_c1_lexical_mission(3)

    print_c1_mission_banner(mission)
    print(f"{BOLD}📐 SEU ROTEIRO VISUAL T-I-T (Fale olhando para este esqueleto):{RESET}")
    print(f"  1️⃣  {GREEN}{BOLD}[T] Visão Geral:{RESET}    \"This photograph captures a candid scene of [quem/o quê + -ing] in [lugar]...\"")
    print(f"  2️⃣  {GREEN}{BOLD}[I] Planos:{RESET}         \"In the foreground, we can observe [frente], whereas the background reveals [fundo]...\"")
    print(f"  3️⃣  {GREEN}{BOLD}[T] Atmosfera:{RESET}      \"The natural lighting conveys a sense of [foco/calma], suggesting that [hipótese]...\"")
    print(f"  {DIM}💡 (Se não souber o nome de um objeto da foto em inglês, fale em PORTUGUÊS mesmo que a IA traduz pra você!){RESET}\n")

    input(f"{GREEN}Pressione [ENTER] para abrir a foto na tela...{RESET}")

    viewer_candidates = [
        os.path.join(SCRIPT_DIR, "det_photo_viewer.py"),
        os.path.join(SCRIPT_DIR, "det-photo-viewer"),
        os.path.expanduser("~/.local/bin/det-photo-viewer")
    ]
    viewer_tool = next((p for p in viewer_candidates if os.path.exists(p)), None)
    viewer_proc = None
    if viewer_tool:
        try:
            viewer_proc = subprocess.Popen(
                [sys.executable, viewer_tool, photo_path, "300", f"SPEAKING COACH: {photo_title}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    captured = False
    audio_rec_path = os.path.join(tempfile.gettempdir(), "det_photo_speak_coach.wav")
    try:
        input(f"\n{CYAN}Observe a foto sem pressa. Quando estiver pronto, pressione [ENTER] para gravar suas 3 frases (60s)...{RESET}")
        print(f"\n{GREEN}{BOLD}>>> FALE AS 3 FRASES (T-I-T) DESCREVENDO A FOTO! (Ctrl+C ao concluir) <<<{RESET}")
        captured = record_mic_clip(audio_rec_path, 60, "Foto T-I-T Falada")
    except (KeyboardInterrupt, EOFError):
        return
    finally:
        if viewer_proc:
            try:
                viewer_proc.terminate()
            except Exception:
                pass

    if captured and get_gemini_key():
        print(f"\n{CYAN}🤖 Avaliando a FOTO REAL + SUA FALA no Gemini Multimodal...{RESET}")
        sys_inst = (
            "Você é um Coach Sênior do Duolingo English Test avaliando o treino guiado de 'Speak About the Photo' com a fórmula T-I-T.\n"
            "Você recebeu a FOTO REAL e o ÁUDIO do aluno (que pode ter usado palavras em português se não sabia algum objeto).\n"
            "Forneça:\n"
            "0. 📊 DIAGNÓSTICO DE PONTUAÇÃO (Escala DET 10-160 para Precisão Visual, Pronúncia/Fluência e Vocabulário):\n"
            "1. 🎙️ TRANSCRIÇÃO DO QUE VOCÊ FALOU + TRADUÇÃO DE TERMOS DA FOTO (Liste os objetos/ações da imagem que o aluno falou em português ou hesitou, dando o vocabulário exato em inglês B2/C1 com pronúncia figurada):\n"
            "2. 🔄 UPGRADE NAS 3 CAMADAS T-I-T (Mostre como cada uma das 3 frases faladas fica em B2 natural e C1 avançado fiel à foto):\n"
            "3. 👄 DICAS DE PRONÚNCIA (Palavras que precisam de atenção fonética):\n"
            "4. 🎯 Coloque a melhor frase C1 descritiva da foto sozinha em uma linha após o marcador EXATO 'SPEAK_MODEL: '.\n"
            "5. Ao final absoluto, inclua: [DET_EVAL: CONVERSATION=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )
        ai_resp = analyze_audio_with_gemini(
            audio_rec_path,
            f"Guided T-I-T Photo Speaking ({photo_title})",
            image_path=photo_path,
            custom_sys_inst=sys_inst
        )
        if ai_resp:
            print(f"\n{BOLD}{MAGENTA}══════════════════════════════════════════════════════════════════════{RESET}")
            print(ai_resp)
            print(f"{BOLD}{MAGENTA}══════════════════════════════════════════════════════════════════════{RESET}\n")
            evaluate_c1_mission_and_cliches(ai_resp, mission)

            conv_score, prod_score = extract_eval_scores(ai_resp, default_conv=85, default_prod=85)
            record_skill_score("conversation", conv_score)
            record_skill_score("production", prod_score)
            print_speaking_coach_scorecard(conv_score, prod_score, mode_label="FOTO T-I-T FALADA")

            model_s = _extract_speak_model_sentence(ai_resp)
            push_to_anki(
                subdeck_name="Speaking Feedback",
                front_html=f"<b>[DET Photo Speaking Coach: T-I-T]</b><br><br><b>Foto:</b> {photo_title}",
                back_html=f"<h3>Coaching Multimodal ({conv_score}/160):</h3><div style='text-align:left;'>{ai_resp.replace(chr(10), '<br>')}</div>",
                tags=["DET", "DET_PhotoSpeakingCoach"],
                audio_text=model_s or None
            )
            _offer_speaking_second_shot(f"Photo T-I-T: {photo_title}", ai_resp, photo_path=photo_path)

    update_streak()
    input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")


def _run_shadowing_pronunciation_lab():
    """Interactive Shadowing, Prosody & Pronunciation Lab using C1 structures and academic sentences."""
    while True:
        header()
        print(f"\n{BOLD}{MAGENTA}[🔁 LABORATÓRIO DE SHADOWING, PRONÚNCIA & RITMO (A-P-F-U / T-I-T / C1)]{RESET}")
        print(f"{DIM}Destrave a musculatura da fala: ouça a voz nativa, repita em voz alta no microfone e receba diagnóstico fonético imediato.{RESET}\n")

        print(f"  {BOLD}1){RESET} 📐 Treinar Pronúncia das 7 Estruturas-Chave (A-P-F-U da Redação/Fala & T-I-T da Foto)")
        print(f"  {BOLD}2){RESET} 🎲 Frase Acadêmica B2/C1 Sortida do Exame (Ditado/Leitura em Voz Alta)")
        print(f"  {BOLD}3){RESET} ✍️  Digitar ou Colar qualquer frase personalizada para treinar pronúncia")
        print(f"  {BOLD}0){RESET} Voltar ao Speaking Coach")

        try:
            choice = input(f"\n{CYAN}Escolha o modo do Shadowing Lab (0-3): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "0":
            break
        elif choice == "1":
            print(f"\n{BOLD}Escolha qual estrutura C1 deseja dominar na fala:{RESET}")
            for i, item in enumerate(C1_STRUCTURE_DECK, 1):
                print(f"  {BOLD}{i}){RESET} [{item['code']}] {GREEN}{item['example']}{RESET}")
            try:
                idx_s = input(f"\n{CYAN}Número da estrutura [1-{len(C1_STRUCTURE_DECK)}, ENTER=aleatória]: {RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                continue
            if idx_s.isdigit() and 1 <= int(idx_s) <= len(C1_STRUCTURE_DECK):
                chosen_item = C1_STRUCTURE_DECK[int(idx_s) - 1]
            else:
                chosen_item = random.choice(C1_STRUCTURE_DECK)
            target_sentence = chosen_item["example"]
            target_label = f"{chosen_item['code']} — {chosen_item['title']}"
        elif choice == "2":
            lt_item = get_random_listen_type_from_pool()
            target_sentence = lt_item["audio"] if isinstance(lt_item, dict) else str(lt_item)
            target_label = "Frase Acadêmica Oficial DET (B2/C1)"
        elif choice == "3":
            try:
                target_sentence = input(f"\n{CYAN}Digite a frase em inglês que deseja treinar falar:\n> {RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                continue
            if not target_sentence:
                continue
            target_label = "Frase Personalizada"
        else:
            continue

        print(f"\n{BOLD}{CYAN}── {target_label} ──{RESET}")
        print(f"🎯 {BOLD}FRASE-ALVO PARA LER EM VOZ ALTA:{RESET}")
        print(f"   {GREEN}{BOLD}\"{target_sentence}\"{RESET}\n")

        while True:
            print(f"{CYAN}🔊 Tocando áudio nativo... Preste atenção nas conexões entre palavras (linking) e na entonação!{RESET}")
            speak_text(target_sentence)
            try:
                act = input(f"\nDigite {BOLD}'o'{RESET} para ouvir de novo, {GREEN}{BOLD}[ENTER]{RESET} para gravar sua voz (15s), ou {BOLD}'v'{RESET} para voltar: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                break
            if act == "o":
                continue
            if act == "v":
                break

            print(f"\n{GREEN}{BOLD}>>> LEIA A FRASE EM VOZ ALTA COM CONFIANÇA! (15s — Ctrl+C ao terminar) <<<{RESET}")
            print(f"   {YELLOW}\"{target_sentence}\"{RESET}\n")
            sh_path = os.path.join(tempfile.gettempdir(), "det_shadow_lab.wav")
            if record_mic_clip(sh_path, 15, "Shadowing Lab"):
                if get_gemini_key():
                    print(f"{CYAN}🤖 Analisando fonética, sílabas tônicas, ritmo (WPM) e clareza acústica...{RESET}")
                    lab_sys = (
                        "Você é um Especialista em Fonética Inglesa para Brasileiros e Examinador do DET.\n"
                        "Compare o áudio gravado pelo aluno com a FRASE-ALVO exata.\n"
                        "Responda de forma prática e encorajadora:\n"
                        "1. 🎯 PRECISÃO FONÉTICA GERAL (0% a 100%) & VELOCIDADE/RITMO (Natural, Pausado demais, ou Apressado):\n"
                        "2. 🎙️ O QUE FOI OUVIDO vs. ALVO (Destaque se alguma palavra soou como outra):\n"
                        "3. 👄 CORREÇÃO FONÉTICA PALAVRA POR PALAVRA (Para cada palavra que teve desvio de pronúncia, mostre:\n"
                        "   - Palavra | Como você pronunciou | Como pronunciar certo [transcrição figurada intuitiva p/ brasileiros, ex: 'mitigates -> MÍ-ti-gueits'])\n"
                        "4. 🔗 DICA DE LINKING SOUNDS (Mostre onde juntar o som final de uma palavra com a vogal da seguinte nesta frase para soar fluido como nativo):\n"
                        "Ao final, inclua: [DET_EVAL: CONVERSATION=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
                    )
                    fb = analyze_audio_with_gemini(sh_path, f"Target Sentence for Shadowing: {target_sentence}", custom_sys_inst=lab_sys)
                    if fb:
                        print(f"\n{BOLD}{GREEN}══════════════════════════════════════════════════════════════════════{RESET}")
                        print(fb)
                        print(f"{BOLD}{GREEN}══════════════════════════════════════════════════════════════════════{RESET}")
                        c_sc, p_sc = extract_eval_scores(fb, default_conv=90, default_prod=90)
                        record_skill_score("conversation", c_sc)
                        print_speaking_coach_scorecard(c_sc, p_sc, mode_label="SHADOWING & PRONÚNCIA")

            try:
                retry = input(f"\n{CYAN}Deseja tentar falar a MESMA frase novamente para bater 100%? [s/N]: {RESET}").strip().lower()
            except (KeyboardInterrupt, EOFError):
                break
            if retry not in ["s", "sim", "y", "yes"]:
                break


def _run_spoken_pt_to_c1_bridge():
    """Voice-to-Voice Idea Bridge: Student speaks an idea in Portuguese/B1 into the mic -> hears & repeats B2/C1 English."""
    header()
    print(f"\n{BOLD}{MAGENTA}[🌉 PONTE DE FALA INSTANTÂNEA (FALE EM PORTUGUÊS/B1 ➔ DESTRAVE EM INGLÊS B2/C1)]{RESET}")
    print(f"{DIM}Travou e não sabe como falar um pensamento em inglês?{RESET}")
    print(f"{DIM}Fale no microfone em PORTUGUÊS (ou inglês misturado), ouça como um candidato C1 falaria e repita em voz alta!{RESET}\n")

    if not get_gemini_key():
        print(f"{YELLOW}⚠️ Configure sua chave do Gemini na opção S) Configurações para usar a Ponte de Fala IA.{RESET}")
        input(f"\n{DIM}Pressione [ENTER] para voltar...{RESET}")
        return

    while True:
        try:
            cmd = input(f"{CYAN}🎙️  Pressione {GREEN}{BOLD}[ENTER]{RESET}{CYAN} para falar sua ideia no microfone (20s) ou digite {BOLD}'q'{RESET}{CYAN} para sair: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break
        if cmd in ["q", "0", "sair"]:
            break

        print(f"\n{GREEN}{BOLD}>>> FALE SUA IDEIA AGORA (em Português, Inglês ou misturado)! (Ctrl+C ao terminar) <<<{RESET}")
        bridge_audio = os.path.join(tempfile.gettempdir(), "det_voice_bridge_in.wav")
        if not record_mic_clip(bridge_audio, 20, "Capturando sua ideia"):
            print(f"{YELLOW}Áudio não detectado. Tente novamente.{RESET}\n")
            continue

        print(f"{CYAN}🤖 Ouvindo sua ideia e construindo a versão falada B2 e C1...{RESET}")
        bridge_sys = (
            "Você é um Coach Oficial de Fala do Duolingo English Test (DET).\n"
            "O aluno gravou um áudio dizendo uma ideia (em português, inglês básico ou misturado) que ele quer aprender a falar na prova.\n"
            "Responda com clareza:\n"
            "1. 🎙️ IDEIA CAPTURADA: Transcreva o que o aluno disse.\n"
            "2. 🟢 COMO FALAR NO NÍVEL B2 (Natural, direto e fácil de lembrar sob pressão + guia de pronúncia figurada das palavras-chave):\n"
            "3. 🚀 COMO FALAR NO NÍVEL C1 (Padrão 120+ DET, com conectivos e collocations elegantes + guia de pronúncia figurada):\n"
            "4. 🧩 3 CHUNKS / BLOCOS DE FALA (Destaque 3 expressões prontas dessa frase para ele reutilizar em outros temas):\n"
            "5. Coloque a frase recomendada para ele repetir em voz alta sozinha em uma linha após o marcador EXATO 'SPEAK_MODEL: '."
        )
        resp = analyze_audio_with_gemini(bridge_audio, "Voice Idea Bridge (PT/B1 to Spoken English B2/C1)", custom_sys_inst=bridge_sys)
        if resp:
            print(f"\n{GREEN}{BOLD}──────────────────────────────────────────────────────────────────────{RESET}")
            print(resp)
            print(f"{GREEN}{BOLD}──────────────────────────────────────────────────────────────────────{RESET}\n")

            model_s = _extract_speak_model_sentence(resp)
            if model_s:
                push_to_anki(
                    subdeck_name="Speaking Feedback",
                    front_html=f"<b>[DET Voice Bridge: Como falar em Inglês B2/C1?]</b><br><br><i>Transforme esta ideia em fala fluente:</i>",
                    back_html=f"<div style='text-align:left;'>{resp.replace(chr(10), '<br>')}</div>",
                    tags=["DET", "DET_VoiceBridge"],
                    audio_text=model_s
                )
                print(f"{YELLOW}📥 Card com áudio nativo enviado automaticamente para o seu Anki!{RESET}")
                print(f"\n{CYAN}🔊 Ouça como pronunciar a frase recomendada:{RESET}")
                print(f"   🎯 {GREEN}{BOLD}\"{model_s}\"{RESET}")
                speak_text(model_s)

                try:
                    rep = input(f"\n🎙️  Pressione {GREEN}{BOLD}[ENTER]{RESET} para REPETIR essa frase em voz alta (15s) e fixar na memória muscular (ou 'p' p/ pular): ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    break
                if rep != "p":
                    print(f"\n{GREEN}{BOLD}>>> REPITA EM INGLÊS AGORA! (Ctrl+C ao terminar) <<<{RESET}")
                    print(f"   🎯 {GREEN}\"{model_s}\"{RESET}\n")
                    rep_path = os.path.join(tempfile.gettempdir(), "det_voice_bridge_rep.wav")
                    if record_mic_clip(rep_path, 15, "Repetindo em Inglês"):
                        check_sys = (
                            "Avalie em no máximo 5 linhas a repetição do aluno para a frase-alvo.\n"
                            "Dê a nota de Precisão Fonética (0-100%), elogie os acertos e aponte qualquer palavra que precise de ajuste na pronúncia.\n"
                            "Ao final inclua: [DET_EVAL: CONVERSATION=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
                        )
                        rep_fb = analyze_audio_with_gemini(rep_path, f"Target Sentence: {model_s}", custom_sys_inst=check_sys)
                        if rep_fb:
                            print(f"\n{GREEN}✓ Feedback da sua pronúncia:{RESET}\n{rep_fb}\n")
                            c_sc, p_sc = extract_eval_scores(rep_fb, default_conv=95, default_prod=95)
                            record_skill_score("conversation", c_sc)
                            record_skill_score("production", p_sc)
                            print_speaking_coach_scorecard(c_sc, p_sc, mode_label="PONTE DE FALA (PT ➔ C1)")


def run_speaking_coach():
    """Main hub for Module K: Speaking Coach & Fluency Gym."""
    while True:
        header()
        stats = load_stats()
        speak_hist = stats.get("speaking_coach_scores", [])
        skills = stats.get("skills", {})
        conv_scores = skills.get("conversation", {}).get("scores", [])
        prod_scores = skills.get("production", {}).get("scores", [])

        print(f"\n{BOLD}{MAGENTA}[MÓDULO K: SPEAKING COACH & FLUENCY GYM (DESTRAVAR A FALA PASSO A PASSO)]{RESET}")
        print(f"{DIM}Perca o medo do microfone: construa a fala em blocos curtos, destrave a pronúncia e domine fotos faladas.{RESET}")

        if speak_hist:
            last_entry = speak_hist[-1]
            avg_sp = int(sum(x.get("overall", 80) for x in speak_hist[-5:]) / len(speak_hist[-5:]))
            recent_trail = " ➔ ".join(str(x.get("overall", 80)) for x in speak_hist[-5:])
            c_col = GREEN if avg_sp >= 95 else (YELLOW if avg_sp >= 80 else RED)
            print(f"{CYAN}📊 {BOLD}Seu Desempenho no Speaking Coach:{RESET} Última Nota: {BOLD}{last_entry.get('overall')}/160{RESET} ({last_entry.get('mode')}) | Média Recente: {c_col}{BOLD}{avg_sp}/160 pts{RESET}")
            print(f"{DIM}   Histórico recente: {recent_trail} pts (Meta UFRJ: 95-105 pts){RESET}\n")
        elif conv_scores or prod_scores:
            c_avg = int(sum(conv_scores[-3:]) / len(conv_scores[-3:])) if conv_scores else 75
            p_avg = int(sum(prod_scores[-3:]) / len(prod_scores[-3:])) if prod_scores else 85
            s_est = int((c_avg + p_avg) / 2)
            print(f"{CYAN}📊 {BOLD}Nível Atual de Fala (Dashboard):{RESET} ~{BOLD}{s_est}/160 pts{RESET} (Conversation: {c_avg} | Production: {p_avg}) — {DIM}Faça um treino abaixo para subir Conversation!{RESET}\n")
        else:
            print()

        print(f"  {BOLD}1){RESET} 🎙️  {BOLD}Construtor de Fala em 3 Blocos (25-35s){RESET} {DIM}(Tese ➔ Exemplo ➔ Conclusão; pode falar PT se travar!){RESET}")
        print(f"  {BOLD}2){RESET} 📸 {BOLD}Fala Guiada sobre Foto (Fórmula T-I-T){RESET}  {DIM}(Foto na tela + esqueleto de 3 frases + Visão/Voz IA){RESET}")
        print(f"  {BOLD}3){RESET} 🔁 {BOLD}Shadowing & Laboratório de Pronúncia{RESET}    {DIM}(Ouça voz nativa, repita no mic e corrija fonética/ritmo){RESET}")
        print(f"  {BOLD}4){RESET} 🌉 {BOLD}Ponte de Fala (Fale em PT ➔ Repita C1){RESET}  {DIM}(Diga sua ideia em português no mic, ouça e repita em inglês){RESET}")
        print(f"  {BOLD}5){RESET} ⏱️  {BOLD}Speak About the Photo Oficial (90s){RESET}     {DIM}(Simulador oficial DET: 20s preparo + 90s falando da foto){RESET}")
        print(f"  {BOLD}6){RESET} ⏱️  {BOLD}Speaking Simulator Oficial (90s){RESET}        {DIM}(Read, Then Speak & Listen, Then Speak cego + Second Shot){RESET}")
        print(f"  {BOLD}0){RESET} Voltar ao Menu Principal")

        try:
            sub = input(f"\n{CYAN}Escolha o treino do Speaking Coach (0-6): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if sub == "1":
            _run_scaffolded_speaking_coach()
        elif sub == "2":
            _run_scaffolded_photo_speaking_coach()
        elif sub == "3":
            _run_shadowing_pronunciation_lab()
        elif sub == "4":
            _run_spoken_pt_to_c1_bridge()
        elif sub == "5":
            run_speak_about_photo_official()
        elif sub == "6":
            run_speaking_drill()
        elif sub == "0":
            break

# ==============================================================================
# 9. DET SCORE DASHBOARD (4 SUBSCORES)
# ==============================================================================
def run_score_dashboard():
    header()
    stats = load_stats()
    skills = stats.get("skills", {})

    print(f"\n{BOLD}{CYAN}[DASHBOARD OFICIAL DET - METAS UFRJ 95-105 PTS]{RESET}\n")

    def calc_score(data):
        scores = data.get("scores", [])
        if scores:
            return int(sum(scores) / len(scores))
        attempts = data.get("attempts", 0)
        correct = data.get("correct", 0)
        if attempts == 0:
            return 80  # Baseline
        pct = (correct / attempts)
        return int(60 + (pct * 95))

    subscores = {}
    names_pt = {
        "literacy": "Literacy (Leitura & Escrita)",
        "comprehension": "Comprehension (Leitura & Audição)",
        "conversation": "Conversation (Audição & Fala)",
        "production": "Production (Escrita & Fala)"
    }

    for k in ["literacy", "comprehension", "conversation", "production"]:
        data = skills.get(k, {"attempts": 0, "correct": 0})
        att = data.get("attempts", 0)
        corr = data.get("correct", 0)
        score = calc_score(data)
        subscores[k] = score

        pct = min(100, int((score / 160) * 100))
        bar_len = int(pct / 100 * 25)
        bar = "█" * bar_len + "░" * (25 - bar_len)
        color = GREEN if score >= 95 else (YELLOW if score >= 85 else RED)

        if score >= 120:
            cefr_badge = f"{GREEN}C1 (Avançado){RESET}"
        elif score >= 95:
            cefr_badge = f"{GREEN}B2 (Meta UFRJ){RESET}"
        elif score >= 80:
            cefr_badge = f"{YELLOW}B1 (Intermediário){RESET}"
        elif score >= 50:
            cefr_badge = f"{RED}A2 (Básico){RESET}"
        else:
            cefr_badge = f"{RED}A1 (Iniciante){RESET}"

        scores = data.get("scores", [])
        detail_str = f"Média IA: {scores[-3:]}" if scores else f"Acurácia: {int(corr)}/{att}"

        print(f"{BOLD}{names_pt[k]}:{RESET} [{cefr_badge}]")
        print(f"  [{color}{bar}{RESET}] {BOLD}{score}/160 pts{RESET} ({detail_str})")

    avg_overall = int(sum(subscores.values()) / 4)
    print("\n" + "=" * 65)
    print(f"📊 {BOLD}SCORE GERAL ESTIMADO:{RESET} {BOLD}{avg_overall} / 160 PONTOS{RESET}")
    if avg_overall >= 105:
        print(f"{GREEN}{BOLD}🎉 PARABÉNS! Você está no topo da faixa B2/C1 da UFRJ!{RESET}")
    elif avg_overall >= 95:
        print(f"{GREEN}{BOLD}✓ META UFRJ ATINGIDA (95-105 pts)! Mantenha o streak diário.{RESET}")
    else:
        print(f"{YELLOW}⚠️  Abaixo da meta da UFRJ. Foque nos treinos de C-Test e Ditado para subir Literacy/Comprehension.{RESET}")

    seen_data = load_seen_history()
    weak_list = seen_data.get("weak_words", [])
    if weak_list:
        print(f"\n🎯 {BOLD}Foco da IA Adaptativa (Seus erros recentes em reciclagem):{RESET}")
        print(f"   {YELLOW}{', '.join(weak_list[-8:])}{RESET}")
    print("=" * 65)

    input(f"\n{DIM}Pressione [ENTER] para voltar ao menu...{RESET}")

# ==============================================================================
# 10. SETTINGS, AI CONFIG & MULTI-MACHINE GIT UPDATER
# ==============================================================================
REPO_PATH_CONFIG_FILE = os.path.join(DATA_DIR, "repo_path.txt")
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/silasms/det-drill/main"


def find_local_git_repo():
    """Finds the local det-drill git repository across Linux, macOS, and Windows."""
    candidates = []
    if os.path.exists(REPO_PATH_CONFIG_FILE):
        try:
            with open(REPO_PATH_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_p = f.read().strip()
                if saved_p:
                    candidates.append(saved_p)
        except Exception:
            pass

    candidates.extend([
        SCRIPT_DIR,
        os.path.expanduser("~/Documents/det-drill-pro"),
        os.path.expanduser("~/Documents/det-drill"),
        os.path.expanduser("~/det-drill-pro"),
        os.path.expanduser("~/det-drill"),
        os.path.expanduser("~/Desktop/det-drill-pro"),
        os.path.expanduser("~/Desktop/det-drill"),
        os.path.expanduser("~/projects/det-drill-pro"),
        os.path.expanduser("~/projects/det-drill"),
    ])

    for cand in candidates:
        if cand and os.path.isdir(os.path.join(cand, ".git")) and os.path.exists(os.path.join(cand, "det_drill.py")):
            try:
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(REPO_PATH_CONFIG_FILE, "w", encoding="utf-8") as f:
                    f.write(cand)
            except Exception:
                pass
            return cand
    return None


def _get_git_version_badge():
    repo_dir = find_local_git_repo()
    if not repo_dir:
        return f"{DIM}Standalone{RESET}"
    try:
        res = subprocess.run(
            ["git", "-C", repo_dir, "log", "-1", "--format=%h (%cr)"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=2
        )
        if res.returncode == 0 and res.stdout.strip():
            return f"{GREEN}{res.stdout.strip()}{RESET} {DIM}[{repo_dir}]{RESET}"
    except Exception:
        pass
    return f"{CYAN}{repo_dir}{RESET}"


def _install_binaries_from_dir(source_dir):
    """Copies det_drill.py and det_photo_viewer.py from source_dir into ~/.local/bin (or Windows wrapper)."""
    import stat
    src_drill = os.path.join(source_dir, "det_drill.py")
    src_viewer = os.path.join(source_dir, "det_photo_viewer.py")
    bin_dir = os.path.join(os.path.expanduser("~"), ".local", "bin")
    os.makedirs(bin_dir, exist_ok=True)

    if IS_WINDOWS:
        if os.path.exists(src_drill):
            shutil.copy2(src_drill, os.path.join(bin_dir, "det_drill.py"))
        if os.path.exists(src_viewer):
            shutil.copy2(src_viewer, os.path.join(bin_dir, "det_photo_viewer.py"))
    else:
        dst_drill = os.path.join(bin_dir, "det-drill")
        dst_viewer = os.path.join(bin_dir, "det-photo-viewer")
        if os.path.exists(src_drill):
            shutil.copy2(src_drill, dst_drill)
            st = os.stat(dst_drill)
            os.chmod(dst_drill, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        if os.path.exists(src_viewer):
            shutil.copy2(src_viewer, dst_viewer)
            st = os.stat(dst_viewer)
            os.chmod(dst_viewer, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def run_self_update(auto_restart=True):
    """Pulls the latest code from GitHub (git@github.com:silasms/det-drill.git), updates ~/.local/bin, and restarts."""
    print(f"\n{BOLD}{CYAN}🔄 [ATUALIZADOR MULTI-MÁQUINAS — DET DRILL PRO]{RESET}")
    repo_dir = find_local_git_repo()

    if repo_dir:
        print(f"📂 Repositório Git encontrado em: {BOLD}{repo_dir}{RESET}")
        print(f"{CYAN}⏳ Buscando atualizações do GitHub (git pull --rebase --autostash)...{RESET}")
        try:
            pull_res = subprocess.run(
                ["git", "-C", repo_dir, "pull", "--rebase", "--autostash"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30
            )
            print(f"{DIM}{(pull_res.stdout or '').strip()}{RESET}")
            if pull_res.returncode != 0:
                print(f"{YELLOW}⚠️ O git pull retornou código {pull_res.returncode}. Verifique sua conexão/SSH.{RESET}")
                return False
        except Exception as e:
            print(f"{RED}✗ Erro ao executar git pull: {e}{RESET}")
            return False

        _install_binaries_from_dir(repo_dir)
        # Also run sync_seed_data if install.py exists
        try:
            res_ver = subprocess.run(
                ["git", "-C", repo_dir, "log", "-1", "--format=%h - %s (%cr)"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=3
            )
            ver_info = res_ver.stdout.strip() if res_ver.returncode == 0 else "Atualizado"
        except Exception:
            ver_info = "Atualizado"

        print(f"\n{GREEN}{BOLD}✓ DET Drill Pro atualizado e instalado com sucesso em ~/.local/bin/det-drill!{RESET}")
        print(f"📌 {BOLD}Versão ativa:{RESET} {CYAN}{ver_info}{RESET}")
    else:
        print(f"{YELLOW}⚠️ Pasta do repositório Git local não encontrada automaticamente.{RESET}")
        print(f"{CYAN}⏳ Tentando atualização direta via GitHub HTTPS ({GITHUB_RAW_BASE_URL})...{RESET}")
        try:
            tmp_dir = tempfile.mkdtemp(prefix="det_update_")
            for fname in ["det_drill.py", "det_photo_viewer.py"]:
                url = f"{GITHUB_RAW_BASE_URL}/{fname}"
                req = urllib.request.Request(url, headers={"User-Agent": "DET-Drill-Updater/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content = resp.read()
                if len(content) > 1000:
                    with open(os.path.join(tmp_dir, fname), "wb") as out_f:
                        out_f.write(content)
            _install_binaries_from_dir(tmp_dir)
            print(f"\n{GREEN}{BOLD}✓ Executáveis atualizados diretamente do GitHub em ~/.local/bin/det-drill!{RESET}")
        except Exception as e:
            print(f"{RED}✗ Não foi possível baixar via HTTPS (o repositório pode ser privado via SSH): {e}{RESET}")
            print(f"{YELLOW}💡 Dica: Em outra máquina, clone o repositório em ~/Documents/det-drill-pro e rode ./install-linux-mac.sh uma vez.{RESET}")
            return False

    if auto_restart:
        try:
            ans = input(f"\n{GREEN}Deseja recarregar o det-drill agora com a nova versão? [S/n]: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            ans = "n"
        if ans not in ["n", "nao", "não", "no"]:
            print(f"{CYAN}🚀 Reiniciando det-drill...{RESET}\n")
            time.sleep(0.5)
            target_bin = os.path.expanduser("~/.local/bin/det-drill")
            if not IS_WINDOWS and os.path.exists(target_bin):
                os.execv(sys.executable, [sys.executable, target_bin])
            else:
                os.execv(sys.executable, [sys.executable] + sys.argv)
    return True


def run_settings():
    while True:
        header()
        print(f"\n{BOLD}[PAINEL DE CONFIGURAÇÕES, CONEXÕES & ATUALIZAÇÃO]{RESET}\n")
        anki_status = f"{GREEN}ONLINE{RESET}" if is_anki_online() else f"{RED}OFFLINE{RESET}"
        gemini_k = get_gemini_key()
        gemini_disp = f"{GREEN}Ativa (...{gemini_k[-6:]}){RESET}" if gemini_k else f"{YELLOW}Não configurada{RESET}"
        pending_count = len(load_pending_cards())
        git_badge = _get_git_version_badge()

        print(f"  1) Status AnkiConnect: {anki_status}")
        print(f"  2) Forçar Inicialização do Anki e Sincronizar ({pending_count} cards pendentes)")
        print(f"  3) Google Gemini AI Key: {gemini_disp}")
        print(f"  4) Testar Síntese de Voz (TTS Áudio)")
        print(f"  5) Testar Microfone (1s de gravação)")
        print(f"  6) 🔄 {GREEN}{BOLD}Atualizar DET Drill via Git (Multi-Máquinas){RESET} — Versão: {git_badge}")
        print(f"  0) Voltar ao Menu Principal")

        try:
            choice = input(f"\n{CYAN}Selecione uma opção (0-6): {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == "1":
            print(f"\nTestando AnkiConnect em {ANKI_URL}...")
            if is_anki_online(force=True):
                print(f"{GREEN}✓ Conexão bem-sucedida com o Anki!{RESET}")
            else:
                print(f"{RED}✗ Anki fechado. Iniciando Anki automaticamente...{RESET}")
                if ensure_anki_running():
                    print(f"{GREEN}✓ Anki iniciado e conectado com sucesso!{RESET}")
            time.sleep(2)
        elif choice == "2":
            ensure_anki_running()
            uploaded = flush_pending_cards()
            print(f"{GREEN}Sincronização concluída! {uploaded} card(s) enviados ao Anki.{RESET}")
            time.sleep(2)
        elif choice == "3":
            print("\nPara usar sua conta Google Pro, acesse https://aistudio.google.com")
            print("Gere uma API Key gratuita com sua conta Google e cole-a abaixo.")
            new_key = input("Cole sua Gemini API Key (ou pressione Enter para cancelar): ").strip()
            if new_key:
                set_gemini_key(new_key)
                print(f"{GREEN}Chave Gemini salva com sucesso!{RESET}")
            time.sleep(2)
        elif choice == "4":
            print(f"{CYAN}Falando frase teste...{RESET}")
            speak_text("Welcome to the Duolingo English Test training suite.")
            time.sleep(1)
        elif choice == "5":
            print(f"{CYAN}Gravando 1s do microfone padrão...{RESET}")
            test_path = os.path.join(tempfile.gettempdir(), "det_test_mic.wav")
            subprocess.run(get_ffmpeg_mic_cmd(test_path, 1), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(test_path) and os.path.getsize(test_path) > 1000:
                print(f"{GREEN}✓ Microfone capturado com sucesso! ({os.path.getsize(test_path)} bytes){RESET}")
                os.remove(test_path)
            else:
                print(f"{RED}✗ Falha ao capturar áudio do microfone.{RESET}")
            time.sleep(2)
        elif choice in ["6", "u", "U"]:
            run_self_update(auto_restart=True)
            input(f"\n{DIM}Pressione [ENTER] para continuar...{RESET}")
        elif choice in ["0", "7"]:
            break

# ==============================================================================
# BACKGROUND PRE-FETCHER (ZERO-LATENCY BUFFERING)
# ==============================================================================
_PREFETCH_ACTIVE = False

def _background_prefetch_task():
    global _PREFETCH_ACTIVE
    if _PREFETCH_ACTIVE:
        return
    _PREFETCH_ACTIVE = True
    try:
        # Always keep at least 2 unseen real photos pre-downloaded in background (0 Gemini API cost)
        if len(get_unseen_live_photos()) < 2:
            fetch_dynamic_real_photo()
        if get_gemini_key():
            if get_unseen_listen_type_from_archive() is None:
                generate_dynamic_listen_type_ai(6)
            elif get_unseen_c_test_from_archive() is None:
                generate_dynamic_c_test_ai()
            elif get_unseen_read_select_batch(6) is None:
                generate_dynamic_read_select_ai(12)
    except Exception:
        pass
    finally:
        _PREFETCH_ACTIVE = False

def trigger_background_prefetch():
    """Silently tops up local unseen exercise pools in a background daemon thread."""
    if get_gemini_key() and not _PREFETCH_ACTIVE:
        t = threading.Thread(target=_background_prefetch_task, daemon=True)
        t.start()

# ==============================================================================
# MAIN ROUTINE
# ==============================================================================
def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["--update", "-u", "update", "pull"]:
        run_self_update(auto_restart=False)
        return

    if is_anki_online():
        flush_pending_cards()

    while True:
        trigger_background_prefetch()
        header()
        print(f"\n{BOLD}Escolha seu treino ativo de hoje:{RESET}\n")
        print(f"  {BOLD}1){RESET} Read & Complete     {DIM}(Fill in the blanks - C-Test Inédito + Navegação Livre){RESET}")
        print(f"  {BOLD}2){RESET} C-Test Modo Offline {DIM}(Banco fixo clássico sem IA){RESET}")
        print(f"  {BOLD}3){RESET} Read & Select       {DIM}(Real vs Fake Words - Lotes Inéditos via IA){RESET}")
        print(f"  {BOLD}4){RESET} Listen & Type       {DIM}(Ditado com Voz Humana + Diff Colorido + Fixação Ativa){RESET}")
        print(f"  {BOLD}5){RESET} Interactive Writing {DIM}(5 min Etapa 1 + 3 min Follow-up Oficial + Missão C1){RESET}")
        print(f"  {BOLD}6){RESET} Interactive Reading {DIM}(Simulador Oficial de 4 Etapas do DET via IA){RESET}")
        print(f"  {BOLD}7){RESET} Vocab & Transitions {DIM}(Conectivos & Vocab B2/C1 em Lotes via IA){RESET}")
        print(f"  {BOLD}8){RESET} Speaking Simulator  {DIM}(Read/Listen Then Speak + Speak About Photo 90s + Second Shot){RESET}")
        print(f"  {BOLD}9){RESET} Write About Photo   {DIM}(1 min - Visão Multimodal + Missão C1 + Fixação Ativa){RESET}")
        print(f"  {BOLD}L){RESET} {CYAN}{BOLD}Interactive Listen{RESET}  {DIM}(Diálogo Acadêmico + Summarize the Conversation 75s){RESET}")
        print(f"  {BOLD}W){RESET} {GREEN}{BOLD}Writing Coach{RESET}       {DIM}(Destravar Escrita: 4 Frases + Foto 3 Frases + Estruturas C1){RESET}")
        print(f"  {BOLD}K){RESET} {MAGENTA}{BOLD}Speaking Coach{RESET}      {DIM}(Destravar Fala: 3 Blocos + Foto T-I-T + Shadowing + Ponte PT➔C1){RESET}")
        print(f"  {BOLD}D){RESET} {CYAN}{BOLD}Dashboard DET{RESET}       {DIM}(Projeção das 4 Subnotas UFRJ + IA Adaptativa){RESET}")
        print(f"  {BOLD}S){RESET} Configurações       {DIM}(Anki + Google Gemini + Mic + 🔄 Atualizar via Git [U]){RESET}")
        print(f"  {BOLD}0){RESET} Sair")

        try:
            choice = input(f"\n{CYAN}Selecione uma opção: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            wait_anki_queue()
            print("\nAté logo e bons estudos!")
            break

        if choice == "1":
            run_c_test(force_ai=True)
        elif choice == "2":
            run_c_test(force_ai=False)
        elif choice == "3":
            run_read_select()
        elif choice == "4":
            run_listen_type()
        elif choice == "5":
            run_writing_prompt()
        elif choice == "6":
            run_interactive_reading()
        elif choice == "7":
            run_vocab_drill()
        elif choice == "8":
            run_speaking_drill()
        elif choice == "9":
            run_photo_writing()
        elif choice.lower() in ["l", "10"]:
            run_interactive_listening()
        elif choice.lower() == "w":
            run_writing_coach()
        elif choice.lower() == "k":
            run_speaking_coach()
        elif choice.lower() == "d":
            run_score_dashboard()
        elif choice.lower() == "s":
            run_settings()
        elif choice.lower() == "u":
            run_self_update(auto_restart=True)
            input(f"\n{DIM}Pressione [ENTER] para continuar...{RESET}")
        elif choice == "0":
            wait_anki_queue()
            print(f"\n{GREEN}Treino encerrado. Mantenha a consistência rumo à aprovação na UFRJ!{RESET}\n")
            try:
                rev = input("Deseja abrir a janela do Anki agora para revisar os novos cards? [s/N]: ").strip().lower()
                if rev in ["s", "sim", "y"]:
                    if IS_MACOS:
                        subprocess.Popen(["open", "-a", "Anki"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        subprocess.Popen(["anki"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            break

if __name__ == "__main__":
    main()
