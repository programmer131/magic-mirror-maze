"""Simple three-turn games with shared rewards and no losing."""

from dataclasses import dataclass

from .bear_game import BEAR_LEVELS


TEAM_GAMES = {
    'garden': {'title': 'Magic Garden', 'urdu': 'جادوئی باغ', 'prompt': 'GROW A FLOWER', 'scene': 'bear_meadow'},
    'dragon': {'title': 'Feed the Dragon', 'urdu': 'ڈریگن کو پھل کھلائیں', 'prompt': 'SHARE A FRUIT', 'scene': 'scene_dragon'},
    'rainbow': {'title': 'Build a Rainbow', 'urdu': 'قوس قزح بنائیں', 'prompt': 'ADD A COLOR', 'scene': 'scene_rainbow'},
    'castle': {'title': 'Wake the Castle', 'urdu': 'محل کو جگائیں', 'prompt': 'LIGHT A LANTERN', 'scene': 'scene_castle'},
    'music': {'title': 'Make Music Together', 'urdu': 'مل کر موسیقی بنائیں', 'prompt': 'PLAY A NOTE', 'scene': 'scene_music'},
}


@dataclass
class TeamGame:
    kind: str
    level: int = 1
    completed: int = 0
    animation: float = 0.0
    finished: bool = False

    @property
    def order(self) -> tuple[int, int, int]:
        return BEAR_LEVELS[self.level - 1].order

    @property
    def current_player(self) -> int | None:
        return self.order[self.completed] if self.completed < 3 else None

    def act(self, player: int) -> bool:
        if self.finished or self.animation > 0 or player != self.current_player:
            return False
        self.completed += 1
        self.animation = 1.0
        return True

    def tick(self, elapsed: float) -> None:
        if self.animation <= 0:
            return
        self.animation = max(0.0, self.animation - max(0.0, elapsed))
        if self.animation == 0 and self.completed == 3:
            self.finished = True
