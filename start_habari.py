#!/usr/bin/env python3
"""HABARI AI Studio local prototype.

Uses a separately running, self-hosted KokoroTTS server at http://127.0.0.1:7860.
Only Python's standard library is required for this small web interface.
"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import os
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
KOKORO_URL = os.environ.get("KOKORO_URL", "http://127.0.0.1:7860").rstrip("/")
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Conservative prototype chunk size. Long-project job management comes later.
CHUNK_CHARS = 1800
MAX_CHARS = 12000  # short prototype safeguard; 60-minute projects are a later milestone.
VOICES = {"am_onyx", "am_michael", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_puck", "am_santa"}

def split_text(text, limit=CHUNK_CHARS):
    """Split on paragraph/sentence boundaries where possible."""
    remaining = text.strip()
    chunks = []
    while len(remaining) > limit:
        cut = max(
            remaining.rfind("\n\n", 0, limit),
            remaining.rfind(". ", 0, limit),
            remaining.rfind("? ", 0, limit),
            remaining.rfind("! ", 0, limit),
        )
        if cut < limit // 2:
            cut = limit
        else:
            cut += 1
        part = remaining[:cut].strip()
        if part:
            chunks.append(part)
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks

def synthesize(text, voice, target):
    payload = json.dumps({
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "response_format": "mp3",
        "speed": 1.0
    }).encode("utf-8")
    req = Request(
        f"{KOKORO_URL}/v1/audio/speech",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    api_key = os.environ.get("KOKOROTTS_API_KEY")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    with urlopen(req, timeout=900) as response:
        audio = response.read()
    if not audio:
        raise RuntimeError("The speech server returned an empty audio file.")
    target.write_bytes(audio)

def join_mp3(parts, output):
    if len(parts) == 1:
        shutil.copyfile(parts[0], output)
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "This script was split into multiple audio parts. Install FFmpeg and add it to PATH "
            "to join MP3 parts automatically. For this first test, try a shorter paragraph."
        )
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        list_file = Path(temp_dir) / "parts.txt"
        lines = []
        for part in parts:
            safe_path = str(part.resolve()).replace("\\", "/").replace("'", r"'\''")
            lines.append(f"file '{safe_path}'")
        list_file.write_text("\n".join(lines), encoding="utf-8")
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-vn", "-codec:a", "libmp3lame", "-q:a", "2", str(output)
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError("FFmpeg could not join the audio parts: " + completed.stderr[-1200:])

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt, *args):
        print("[HABARI]", fmt % args)

    def do_GET(self):
        if self.path == "/api/health":
            self.send_json(200, {"ok": True, "kokoro_url": KOKORO_URL})
            return
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/generate":
            self.send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 200_000:
                self.send_json(400, {"error": "Please provide a text script under 200 KB."})
                return
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            text = str(data.get("text", "")).strip()
            voice = str(data.get("voice", "am_onyx"))
            if not text:
                self.send_json(400, {"error": "Paste a script first."})
                return
            if len(text) > MAX_CHARS:
                self.send_json(400, {"error": f"This prototype is limited to {MAX_CHARS:,} characters. The 60-minute workflow will be added after the short test works."})
                return
            if voice not in VOICES:
                self.send_json(400, {"error": "Please choose one of the listed American male voices."})
                return

            job_id = uuid.uuid4().hex[:12]
            chunks = split_text(text)
            with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
                temp = Path(temp_dir)
                parts = []
                for index, chunk in enumerate(chunks, start=1):
                    part = temp / f"part_{index:03d}.mp3"
                    synthesize(chunk, voice, part)
                    parts.append(part)
                output = OUTPUT_DIR / f"habari-voice-{job_id}.mp3"
                join_mp3(parts, output)

            audio = output.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(audio)))
            self.send_header("Content-Disposition", f'attachment; filename="{output.name}"')
            self.end_headers()
            self.wfile.write(audio)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            self.send_json(502, {"error": f"Kokoro server returned HTTP {exc.code}: {detail}"})
        except URLError:
            self.send_json(503, {
                "error": "Cannot reach the local Kokoro server. Start KokoroTTS at http://127.0.0.1:7860, then try again."
            })
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    host, port = "127.0.0.1", 8787
    print("HABARI AI Studio prototype")
    print(f"Open http://{host}:{port} in your browser")
    print(f"Local Kokoro server expected at {KOKORO_URL}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
