# Slice E — still vs live SRT (known issues)
## Camera exclusive lock (exit 255)
**Symptom:** Snapshot / `rpicam-still` → exit **255** while `whip.service` (`rpicam-vid`) is running.
**Cause:** Libcamera allows **one** Unicam client. Live SRT holds the lock.
**Fix:** `camera_still.py` with `CAPTURE_RELEASE_WHIP=1` briefly `systemctl stop whip.service`, captures (`--immediate` 720p), then `start`. Needs passwordless sudo — `sudoers/capture-whip.sudoers`.
Live `/cam` glitches ~1–3 s per Snapshot.
## HID “Capture timed out” with whip already stopped
**Symptom:** Manual `rpicam-still` works after `systemctl stop whip`, but UI Snapshot times out.
**Causes:**
1. **Old agent** on Pi: `_capture_jpeg` with only `rpicam-still -n -o` (no `--immediate`) — default AE wait ~5 s.
2. HID photo timeout was **5 s** (now **20 s** in `captureHub.js` — redeploy HID).
3. **systemd without `XDG_RUNTIME_DIR`:** headless `rpicam-still` can hang under the service user.
**Fix:** Pull latest `camera_still.py` + agent; set in unit:
```ini
Environment=XDG_RUNTIME_DIR=/run/user/1000
(use id -u if not 1000). Remove NoNewPrivileges=yes so sudo -n systemctl works.

Verify
journalctl -u capture-ws.service -f
# Snapshot → photo_req / still: ok / photo_ok
