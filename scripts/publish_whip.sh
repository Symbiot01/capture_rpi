#!/usr/bin/env bash
# Slice C — WHIP publish to MediaMTX (placeholder until tool chain chosen).
# Do not run until Slice A and B pass on this Pi.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "${ROOT}/.env"
  set +a
fi

WHIP_URL="${WHIP_URL:-https://mediarelay.sahilpatel.online/cam/whip}"
WIDTH="${WIDTH:-1280}"
HEIGHT="${HEIGHT:-720}"
FPS="${FPS:-30}"

echo "Slice C not wired yet."
echo "  WHIP_URL=${WHIP_URL}"
echo "  Encode: ${WIDTH}x${HEIGHT}@${FPS}"
echo
echo "After A/B pass, implement publish (ffmpeg/GStreamer/whip client) here."
echo "Path must be /cam/whip (not /desk)."
exit 1
