"""Local level progress. The file stays on this computer."""

from __future__ import annotations

import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "progress.json"


def load_progress() -> list[int]:
    if not PATH.is_file():
        return []
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    cleared = data.get("cleared", [])
    return sorted({int(number) for number in cleared if isinstance(number, int)})


def save_progress(cleared: list[int]) -> None:
    payload = {"cleared": sorted(set(cleared))}
    PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
