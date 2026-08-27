#!/usr/bin/env python3
"""
Slice D — local still capture HTTP (token required).

Bind to STILL_HOST (default 127.0.0.1). Relay calls this with CAPTURE_TOKEN.
Not for public exposure without VPN/tunnel.

Env:
  STILL_HOST, STILL_PORT, CAPTURE_TOKEN
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("STILL_HOST", "127.0.0.1")
PORT = int(os.environ.get("STILL_PORT", "8091"))
TOKEN = os.environ.get("CAPTURE_TOKEN", "").strip()
MIN_INTERVAL_S = float(os.environ.get("STILL_MIN_INTERVAL_S", "2"))

_last_capture = 0.0


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    if not TOKEN:
        return False
    auth = handler.headers.get("Authorization", "")
    if auth == f"Bearer {TOKEN}":
        return True
    return handler.headers.get("X-Capture-Token", "") == TOKEN


def _capture_jpeg() -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        path = tmp.name
    try:
        cmd = None
        for binary in ("rpicam-still", "libcamera-still"):
            from shutil import which

            if which(binary):
                cmd = [binary, "-n", "-o", path]
                break
        if not cmd:
            raise RuntimeError("rpicam-still / libcamera-still not found")
        subprocess.run(cmd, check=True, capture_output=True, timeout=15)
        with open(path, "rb") as f:
            data = f.read()
        if not data:
            raise RuntimeError("empty JPEG")
        return data
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


class StillHandler(BaseHTTPRequestHandler):
    server_version = "hid-capture-still/0.1"

    def log_message(self, fmt: str, *args) -> None:
        # Avoid logging tokens; path only.
        sys_stderr = __import__("sys").stderr
        print("%s - %s" % (self.address_string(), fmt % args), file=sys_stderr)

    def do_GET(self) -> None:
        if self.path in ("/healthz", "/health"):
            body = b'{"ok":true}\n'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        global _last_capture
        if self.path not in ("/still", "/still/"):
            self.send_error(404)
            return
        if not TOKEN:
            self.send_error(503, "CAPTURE_TOKEN not configured")
            return
        if not _authorized(self):
            self.send_error(401, "unauthorized")
            return
        now = time.monotonic()
        if now - _last_capture < MIN_INTERVAL_S:
            self.send_error(429, "rate limited")
            return
        try:
            jpeg = _capture_jpeg()
        except Exception as exc:  # noqa: BLE001 — return error to caller
            self.send_error(500, str(exc)[:200])
            return
        _last_capture = now
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(jpeg)


def main() -> None:
    if HOST not in ("127.0.0.1", "localhost", "::1") and not TOKEN:
        raise SystemExit("Refusing non-localhost bind without CAPTURE_TOKEN")
    if not TOKEN:
        print("WARNING: CAPTURE_TOKEN empty — all /still requests will 503", flush=True)
    httpd = ThreadingHTTPServer((HOST, PORT), StillHandler)
    print(f"still listening on http://{HOST}:{PORT}  POST /still", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
