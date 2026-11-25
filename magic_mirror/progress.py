"""Local level progress. The file stays on this computer."""

from __future__ import annotations

import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "progress.json"
BEAR_PATH = Path(__file__).resolve().parents[1] / "bear_progress.json"
ACTIVITY_PATH = Path(__file__).resolve().parents[1] / "activity_progress.json"


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


def load_bear_progress() -> list[int]:
    try:
        data = json.loads(BEAR_PATH.read_text(encoding="utf-8"))
        cleared = data.get("cleared", [])
        return sorted({number for number in cleared if isinstance(number, int) and 1 <= number <= 12})
    except (OSError, ValueError, AttributeError, TypeError):
        return []


def save_bear_progress(cleared: list[int]) -> None:
    payload = {"cleared": sorted(set(cleared))}
    BEAR_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_activity_progress() -> dict[str, list[int]]:
    try:
        data = json.loads(ACTIVITY_PATH.read_text(encoding="utf-8"))
        return {str(key): sorted({n for n in value if isinstance(n, int) and 1 <= n <= 12})
                for key, value in data.items() if isinstance(value, list)}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def save_activity_progress(progress: dict[str, list[int]]) -> None:
    ACTIVITY_PATH.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
