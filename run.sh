#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
mkdir -p models
MODEL="models/pose_landmarker.task"
if [[ ! -f "$MODEL" ]]; then
  curl -fL --retry 3 -o "$MODEL" \
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker.task" \
    || echo "Pose model download failed. Keyboard play still works."
fi
exec .venv/bin/python -m magic_mirror "$@"
