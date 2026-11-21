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

def analyze_audio_with_gemini(audio_path, prompt_text):
    """Analyzes user's spoken audio directly via Gemini Multimodal API with fallback."""
    client = get_gemini_client()
    if not client or not os.path.exists(audio_path):
        return None
    try:
        from google.genai import types
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        sys_inst = (
            "Você é um Examinador Sênior Oficial do Duolingo English Test (DET). "
            "Avalie com rigor pedagógico e construtivo o áudio do candidato na questão de Speaking.\n\n"
            "Estruture sua resposta estritamente nas seguintes seções:\n"
            "1. 🎙️ TRANSCRIÇÃO EXATA:\n"
            "Transcreva palavra por palavra o que o candidato falou, indicando pausas longas e repetições.\n\n"
            "2. ⚡ FLUÊNCIA, ACÚSTICA & PRONÚNCIA:\n"
            "Avalie o ritmo, pausas silenciosas, hesitações e clareza da pronúncia.\n\n"
            "3. 📝 GRAMÁTICA & VOCABULÁRIO:\n"
            "Destaque erros gramaticais e estruturas incompletas, apresentando as correções formais.\n\n"
            "4. 📊 NOTA ESTIMADA DET (Escala 10 a 160) & NÍVEL CEFR:\n"
            "Dê uma estimativa realista dos subscores Conversation e Production (ex: 55-65/160, Nível A2).\n\n"
            "5. ✨ MODELO REFINADO B2/C1 (Meta UFRJ 95-105+):\n"
            "Apresente como o candidato deveria responder à mesma pergunta em 3 blocos estruturados e fluidos.\n\n"
            "IMPORTANTE: Ao final absoluto da sua mensagem, inclua obrigatoriamente a tag de pontuação no formato exato:\n"
            "[DET_EVAL: CONVERSATION=<nota_de_10_a_160>, PRODUCTION=<nota_de_10_a_160>]"
        )

        for model_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                        f"{sys_inst}\n\nTask Prompt: {prompt_text}"
                    ]
                )
                if response and response.text:
                    return response.text
            except Exception:
                continue
        return None
    except Exception as e:
        return f"[Erro ao analisar áudio com Gemini: {e}]"

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
        print(f"\n{BOLD}Questão {idx}/{len(questions)}:{RESET} [{CYAN}{q['word']}{RESET}] - {DIM}{q['type']}{RESET}")
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

        if user_idx == q["answer"]:
            print(f"{GREEN}✓ Correto!{RESET} {q['explanation']}")
            correct += 1
        else:
            print(f"{RED}✗ Incorreto.{RESET} A resposta certa era: {q['options'][q['answer']]}")
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

def run_speaking_drill(force_ai=True):
    header()
    print(f"\n{BOLD}{MAGENTA}[SKILL 8: SPEAKING SIMULATOR (READ/LISTEN, THEN SPEAK - 90s)]{RESET}")
    print("Escolha a modalidade oficial do DET que deseja treinar:")
    print(f"  {BOLD}1){RESET} Read, Then Speak   {DIM}(Pergunta escrita visível na tela){RESET}")
    print(f"  {BOLD}2){RESET} Listen, Then Speak {DIM}(Pergunta cega apenas em áudio - Oficial DET){RESET}")
    try:
        mode_choice = input(f"\n{CYAN}Modalidade [1/2, padrão=1]: {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
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
        print("Estrutura recomendada:")
        print("  1. Resposta direta (15s) | 2. Exemplo com 'for instance' (45s) | 3. Conclusão com 'ultimately' (30s)\n")
        input(f"{GREEN}Pressione [ENTER] para iniciar os 20s de PREPARAÇÃO mental...{RESET}")

    for remaining in range(20, 0, -1):
        print(f"\r{YELLOW}Preparação: {remaining:02d}s restantes...{RESET}", end="", flush=True)
        time.sleep(1)

    print(f"\a\n\n{GREEN}{BOLD}>>> COMECE A FALAR AGORA! MICROFONE ATIVO! <<<{RESET}\n")
    print(f"{DIM}(Se terminar antes dos 90 segundos, pressione [Ctrl+C] para encerrar e enviar para análise){RESET}\n")

    audio_rec_path = os.path.join(tempfile.gettempdir(), "det_speaking_rec.wav")
    if os.path.exists(audio_rec_path):
        os.remove(audio_rec_path)

    rec_proc = subprocess.Popen(
        get_ffmpeg_mic_cmd(audio_rec_path, 90),
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    try:
        for remaining in range(90, 0, -1):
            mins, secs = divmod(remaining, 60)
            bar_len = int((90 - remaining) / 90 * 30)
            progress = "█" * bar_len + "░" * (30 - bar_len)
            color = GREEN if remaining > 30 else (YELLOW if remaining > 10 else RED)
            print(f"\r[{progress}] Gravando áudio: {color}{mins:02d}:{secs:02d}{RESET} restantes...", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nGravação finalizada pelo usuário.")
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

    print(f"\a\n\n{CYAN}{BOLD}ÁUDIO CAPTURADO COM SUCESSO!{RESET}")
    if blind_audio_mode:
        print(f"\n{BOLD}📜 Revelando a Pergunta Auditiva Original:{RESET}")
        print(f"{YELLOW}{prompt}{RESET}")

    gemini_key = get_gemini_key()
    if gemini_key and os.path.exists(audio_rec_path) and os.path.getsize(audio_rec_path) > 10000:
        print(f"\n{CYAN}🤖 Enviando seu áudio para a IA do Google Gemini (Análise Multimodal)...{RESET}")
        ai_feedback = analyze_audio_with_gemini(audio_rec_path, prompt)
        if ai_feedback:
            print(f"\n{BOLD}{CYAN}AVALIAÇÃO DA BANCA DET (SPEAKING):{RESET}")
            print(ai_feedback)
            evaluate_c1_mission_and_cliches(ai_feedback, mission)

            front = f"<b>[DET: Speaking Simulator]</b><br><br><b>Pergunta:</b> {prompt}<br><br><i>[Feedback da sua fala]</i>"
            back = f"<h3>Análise da IA:</h3><div style='text-align:left;'>{ai_feedback.replace(chr(10), '<br>')}</div>"
            push_to_anki(
                subdeck_name="Speaking Feedback",
                front_html=front,
                back_html=back,
                tags=["DET", "DET_Speaking"]
            )
            print(f"\n{YELLOW}📥 Análise de fala enviada ao Anki em segundo plano!{RESET}")

            conv_score, prod_score = extract_eval_scores(ai_feedback)
            record_skill_score("conversation", conv_score)
            record_skill_score("production", prod_score)
            print(f"\n{BOLD}📊 Subscores Oficiais Registrados no Dashboard DET:{RESET}")
            print(f"  • Conversation: {CYAN}{conv_score}/160 pts{RESET}")
            print(f"  • Production:   {CYAN}{prod_score}/160 pts{RESET}")
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
# 10. SETTINGS & AI CONFIG
# ==============================================================================
def run_settings():
    while True:
        header()
        print(f"\n{BOLD}[PAINEL DE CONFIGURAÇÕES & CONEXÕES]{RESET}\n")
        anki_status = f"{GREEN}ONLINE{RESET}" if is_anki_online() else f"{RED}OFFLINE{RESET}"
        gemini_k = get_gemini_key()
        gemini_disp = f"{GREEN}Ativa (...{gemini_k[-6:]}){RESET}" if gemini_k else f"{YELLOW}Não configurada{RESET}"
        pending_count = len(load_pending_cards())

        print(f"  1) Status AnkiConnect: {anki_status}")
        print(f"  2) Forçar Inicialização do Anki e Sincronizar ({pending_count} cards pendentes)")
        print(f"  3) Google Gemini AI Key: {gemini_disp}")
        print(f"  4) Testar Síntese de Voz (TTS Áudio)")
        print(f"  5) Testar Microfone (1s de gravação)")
        print(f"  6) Voltar ao Menu Principal")

        choice = input(f"\n{CYAN}Selecione uma opção (1-6): {RESET}").strip()

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
        elif choice == "6":
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
        print(f"  {BOLD}8){RESET} Speaking Simulator  {DIM}(Read/Listen Then Speak Cego + Missão C1 + Voz IA){RESET}")
        print(f"  {BOLD}9){RESET} Write About Photo   {DIM}(1 min - Visão Multimodal + Missão C1 + Fixação Ativa){RESET}")
        print(f"  {BOLD}L){RESET} {CYAN}{BOLD}Interactive Listen{RESET}  {DIM}(Diálogo Acadêmico + Summarize the Conversation 75s){RESET}")
        print(f"  {BOLD}D){RESET} {MAGENTA}{BOLD}Dashboard DET{RESET}       {DIM}(Projeção das 4 Subnotas UFRJ + IA Adaptativa){RESET}")
        print(f"  {BOLD}S){RESET} Configurações       {DIM}(Anki + Google Gemini + Mic){RESET}")
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
        elif choice.lower() == "d":
            run_score_dashboard()
        elif choice.lower() == "s":
            run_settings()
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
