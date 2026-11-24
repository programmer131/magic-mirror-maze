"""Courtyard beam puzzles. Two mirror faces, three players, one chest."""

from __future__ import annotations

from dataclasses import dataclass, field

# Screen coordinates, y grows downward.
EAST = (1, 0)
WEST = (-1, 0)
NORTH = (0, -1)
SOUTH = (0, 1)

CATCH = 64
CHEST_CATCH = 78
STEP = 8
MAX_STEPS = 520
MIN_X, MIN_Y = 80, 188
MAX_X, MAX_Y = 1200, 548

PLAYERS = {
    1: ("Blue", "#3D7DFF", "star"),
    2: ("Green", "#3CB371", "leaf"),
    3: ("Orange", "#F08A24", "sun"),
}


@dataclass
class Mirror:
    player: int
    name: str
    color: str
    badge: str
    x: float
    y: float
    # 0 is the slash face (/). 1 is the backslash face (\).
    angle: int = 1

    def turn(self, clockwise: bool) -> None:
        # Beginner mirrors have two faces, so either arm switches to the other one.
        del clockwise
        self.angle = 1 - self.angle


@dataclass
class Blocker:
    x: float
    y: float
    w: float
    h: float


@dataclass
class Level:
    number: int
    name: str
    lantern: tuple[float, float]
    direction: tuple[int, int]
    chest: tuple[float, float]
    mirrors: list[Mirror]
    solution: tuple[int, int, int]
    hints: tuple[str, str, str]
    blockers: list[Blocker] = field(default_factory=list)


@dataclass
class Beam:
    points: list[tuple[float, float]] = field(default_factory=list)
    hit: list[int] = field(default_factory=list)
    solved: bool = False
    looping: bool = False
    blocked: bool = False
    reached_chest: bool = False


def reflect(direction: tuple[int, int], angle: int) -> tuple[int, int]:
    dx, dy = direction
    if angle == 0:
        return (-dy, -dx)
    return (dy, dx)


def _mirror(player: int, x: float, y: float, angle: int) -> Mirror:
    name, color, badge = PLAYERS[player]
    return Mirror(player, name, color, badge, x, y, angle)


def campaign() -> list[Level]:
    """Six forest-courtyard puzzles. Each call returns fresh mirror objects.

    Pieces stay left of x=960 so the camera card in the lower right stays clear.
    """
    return [
        Level(
            1,
            "The First Spark",
            (230, 455),
            EAST,
            (860, 455),
            [_mirror(1, 450, 455, 1), _mirror(2, 450, 300, 1), _mirror(3, 860, 300, 1)],
            (0, 0, 1),
            (
                "Look at where the light stops.",
                "Blue needs to send the light up to Green.",
                "Turn Blue and Green to the / face. Leave Orange on the \\ face.",
            ),
        ),
        Level(
            2,
            "The Low Road",
            (230, 300),
            EAST,
            (860, 300),
            [_mirror(1, 450, 300, 0), _mirror(2, 450, 455, 0), _mirror(3, 860, 455, 1)],
            (1, 1, 0),
            (
                "The lantern is up high this time.",
                "Blue needs to send the light down to Green.",
                "Turn Blue and Green to the \\ face. Turn Orange to the / face.",
            ),
        ),
        Level(
            3,
            "The Side Gate",
            (210, 300),
            SOUTH,
            (860, 300),
            [_mirror(1, 210, 455, 0), _mirror(2, 530, 455, 1), _mirror(3, 530, 300, 1)],
            (1, 0, 0),
            (
                "The light is going down.",
                "Blue needs to send it across to Green.",
                "Blue uses \\. Green and Orange use / so the light climbs, then goes right.",
            ),
        ),
        Level(
            4,
            "The Way Home",
            (900, 300),
            WEST,
            (230, 300),
            [_mirror(1, 680, 300, 1), _mirror(2, 680, 455, 1), _mirror(3, 250, 455, 0)],
            (0, 0, 1),
            (
                "The lantern is on the right.",
                "Blue needs to send the light down.",
                "Blue and Green use /. Orange uses \\ to send the light up into the chest.",
            ),
        ),
        Level(
            5,
            "Mind the Stones",
            (230, 455),
            EAST,
            (860, 455),
            [_mirror(1, 450, 455, 1), _mirror(2, 450, 300, 1), _mirror(3, 860, 300, 0)],
            (0, 0, 1),
            (
                "Stones stop the light. Mirrors do not.",
                "Send the light up and across, the same way as the first spark.",
                "Orange must use \\. The / face sends the light into the stones.",
            ),
            [Blocker(800, 192, 130, 58)],
        ),
        Level(
            6,
            "The Long Bend",
            (860, 455),
            WEST,
            (230, 455),
            [_mirror(1, 620, 455, 0), _mirror(2, 620, 300, 0), _mirror(3, 250, 300, 1)],
            (1, 1, 0),
            (
                "Start from the lower lantern and climb.",
                "Blue sends the light up. Green sends it left.",
                "Blue and Green use \\. Orange uses / to drop the light into the chest.",
            ),
        ),
    ]


def _inside(blockers: list[Blocker], x: float, y: float) -> bool:
    for stone in blockers:
        if stone.x <= x <= stone.x + stone.w and stone.y <= y <= stone.y + stone.h:
            return True
    return False


def trace(level: Level) -> Beam:
    beam = Beam(points=[level.lantern])
    x, y = float(level.lantern[0]), float(level.lantern[1])
    direction = level.direction
    seen: set[int] = set()
    leaving: Mirror | None = None
    for _ in range(MAX_STEPS):
        x += direction[0] * STEP
        y += direction[1] * STEP
        if x < MIN_X or y < MIN_Y or x > MAX_X or y > MAX_Y:
            beam.points.append((x, y))
            break
        if leaving is not None:
            still_inside = (x - leaving.x) ** 2 + (y - leaving.y) ** 2 <= CATCH ** 2
            if still_inside:
                beam.points.append((x, y))
                continue
            leaving = None
        if _inside(level.blockers, x, y):
            beam.blocked = True
            break
        caught = None
        for mirror in level.mirrors:
            if (x - mirror.x) ** 2 + (y - mirror.y) ** 2 <= CATCH ** 2:
                if mirror.player in seen:
                    beam.looping = True
                    beam.points.append((mirror.x, mirror.y))
                    return beam
                caught = mirror
                break
        if caught is not None:
            seen.add(caught.player)
            beam.hit.append(caught.player)
            x, y = caught.x, caught.y
            beam.points.append((x, y))
            direction = reflect(direction, caught.angle)
            leaving = caught
            continue
        beam.points.append((x, y))
        if (x - level.chest[0]) ** 2 + (y - level.chest[1]) ** 2 <= CHEST_CATCH ** 2:
            beam.points.append(level.chest)
            beam.reached_chest = True
            beam.solved = len(seen) == 3
            break
    return beam
