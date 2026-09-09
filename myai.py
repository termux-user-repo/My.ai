#!/usr/bin/env python3
"""
my.ai backend — a free, open-source, local AI API server.
No API key. No cloud. Works on PC, Linux, and Android (Termux).

This is a STANDALONE backend. It knows nothing about any frontend —
it just exposes a JSON API over HTTP. Point any client at it: the
included index.html, curl, a mobile app, whatever. CORS is wide open
so index.html can even be opened directly as a local file (file://)
and still talk to this server.

Brain modes (auto-detected, in order of preference):
  1. Ollama (if installed + running)  -> real local LLM, best quality
  2. Built-in lightweight brain        -> pure Python, zero dependencies, always works

Usage:
    python3 myai.py
The API will be listening on http://0.0.0.0:8420 (see printed URLs).

Only standard library is used — nothing to pip install, nothing to configure.

API:
    GET  /api/status   -> { ollama: bool, model: str }
    GET  /api/history  -> { history: [...] }
    POST /api/chat      body: { "message": "..." }
                        -> { reply: str, engine: "ollama"|"lite" }
"""

import json
import os
import random
import re
import socket
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

PORT = int(os.environ.get("MYAI_PORT", "8420"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
HISTORY_FILE = Path.home() / ".myai_history.json"
MAX_HISTORY_TURNS = 12  # how many past exchanges get sent as context

SYSTEM_PROMPT = (
    "You are my.ai, a friendly, direct, open-source personal assistant "
    "running entirely on the user's own device. Be concise, warm, and honest. "
    "If you don't know something, say so plainly instead of guessing."
)

# --------------------------------------------------------------------------
# Ollama bridge (used only if Ollama is actually running — never required)
# --------------------------------------------------------------------------

def ollama_is_available():
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def ollama_chat(messages):
    """Streams a response from Ollama's /api/chat endpoint. Returns full text or None on failure."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "").strip() or None
    except Exception as e:
        print(f"[myai] Ollama request failed, falling back: {e}")
        return None


# --------------------------------------------------------------------------
# Built-in lightweight brain — pure Python, no dependencies, always available.
# Not a real LLM — a transparent rule + pattern based assistant. Honest about
# its own limits rather than pretending to be something it isn't.
# --------------------------------------------------------------------------

class LiteBrain:
    GREETINGS = ["hi", "hello", "hey", "yo", "sup", "hola", "morning", "evening"]

    FAREWELLS = ["bye", "goodbye", "see ya", "later", "cya", "night"]

    THANKS = ["thanks", "thank you", "thx", "appreciate it", "cheers"]

    IDENTITY_Q = ["who are you", "what are you", "your name", "what is myai", "what's myai"]

    CAPABILITY_Q = ["what can you do", "what do you do", "help me", "capabilities", "features"]

    def __init__(self):
        self.memory = {}  # per-process short-term facts, e.g. name

    def _match_any(self, text, options):
        t = text.lower()
        return any(o in t for o in options)

    def _try_math(self, text):
        # Very small, safe arithmetic evaluator — digits/operators only.
        cleaned = text.lower().replace("what is", "").replace("what's", "").replace("=", "").strip()
        if re.fullmatch(r"[0-9\.\s\+\-\*\/\(\)%]+", cleaned) and any(c.isdigit() for c in cleaned):
            try:
                # eval is safe here: input is restricted to digits/operators by the regex above
                result = eval(cleaned, {"__builtins__": {}}, {})
                return f"{cleaned.strip()} = {result}"
            except Exception:
                return None
        return None

    def _remember_name(self, text):
        m = re.search(r"\bmy name is ([a-zA-Z][a-zA-Z\-' ]{0,30})", text, re.IGNORECASE)
        if m:
            name = m.group(1).strip().split()[0]
            self.memory["name"] = name
            return f"Nice to meet you, {name}. I'll remember that for this session."
        return None

    def reply(self, text, history=None):
        text = text.strip()
        if not text:
            return "I'm listening — go ahead."

        remembered = self._remember_name(text)
        if remembered:
            return remembered

        if "your name" in text.lower() and "my name" not in text.lower():
            pass  # handled by IDENTITY_Q below

        if self._match_any(text, self.IDENTITY_Q):
            return (
                "I'm my.ai — a free, open-source assistant that runs entirely on your own "
                "device. Right now I'm using my lightweight built-in brain (no internet, "
                "no API key). If you install Ollama and pull a model, I'll switch to using "
                "that automatically for much better conversations."
            )

        if self._match_any(text, self.CAPABILITY_Q):
            return (
                "In lightweight mode I can chat, do basic arithmetic, remember your name "
                "for this session, and hold a simple conversation. I'm honest about not "
                "being a full language model in this mode — for real depth, install Ollama "
                "(ollama.com) and pull any model, e.g. `ollama pull llama3.2`, and I'll use "
                "it automatically next time you talk to me."
            )

        math_result = self._try_math(text)
        if math_result:
            return math_result

        if self._match_any(text, self.GREETINGS) and len(text.split()) <= 4:
            name = self.memory.get("name")
            greeting = random.choice([
                "Hey! What's on your mind?",
                "Hi there — what can I help with?",
                "Hello. I'm here.",
            ])
            return f"{greeting[:-1]}, {name}." if name else greeting

        if self._match_any(text, self.FAREWELLS):
            return random.choice(["Take care.", "See you next time.", "Bye for now."])

        if self._match_any(text, self.THANKS):
            return random.choice(["Anytime.", "You're welcome.", "Happy to help."])

        if text.endswith("?"):
            return (
                "That's a real question and I don't want to fake an answer — my lightweight "
                "brain doesn't have general knowledge built in. Install Ollama for genuine "
                "answers, or ask me something I can actually help with directly (math, "
                "conversation, or remembering things for this session)."
            )

        # Generic honest fallback — reflect + invite more rather than pretend understanding.
        reflections = [
            f"Got it — you said: \"{text}\". Tell me more about what you need from that.",
            "I hear you. Can you say a bit more so I can actually help?",
            "Noted. What would be most useful to do with that right now?",
        ]
        return random.choice(reflections)


lite_brain = LiteBrain()

# --------------------------------------------------------------------------
# History persistence (local JSON file — never leaves the device)
# --------------------------------------------------------------------------

def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            return []
    return []


def save_history(history):
    try:
        HISTORY_FILE.write_text(json.dumps(history[-200:], indent=2))
    except Exception as e:
        print(f"[myai] could not save history: {e}")


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep terminal quiet; comment out to debug

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # CORS preflight — lets index.html be hosted anywhere (or opened as a
        # local file) and still call this API cross-origin.
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/api":
            self._send_json({
                "service": "my.ai backend",
                "endpoints": ["/api/status", "/api/history", "/api/chat (POST)"],
            })
        elif self.path == "/api/status":
            self._send_json({
                "ollama": ollama_is_available(),
                "model": OLLAMA_MODEL if ollama_is_available() else "lite-brain",
            })
        elif self.path == "/api/history":
            self._send_json({"history": load_history()})
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/chat":
            self._send_json({"error": "not found"}, 404)
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send_json({"error": "bad json"}, 400)
            return

        user_text = (body.get("message") or "").strip()
        if not user_text:
            self._send_json({"error": "empty message"}, 400)
            return

        history = load_history()

        use_ollama = ollama_is_available()
        reply_text = None
        engine = "lite"

        if use_ollama:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for turn in history[-MAX_HISTORY_TURNS:]:
                messages.append({"role": "user", "content": turn["user"]})
                messages.append({"role": "assistant", "content": turn["assistant"]})
            messages.append({"role": "user", "content": user_text})

            reply_text = ollama_chat(messages)
            if reply_text:
                engine = "ollama"

        if not reply_text:
            reply_text = lite_brain.reply(user_text, history)
            engine = "lite"

        history.append({
            "user": user_text,
            "assistant": reply_text,
            "engine": engine,
            "ts": time.time(),
        })
        save_history(history)

        self._send_json({"reply": reply_text, "engine": engine})


# --------------------------------------------------------------------------
# Startup helpers
# --------------------------------------------------------------------------

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    brain_status = "Ollama (local LLM)" if ollama_is_available() else "Lite brain (built-in, offline)"
    lan_ip = get_lan_ip()

    print("=" * 60)
    print("  my.ai backend — open-source local AI API")
    print("=" * 60)
    print(f"  Brain:        {brain_status}")
    print(f"  API on this device:  http://127.0.0.1:{PORT}")
    print(f"  API on your network: http://{lan_ip}:{PORT}")
    print()
    print("  This is the backend only. Open index.html in a browser")
    print("  (double-click it, or host it separately) and point it at")
    print("  one of the URLs above.")
    print("=" * 60)
    print("  Press Ctrl+C to stop.")
    print()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[myai] Shutting down. Bye.")
        server.shutdown()


if __name__ == "__main__":
    main()
