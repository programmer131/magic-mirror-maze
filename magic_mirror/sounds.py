"""Small, overlapping sound effects for the game."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from .settings import load_settings


class SoundBank:
    def __init__(self, parent) -> None:
        folder = Path(__file__).resolve().parents[1] / "assets" / "sounds"
        files = {
            "start": ("open_003.wav", 0.35),
            "menu": ("select_001.wav", 0.28),
            "hint": ("question_002.wav", 0.32),
            "mirror1": ("glass_001.wav", 0.36),
            "mirror2": ("glass_003.wav", 0.36),
            "mirror3": ("glass_005.wav", 0.36),
            "blocked": ("error_004.wav", 0.25),
            "success": ("confirmation_003.wav", 0.35),
            "victory": ("victory.wav", 0.40),
            "word_blue": ("word_blue.wav", 0.55),
            "word_green": ("word_green.wav", 0.55),
            "word_orange": ("word_orange.wav", 0.55),
            "word_bear": ("word_bear.wav", 0.55),
            "word_home": ("word_home.wav", 0.55),
            "word_star": ("word_star.wav", 0.50),
        }
        for path in folder.glob('*.wav'):
            if path.stem.startswith(('ask_', 'ar_', 'letter_', 'note_', 'example_', 'places_')) or path.stem in ('good', 'try', 'listening', 'song'):
                files[path.stem] = (path.name, 0.55)
        for index, player in enumerate(load_settings()["players"], 1):
            slug = "".join(char for char in player["name"].lower() if char.isascii() and char.isalpha())
            filename = f"name_{slug}.wav"
            if slug and (folder / filename).is_file():
                files[f"name_{index}"] = (filename, 0.55)
        self.enabled = True
        self.effects = {}
        for name, (filename, volume) in files.items():
            voices = []
            for _ in range(2):
                effect = QSoundEffect(parent)
                effect.setSource(QUrl.fromLocalFile(str(folder / filename)))
                effect.setVolume(volume)
                voices.append(effect)
            self.effects[name] = voices

    def play(self, name: str) -> None:
        if not self.enabled or name not in self.effects:
            return
        voices = self.effects[name]
        effect = next((voice for voice in voices if not voice.isPlaying()), voices[0])
        effect.play()

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop_all()
        return self.enabled

    def stop_all(self) -> None:
        for voices in self.effects.values():
            for effect in voices:
                effect.stop()
