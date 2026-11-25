"""Local family settings, kept separate from the game source."""

import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config.json"


def load_settings(path: Path = CONFIG) -> dict:
    defaults = [{"name": f"Player {number}", "urdu": ""} for number in (1, 2, 3)]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"players": defaults}
    except (OSError, ValueError):
        return {"players": defaults}
    players = data.get("players")
    if not isinstance(players, list) or len(players) != 3:
        data["players"] = defaults
    else:
        data["players"] = [
            {"name": str(player.get("name") or defaults[i]["name"])[:24], "urdu": str(player.get("urdu") or "")[:24]}
            if isinstance(player, dict) else defaults[i]
            for i, player in enumerate(players)
        ]
    return data
