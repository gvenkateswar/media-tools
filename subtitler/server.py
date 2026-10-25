"""Local speech server for the live subtitle page.

Serves ``index.html`` and one API endpoint:

    POST /api/transcribe?original=1&restrict=1
    body: a 16-bit mono WAV clip (the page sends ~2-8 s phrases at 16 kHz)
    ->    {"language": "cy", "english": "...", "original": "..."}

For each clip we first detect the spoken language. English is transcribed as
is. Anything else (Welsh, for this show) is run through Whisper's built-in
"translate" task to get English, and optionally transcribed a second time so
the page can show the Welsh words too.

``restrict=1`` narrows detection to English vs Welsh. Whisper sometimes
mistakes short Welsh phrases for Irish, Breton or Dutch; when we know the show
only uses two languages, picking the likelier of those two is more reliable.

Only the standard library plus faster-whisper and numpy are needed.
"""
from __future__ import annotations

import argparse
import io
import json
import threading
import time
import wave
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

HERE = Path(__file__).resolve().parent
INDEX_HTML = HERE / "index.html"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # ~5 minutes of 16 kHz audio; plenty

# Whisper "hears" these on music, applause or silence. Drop them.
HALLUCINATIONS = {
    "thank you.", "thanks for watching!", "thank you for watching.",
    "thank you for watching!", "please subscribe.", "you", "bye.",
    "diolch.", "diolch am wylio.", "subtitles by the amara.org community",
}


class Engine:
    """Holds the Whisper model and serializes calls to it."""

    def __init__(self, model_name: str, device: str | None, compute_type: str | None):
        from faster_whisper import WhisperModel

        device, compute_type = _auto_device(device, compute_type)
        print(f"Loading Whisper '{model_name}' on {device} ({compute_type}) ...")
        t0 = time.time()
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        print(f"Model ready in {time.time() - t0:.1f}s")
        self.info = {"model": model_name, "device": device, "compute_type": compute_type}
        self._lock = threading.Lock()

    def process(self, audio: np.ndarray, want_original: bool, restrict: bool) -> dict:
        with self._lock:
            t0 = time.time()
            lang, prob, all_probs = self.model.detect_language(audio)
            if restrict:
                probs = dict(all_probs)
                lang = "cy" if probs.get("cy", 0.0) > probs.get("en", 0.0) else "en"
                prob = probs.get(lang, 0.0)

            if lang == "en":
                english = self._run(audio, "en", "transcribe")
                original = ""
            else:
                english = self._run(audio, lang, "translate")
                original = self._run(audio, lang, "transcribe") if want_original else ""

            return {
                "language": lang,
                "confidence": round(float(prob), 3),
                "english": english,
                "original": original,
                "seconds": round(time.time() - t0, 2),
            }

    def _run(self, audio: np.ndarray, lang: str, task: str) -> str:
        segments, _ = self.model.transcribe(
            audio,
            language=lang,
            task=task,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return "" if text.lower() in HALLUCINATIONS else text


def _auto_device(device: str | None, compute_type: str | None) -> tuple[str, str]:
    """CUDA + float16 when a GPU is present, otherwise CPU + int8."""
    if device is None:
        try:
            import ctranslate2

            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
    if compute_type is None:
        compute_type = "float16" if device == "cuda" else "int8"
    return device, compute_type


def read_wav(data: bytes) -> np.ndarray:
    """Decode a 16-bit PCM WAV into float32 mono at 16 kHz."""
    with wave.open(io.BytesIO(data), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("expected 16-bit PCM WAV")
        rate, channels = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    audio = pcm.astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != 16_000:  # the page already sends 16 kHz; this is a safety net
        n = int(len(audio) * 16_000 / rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)
        audio = audio.astype(np.float32)
    return audio


def make_handler(engine: Engine):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, INDEX_HTML.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/health":
                self._json(HTTPStatus.OK, {"ok": True, **engine.info})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/api/transcribe":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_UPLOAD_BYTES:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "bad upload size"})
                return
            query = parse_qs(url.query)
            try:
                audio = read_wav(self.rfile.read(length))
                result = engine.process(
                    audio,
                    want_original=query.get("original", ["1"])[0] == "1",
                    restrict=query.get("restrict", ["1"])[0] == "1",
                )
            except Exception as exc:  # report to the page instead of crashing
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                return
            self._json(HTTPStatus.OK, result)

        def _json(self, status, payload):
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _send(self, status, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # keep the console quiet
            pass

    return Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="subtitler",
        description="Live English + Welsh subtitles from a show's audio.",
    )
    p.add_argument("--model", default="small",
                   help="Whisper size: tiny/base/small/medium/large-v3 "
                        "(default: small). Bigger = better Welsh, slower.")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--device", default=None, help="cpu or cuda (default: auto).")
    p.add_argument("--compute-type", default=None,
                   help="e.g. int8, float16 (default: auto).")
    p.add_argument("--no-browser", action="store_true",
                   help="Don't open the page automatically.")
    args = p.parse_args(argv)

    engine = Engine(args.model, args.device, args.compute_type)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(engine))
    url = f"http://{'localhost' if args.host == '127.0.0.1' else args.host}:{args.port}/"
    print(f"Subtitles app running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0
