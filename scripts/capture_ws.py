#!/usr/bin/env python3
"""
Slice E — outbound WebSocket capture agent.

Connects to HID /ws/capture with CAPTURE_TOKEN (Pi initiates; no static IP).
On photo_req: rpicam-still → photo_meta + binary JPEG.

Env:
  RELAY_WS_URL   wss://webrelay.example/ws/capture  (token query added if missing)
  CAPTURE_TOKEN  same secret as HID CAPTURE_TOKEN (≥16 chars)
  STILL_MIN_INTERVAL_S  default 2
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from shutil import which
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:
    print("Install websockets: pip install websockets", file=sys.stderr)
    raise SystemExit(1)

MAX_JPEG_BYTES = 8 * 1024 * 1024
MIN_INTERVAL_S = float(os.environ.get("STILL_MIN_INTERVAL_S", "2"))
_last_capture = 0.0


def _load_dotenv() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = val


def _ws_url() -> str:
    raw = (os.environ.get("RELAY_WS_URL") or "").strip()
    token = (os.environ.get("CAPTURE_TOKEN") or "").strip()
    if not raw:
        raise SystemExit("RELAY_WS_URL is required")
    if not token or len(token.encode("utf-8")) < 16:
        raise SystemExit("CAPTURE_TOKEN must be set (≥16 characters)")

    parsed = urlparse(raw)
    if parsed.scheme not in ("ws", "wss"):
        raise SystemExit("RELAY_WS_URL must be ws:// or wss://")

    qs = parse_qs(parsed.query, keep_blank_values=True)
    if "token" not in qs or not qs["token"] or not qs["token"][0]:
        qs["token"] = [token]
    # Flat query (single values)
    flat = {k: v[0] if isinstance(v, list) else v for k, v in qs.items()}
    path = parsed.path or "/ws/capture"
    return urlunparse(
        (parsed.scheme, parsed.netloc, path, "", urlencode(flat), "")
    )


def _capture_jpeg() -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        path = tmp.name
    try:
        cmd = None
        for binary in ("rpicam-still", "libcamera-still"):
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
        if len(data) > MAX_JPEG_BYTES:
            raise RuntimeError("JPEG too large")
        if data[0] != 0xFF or data[1] != 0xD8:
            raise RuntimeError("not a JPEG")
        return data
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


async def _handle_photo(ws, req_id: str) -> None:
    global _last_capture
    now = time.monotonic()
    if now - _last_capture < MIN_INTERVAL_S:
        await ws.send(json.dumps({"type": "photo_err", "id": req_id, "error": "rate limited"}))
        return
    try:
        jpeg = await asyncio.to_thread(_capture_jpeg)
    except Exception as exc:  # noqa: BLE001
        err = str(exc)[:200]
        await ws.send(json.dumps({"type": "photo_err", "id": req_id, "error": err}))
        return
    _last_capture = time.monotonic()
    await ws.send(json.dumps({"type": "photo_meta", "id": req_id, "bytes": len(jpeg)}))
    await ws.send(jpeg)


async def _session(url: str) -> None:
    # Do not log token (url may contain it) — log host/path only
    parsed = urlparse(url)
    safe = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    print(f"connecting {safe}", flush=True)
    async with websockets.connect(
        url,
        max_size=MAX_JPEG_BYTES + 1024,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=5,
    ) as ws:
        print("capture ws connected", flush=True)
        async for message in ws:
            if isinstance(message, bytes):
                continue
            try:
                msg = json.loads(message)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "pong":
                continue
            if msg.get("type") == "photo_req" and isinstance(msg.get("id"), str):
                await _handle_photo(ws, msg["id"])
                continue


async def main() -> None:
    _load_dotenv()
    url = _ws_url()
    delay = 1.0
    while True:
        try:
            await _session(url)
            delay = 1.0
        except ConnectionClosed as exc:
            print(f"disconnected code={exc.code}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"session error: {type(exc).__name__}", flush=True)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60.0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
