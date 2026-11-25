"""The three children take turns opening a path for the little bear."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BearLevel:
    name: str
    order: tuple[int, int, int]
    accent: str


BEAR_LEVELS = (
    BearLevel("Sunny Trail", (1, 2, 3), "#FFCD55"),
    BearLevel("Daisy Meadow", (2, 1, 3), "#FF9EB5"),
    BearLevel("Butterfly Path", (3, 2, 1), "#B9A5FF"),
    BearLevel("Little Bridge", (1, 3, 2), "#76D7EA"),
    BearLevel("Rainbow Woods", (2, 3, 1), "#FFAF6D"),
    BearLevel("Bluebell Lane", (3, 1, 2), "#A5B8FF"),
    BearLevel("Honey Grove", (1, 2, 3), "#FFD35D"),
    BearLevel("Ladybird Garden", (2, 1, 3), "#F78584"),
    BearLevel("Twinkle Trail", (3, 2, 1), "#D5A2ED"),
    BearLevel("Apple Orchard", (1, 3, 2), "#FF9F91"),
    BearLevel("Firefly Forest", (2, 3, 1), "#B1E788"),
    BearLevel("Welcome Home", (3, 1, 2), "#FFE181"),
)


@dataclass
class BearJourney:
    level: int = 1
    gates_open: int = 0
    position: float = 0.0
    moving: bool = False
    home: bool = False

    @property
    def current_player(self) -> int | None:
        return BEAR_LEVELS[self.level - 1].order[self.gates_open] if self.gates_open < 3 else None

    def open_next_gate(self, player: int) -> bool:
        if self.moving or self.home or player != self.current_player:
            return False
        self.gates_open += 1
        self.moving = True
        return True

    def tick(self, elapsed: float) -> None:
        if not self.moving:
            return
        self.position = min(float(self.gates_open), self.position + max(0.0, elapsed) * 0.85)
        if self.position >= self.gates_open:
            self.moving = False
            if self.gates_open == 3:
                self.home = True
