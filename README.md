# Capture node (Raspberry Pi 4 + Camera Module 3)

Pi-side publisher for the operator console: **H.264 → MediaMTX WHIP** (`cam` path) and a **local token still API**.  
No HID. No `/ws/device`. Video never shares sockets with the ESP32 path.

| Slice | Goal | Status |
|-------|------|--------|
| **A** | Detect IMX708 + still JPEG | Run on Pi (scripts below) |
| **B** | Local 720p30 H.264 encode | Run on Pi |
| **C** | Publish live video to MediaMTX path `cam` | **SRT ingest** (see `docs/SLICE_C_SRT.md`) — stock ffmpeg cannot WHIP |
| **D** | `still_server.py` token HTTP | Stub / running on Pi |
| **E/F** | Node `/api/photo` + Focus WHEP | HID repo |

**Why not WHIP from Pi yet?** Distro `ffmpeg` failed as a WHIP client (`-f webrtc`); Stream-test on `/desk` already proved VPS 443+8189. We use **SRT → MediaMTX → WHEP** until a real WHIP client is on the Pi. Details: [`docs/SLICE_C_SRT.md`](docs/SLICE_C_SRT.md).

Defaults: **1280×720 @ 30**. Not 1080 until 720 is stable.

---

## 1. Hardware & OS baseline

1. **Power off** the Pi 4.
2. CAMERA port (between audio and HDMI): lift collar, insert Module 3 ribbon (**silver contacts facing HDMI**), press collar down.
3. Power on, SSH in.
4. Update + camera apps:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y libcamera-apps
# On newer images the binary may be rpicam-*; package still provides the tools.
```

Clone or copy this repo to the Pi, e.g. `~/capture`.

---

## 2. Slice A — Detect & still

```bash
cd ~/capture
./scripts/slice_a_detect.sh
```

Or manually:

```bash
rpicam-hello --list-cameras
# Expect one camera, imx708 (Module 3)

rpicam-still -n -o /tmp/test.jpg
```

**Headless view:**

```bash
cd /tmp && python3 -m http.server 8080
# Browser: http://<PI_IP>:8080/test.jpg  — then Ctrl+C
```

**Pass:** Sensor listed as `imx708`; JPEG looks correct.  
**Fail → stop.** Do not start WHIP or still server.

---

## 3. Slice B — Local H.264 (720p30)

```bash
cd ~/capture
./scripts/slice_b_encode.sh
```

Or:

```bash
rpicam-vid -t 10000 --width 1280 --height 720 --framerate 30 -o /tmp/test.h264
```

Watch for **10 s** with no libcamera buffer errors. Serve/download `/tmp/test.h264` and play in VLC if useful.

**Pass:** Clean 10 s encode. Then proceed to **Slice C**.

---

## 4. Layout

```text
capture/
  README.md
  env.example
  still_server.py          # Slice D (bind localhost + token)
  scripts/
    slice_a_detect.sh
    slice_b_encode.sh
    publish_whip.sh        # Slice C placeholder
  systemd/
    still.service.example
    whip.service.example
```

Copy `env.example` → `/etc/hid-capture.env` or `~/capture/.env` (gitignored) before C/D.

---

## Security

- Still API: **127.0.0.1** (or LAN) + `CAPTURE_TOKEN`. Not the UI gate password.
- Do not expose still port on `0.0.0.0/0` without a tunnel/VPN.
- WHIP URL points at public MediaMTX; tighten MediaMTX auth before production.
