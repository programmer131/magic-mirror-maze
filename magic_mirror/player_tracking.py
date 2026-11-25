"""Keep mirror ownership stable when pose detections briefly disappear."""

from __future__ import annotations

import time


def calibrate_three(positions: list[float]) -> list[int] | None:
    """Assign left, middle and right only when three distinct players are visible."""
    if len(positions) != 3 or any(not 0 <= x <= 1 for x in positions):
        return None
    indices = sorted(range(3), key=positions.__getitem__)
    ordered = [positions[index] for index in indices]
    if any(b - a < 0.08 for a, b in zip(ordered, ordered[1:])):
        return None
    result = [0, 0, 0]
    for player, index in enumerate(indices, 1):
        result[index] = player
    return result


class PlayerTracker:
    def __init__(self, max_distance: float = 0.18, ambiguity: float = 0.04) -> None:
        self.positions: dict[int, float] = {}
        self.visible: set[int] = set()
        self.max_distance = max_distance
        self.ambiguity = ambiguity
        self.unassigned_since: float | None = None
        self.healthy_since: float | None = None
        self.reassigned = False

    def assign(self, positions: list[float]) -> list[int | None]:
        self.reassigned = False
        result: list[int | None] = [None] * len(positions)
        if not self.positions:
            for player, index in enumerate(sorted(range(len(positions)), key=positions.__getitem__)[:3], 1):
                result[index] = player
                self.positions[player] = positions[index]
            self.visible = {player for player in result if player is not None}
            return result

        candidates = []
        ambiguous = set()
        for index, x in enumerate(positions):
            visible_distances = sorted(
                (abs(x - old), player)
                for player, old in self.positions.items()
                if player in self.visible and abs(x - old) <= self.max_distance
            )
            distances = visible_distances or sorted((abs(x - old), player) for player, old in self.positions.items())
            if len(distances) > 1 and distances[1][0] - distances[0][0] < self.ambiguity:
                ambiguous.add(index)
                continue
            if distances and distances[0][0] <= self.max_distance:
                candidates.append((distances[0][0], index, distances[0][1]))
        used = set()
        for _, index, player in sorted(candidates):
            if player not in used:
                result[index] = player
                used.add(player)
                self.positions[player] = positions[index]

        free = [player for player in (1, 2, 3) if player not in self.positions]
        for index in sorted(range(len(positions)), key=positions.__getitem__):
            if result[index] is not None or index in ambiguous or not free:
                continue
            if any(abs(positions[index] - old) <= self.max_distance for old in self.positions.values()):
                continue
            player = free.pop(0)
            result[index] = player
            self.positions[player] = positions[index]
        self.visible = {player for player in result if player is not None}
        ordered = sorted(positions)
        separated = all(b - a >= 0.08 for a, b in zip(ordered, ordered[1:]))
        if positions and any(player is None for player in result) and separated:
            now = time.monotonic()
            self.healthy_since = None
            if self.unassigned_since is None:
                self.unassigned_since = now
            elif now - self.unassigned_since >= 1.5:
                for player in list(self.positions):
                    if player not in self.visible:
                        del self.positions[player]
                free = [player for player in (1, 2, 3) if player not in self.positions]
                for index in sorted(range(len(positions)), key=positions.__getitem__):
                    if result[index] is None and free:
                        player = free.pop(0)
                        result[index] = player
                        self.positions[player] = positions[index]
                self.visible = {player for player in result if player is not None}
                self.unassigned_since = None
                self.reassigned = True
        elif positions and not separated:
            self.unassigned_since = None
            self.healthy_since = None
        elif self.unassigned_since is not None:
            now = time.monotonic()
            if self.healthy_since is None:
                self.healthy_since = now
            elif now - self.healthy_since >= 1.0:
                self.unassigned_since = None
                self.healthy_since = None
        return result
