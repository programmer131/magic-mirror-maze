"""Magic Mirror Maze on one desktop screen."""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .activities import HUB_KINDS, VOICE_GAMES, activity_info
from .arabic_tutor import ArabicTutorState, ArabicTutorWorker
from .bear_game import BEAR_LEVELS, BearJourney
from .board import PLAYERS, Beam, Blocker, Level, Mirror, campaign, trace
from .learning import PLACES, WORD_HINTS, VoiceRound
from .next_gesture import NextGesture
from .pose_track import PoseWorker
from .progress import load_activity_progress, load_bear_progress, load_progress, save_activity_progress, save_bear_progress, save_progress
from .settings import load_settings
from .sounds import SoundBank
from .speech import SpeechWorker
from .team_games import TEAM_GAMES, TeamGame

KEYS = {
    Qt.Key.Key_A: (1, False),
    Qt.Key.Key_D: (1, True),
    Qt.Key.Key_F: (2, False),
    Qt.Key.Key_H: (2, True),
    Qt.Key.Key_J: (3, False),
    Qt.Key.Key_L: (3, True),
}
KEY_LABELS = {1: ("A", "D"), 2: ("F", "H"), 3: ("J", "L")}
GOLD = QColor("#FFE7A3")
INK = QColor("#142033")
VIEW_W, VIEW_H = 1280, 720
URDU_COLORS = {1: "نیلا", 2: "سبز", 3: "نارنجی"}


def _art_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "assets"


def _load_art() -> dict[str, QPixmap]:
    found = {}
    folder = _art_dir()
    for name in (
        "courtyard",
        "lantern",
        "chest_closed",
        "chest_open",
        "mirror_blue",
        "mirror_green",
        "mirror_orange",
        "bear",
        "bear_forest",
        "bear_meadow",
        "bear_sunset",
        "scene_dragon", "scene_rainbow", "scene_castle", "scene_music", "scene_village", "scene_animals",
        "vocab_book", "vocab_pencil", "vocab_door", "vocab_house", "vocab_chair", "vocab_key",
        "animal_cat", "animal_rabbit", "animal_bird",
    ):
        for suffix in (".png", ".jpg"):
            path = folder / f"{name}{suffix}"
            if path.is_file():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    found[name] = pixmap
                break
    return found


class MazeWindow(QWidget):
    def __init__(self, camera: int | None = None, camera_enabled: bool = True) -> None:
        super().__init__()
        self.sounds = SoundBank(self)
        self.settings = load_settings()
        self.players = self.settings["players"]
        self.art = _load_art()
        self.vocab_art = OrderedDict()
        self.cleared = load_progress()
        self.bear_cleared = load_bear_progress()
        self.activity_cleared = load_activity_progress()
        self.mode = "home"
        self.level: Level | None = None
        self.bear: BearJourney | None = None
        self.team: TeamGame | None = None
        self.voice_round: VoiceRound | None = None
        self.speech_worker: SpeechWorker | None = None
        self.voice_status = 'unavailable'
        self.voice_request = 0
        self.voice_busy = False
        self.voice_feedback = ''
        self.voice_last_item = None
        self.voice_prompted = None
        self.arabic_worker = None
        self.arabic_status = 'connecting'
        self.arabic_state = None
        self.arabic_transcript = ''
        self.selection_kind = ''
        self.hub_focus = 0
        self.hub_scan_at = time.monotonic()
        self.home_focus = 1
        self.home_scan_at = time.monotonic()
        self.hub_gesture = NextGesture()
        self.activity_gesture = NextGesture()
        self.bear_calibrated = True
        self.bear_menu_gesture = NextGesture()
        self.bear_last_tick = time.monotonic()
        self.beam = Beam()
        self.paused = False
        self.pause_reason = ""
        self.hold = 0.0
        self.celebrating = False
        self.next_gesture = NextGesture()
        self.hint_step = 0
        self.face: dict[int, float] = {}
        self.flash: dict[int, tuple[float, bool]] = {}
        self.raised: dict[tuple[int, str], float] = {}
        self.armed: set[tuple[int, str]] = set()
        self.both_since: dict[int, float] = {}
        self.bodies = []
        self.preview = None
        self.camera_status = "missing"
        self.had_body = False
        self.missing_since: float | None = None
        self.ignore_tracking_loss = False
        self.wait_for_arms_down = False
        self.hotspots: list[tuple[QRectF, tuple | None]] = []
        self._view = (0.0, 0.0, 1.0)
        self.setWindowTitle("Magic Mirror Maze")
        self.resize(VIEW_W, VIEW_H)
        self.setMinimumSize(960, 540)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self.worker = None
        self.camera_index = camera
        if camera_enabled:
            self._ensure_camera()

    def _ensure_camera(self) -> None:
        if self.worker is not None or (self.camera_index is not None and self.camera_index < 0):
            return
        self.camera_status = "starting"
        model = _art_dir().parent / "models" / "pose_landmarker.task"
        self.worker = PoseWorker(self.camera_index, model)
        self.worker.bodies_ready.connect(self._on_bodies)
        self.worker.poses_ready.connect(self._on_poses)
        self.worker.preview_ready.connect(self._on_preview)
        self.worker.status_ready.connect(self._on_status)
        self.worker.tracking_reset.connect(self._tracking_reset)
        self.worker.players_calibrated.connect(self._bear_players_ready)
        self.worker.start()

    def _stop_camera(self) -> bool:
        if self.worker is None:
            return True
        self.worker.stop()
        if not self.worker.wait(5000):
            return False
        self.worker = None
        self.preview = None
        self.bodies = []
        self.camera_status = 'missing'
        return True

    def _tick(self) -> None:
        now = time.monotonic()
        elapsed = min(0.1, max(0.0, now - self.bear_last_tick))
        self.bear_last_tick = now
        if self.mode == 'home':
            if self.bear_menu_gesture.progress > 0:
                self.home_scan_at = now
            elif now - self.home_scan_at >= 3.0:
                self.home_focus = (self.home_focus + 1) % 3
                self.home_scan_at = now
        if self.mode == "hub":
            if self.hub_gesture.progress > 0:
                self.hub_scan_at = now
            elif now - self.hub_scan_at >= 3.0:
                self.hub_focus = (self.hub_focus + 1) % len(HUB_KINDS)
                self.hub_scan_at = now
        if self.mode == "team" and self.team is not None and not self.paused and not self.celebrating:
            was_active = self.team.animation > 0
            self.team.tick(elapsed)
            if was_active and self.team.animation == 0 and not self.team.finished and self.bear_calibrated:
                self._say_team_turn()
            if self.team.finished:
                self.celebrating = True
                self.next_gesture.reset()
                self.sounds.play('song' if self.team.kind == 'music' else 'victory')
                self._record_activity(self.team.kind, self.team.level)
        if self.mode == "bear" and self.bear is not None and not self.paused and not self.celebrating:
            was_moving = self.bear.moving
            self.bear.tick(elapsed)
            if was_moving and not self.bear.moving and not self.bear.home and self.bear_calibrated:
                self._say_bear_turn()
            if self.bear.home:
                self.celebrating = True
                self.next_gesture.reset()
                self.sounds.play("victory")
                QTimer.singleShot(800, lambda: self.sounds.play("word_home") if self.mode == "bear" and self.celebrating else None)
                if self.bear.level not in self.bear_cleared:
                    self.bear_cleared.append(self.bear.level)
                    save_bear_progress(self.bear_cleared)
        if self.level is not None:
            for mirror in self.level.mirrors:
                target = float(mirror.angle)
                current = self.face.get(mirror.player, target)
                step = max(-0.14, min(0.14, target - current))
                self.face[mirror.player] = current + step
        if self.mode == "play" and self.beam.solved and not self.paused:
            self.hold = min(1.0, self.hold + 0.016)
            if self.hold >= 1.0 and not self.celebrating:
                self.celebrating = True
                self.next_gesture.reset()
                self.sounds.play("victory")
                self._mark_cleared()
        elif not self.celebrating:
            self.hold = 0.0
        self._watch_tracking()
        self.update()

    def _mark_cleared(self) -> None:
        if self.level is None:
            return
        if self.level.number not in self.cleared:
            self.cleared.append(self.level.number)
            save_progress(self.cleared)

    def _unlocked(self, number: int) -> bool:
        return number <= 1 or (number - 1) in self.cleared or number in self.cleared

    def _continue_number(self) -> int:
        for number in range(1, 7):
            if number not in self.cleared and self._unlocked(number):
                return number
        return 1

    def _begin(self, number: int) -> None:
        if not self._unlocked(number):
            return
        self._stop_speech()
        self.sounds.play("start")
        self.level = campaign()[number - 1]
        self.bear = None
        self.team = None
        self.voice_round = None
        if self.worker is not None:
            self.worker.require_three_players = False
            self.worker.calibrate_for_three = False
        self.beam = trace(self.level)
        self.mode = "play"
        self.paused = False
        self.pause_reason = ""
        self.hold = 0.0
        self.celebrating = False
        self.next_gesture.reset()
        self.hint_step = 0
        self.face = {mirror.player: float(mirror.angle) for mirror in self.level.mirrors}
        self.flash.clear()
        self.raised.clear()
        self.armed.clear()
        self.both_since.clear()
        self.wait_for_arms_down = True
        self.missing_since = None
        self.had_body = False
        self.ignore_tracking_loss = False
        if self.worker is not None:
            self.worker.reset_tracking = True
        self.update()

    def _bear_unlocked(self, number: int) -> bool:
        return 1 <= number <= len(BEAR_LEVELS) and (number == 1 or number - 1 in self.bear_cleared or number in self.bear_cleared)

    def _bear_continue_number(self) -> int:
        return next((n for n in range(1, len(BEAR_LEVELS) + 1) if n not in self.bear_cleared and self._bear_unlocked(n)), 1)

    def _open_bear_menu(self) -> None:
        self._stop_speech()
        if self.worker is not None:
            self.worker.require_three_players = False
            self.worker.calibrate_for_three = False
            self.worker.reset_tracking = True
        self.mode = "bear_select"
        self.celebrating = False
        self.bear_menu_gesture.reset()
        self.update()

    def _begin_bear(self, number: int) -> None:
        if not self._bear_unlocked(number):
            return
        self._stop_speech()
        self.sounds.play("start")
        self.bear = BearJourney(level=number)
        self.team = None
        self.voice_round = None
        self.level = None
        self.mode = "bear"
        self.paused = False
        self.pause_reason = ""
        self.celebrating = False
        self.next_gesture.reset()
        self.bear_menu_gesture.reset()
        self.bear_last_tick = time.monotonic()
        self.raised.clear()
        self.armed.clear()
        self.both_since.clear()
        self.flash.clear()
        self.wait_for_arms_down = True
        self.missing_since = None
        self.had_body = False
        self.ignore_tracking_loss = False
        self.bear_calibrated = self.worker is None
        if self.worker is not None:
            self.worker.require_three_players = True
            self.worker.calibrate_for_three = True
            self.worker.reset_tracking = True
        else:
            self._say_bear_turn()
        self.update()

    def _bear_players_ready(self) -> None:
        if self.mode in ("bear", "team", "voice") and not self.celebrating and not self.bear_calibrated:
            self.bear_calibrated = True
            self.wait_for_arms_down = True
            if self.bear is not None and not self.bear.moving:
                self._say_bear_turn()
            elif self.team is not None and not self.team.animation:
                self._say_team_turn()
            elif self.voice_round is not None:
                self._announce_voice_prompt()
            self.update()

    def _say_bear_turn(self) -> None:
        if self.bear is not None and self.bear.current_player is not None:
            player = self.bear.current_player
            color = PLAYERS[player][0].lower()
            if f"name_{player}" in self.sounds.effects:
                self.sounds.play(f"name_{player}")
                QTimer.singleShot(750, lambda: self.sounds.play(f"word_{color}") if self.mode == "bear" and self.bear is not None and self.bear.current_player == player and not self.bear.moving and not self.celebrating else None)
            else:
                self.sounds.play(f"word_{color}")

    def _activity_unlocked(self, kind: str, number: int) -> bool:
        cleared = self.activity_cleared.get(kind, [])
        return 1 <= number <= activity_info(kind)['levels'] and (number == 1 or number - 1 in cleared or number in cleared)

    def _activity_continue(self, kind: str) -> int:
        return next((n for n in range(1, activity_info(kind)['levels'] + 1)
                     if n not in self.activity_cleared.get(kind, []) and self._activity_unlocked(kind, n)), 1)

    def _record_activity(self, kind: str, level: int) -> None:
        cleared = self.activity_cleared.setdefault(kind, [])
        if level not in cleared:
            cleared.append(level)
            save_activity_progress(self.activity_cleared)

    def _open_hub(self) -> None:
        self._stop_arabic_tutor()
        self._stop_speech()
        self._ensure_camera()
        self.mode = 'hub'
        self.celebrating = False
        self.hub_focus = 0
        self.hub_scan_at = time.monotonic()
        self.hub_gesture.reset()
        if self.worker is not None:
            self.worker.require_three_players = False
            self.worker.calibrate_for_three = False
            self.worker.reset_tracking = True
        self.update()

    def _open_activity(self, kind: str) -> None:
        if kind not in HUB_KINDS:
            return
        if kind == 'arabic':
            self._begin_arabic_tutor()
            return
        self._stop_speech()
        self.mode = 'activity_select'
        self.selection_kind = kind
        self.celebrating = False
        self.activity_gesture.reset()
        self.update()

    def _begin_arabic_tutor(self) -> None:
        self._stop_arabic_tutor()
        self._stop_speech()
        self.sounds.stop_all()
        self.mode = 'arabic_live'
        self.level = None
        self.team = None
        self.bear = None
        self.voice_round = None
        self.paused = False
        self.celebrating = False
        self.arabic_status = 'connecting'
        self.arabic_transcript = ''
        self.arabic_state = ArabicTutorState([]).snapshot()
        if not self._stop_camera():
            self.arabic_status = 'camera_error'
            self.update()
            return
        worker = ArabicTutorWorker([])
        self.arabic_worker = worker
        worker.status.connect(lambda status: self._arabic_status_changed(worker, status))
        worker.changed.connect(lambda state: self._arabic_state_changed(worker, state))
        worker.transcript.connect(lambda text: self._arabic_transcript_changed(worker, text))
        worker.go_home.connect(lambda: self._open_hub() if self.arabic_worker is worker else None)
        worker.start()
        self.update()

    def _stop_arabic_tutor(self) -> None:
        worker = self.arabic_worker
        if worker is not None:
            self.arabic_worker = None
            worker.stop()
            worker.wait(8000)

    def _arabic_status_changed(self, worker, status: str) -> None:
        if self.arabic_worker is worker:
            self.arabic_status = status
            self.update()

    def _arabic_state_changed(self, worker, state: dict) -> None:
        if self.arabic_worker is worker:
            self.arabic_state = state
            self.update()

    def _arabic_transcript_changed(self, worker, text: str) -> None:
        if self.arabic_worker is worker:
            self.arabic_transcript = text[:250]
            self.update()

    def _begin_activity(self, kind: str, number: int) -> None:
        if kind in TEAM_GAMES:
            self._begin_team(kind, number)
        elif kind in VOICE_GAMES:
            self._begin_voice(kind, number)

    def _prepare_cooperative_tracking(self) -> None:
        self.raised.clear()
        self.armed.clear()
        self.both_since.clear()
        self.flash.clear()
        self.wait_for_arms_down = True
        self.missing_since = None
        self.had_body = False
        self.ignore_tracking_loss = False
        self.bear_calibrated = self.worker is None
        if self.worker is not None:
            self.worker.require_three_players = True
            self.worker.calibrate_for_three = True
            self.worker.reset_tracking = True

    def _begin_team(self, kind: str, number: int) -> None:
        if kind not in TEAM_GAMES or not self._activity_unlocked(kind, number):
            return
        self._stop_speech()
        self.sounds.play('start')
        self.team = TeamGame(kind=kind, level=number)
        self.bear = None
        self.level = None
        self.voice_round = None
        self.mode = 'team'
        self.paused = False
        self.pause_reason = ''
        self.celebrating = False
        self.next_gesture.reset()
        self.bear_last_tick = time.monotonic()
        self._prepare_cooperative_tracking()
        if self.bear_calibrated:
            self._say_team_turn()
        self.update()

    def _say_team_turn(self) -> None:
        if self.team is not None and self.team.current_player is not None:
            player = self.team.current_player
            if f'name_{player}' in self.sounds.effects:
                self.sounds.play(f'name_{player}')
            else:
                self.sounds.play(f"word_{PLAYERS[player][0].lower()}")

    def _begin_voice(self, kind: str, number: int) -> None:
        if kind not in VOICE_GAMES or not self._activity_unlocked(kind, number):
            return
        self._stop_speech()
        self.voice_request += 1
        self.voice_round = VoiceRound(kind=kind, level=number)
        self.team = None
        self.bear = None
        self.level = None
        self.mode = 'voice'
        self.paused = False
        self.pause_reason = ''
        self.celebrating = False
        self.next_gesture.reset()
        self.bear_last_tick = time.monotonic()
        self.voice_busy = False
        self.voice_feedback = ''
        self.voice_last_item = None
        self.voice_prompted = None
        self._prepare_cooperative_tracking()
        self._ensure_speech()
        self._announce_voice_prompt()
        self.update()

    def _ensure_speech(self) -> None:
        if self.speech_worker is not None and self.speech_worker.isRunning():
            return
        self.voice_status = 'loading'
        worker = SpeechWorker(self.settings)
        self.speech_worker = worker
        worker.status.connect(lambda status: self._on_voice_status(status) if self.speech_worker is worker else None)
        worker.result.connect(lambda request, text, error: self._on_voice_result(request, text, error) if self.speech_worker is worker else None)
        worker.start()

    def _stop_speech(self) -> None:
        if self.speech_worker is not None:
            self.voice_request += 1
            self.speech_worker.stop()
            self.speech_worker.wait(5000)
            self.speech_worker = None
        self.voice_status = 'unavailable'
        self.voice_busy = False

    def _on_voice_status(self, status: str) -> None:
        if self.mode != 'voice':
            return
        self.voice_status = status
        if status == 'ready' and not self.voice_feedback:
            self._announce_voice_prompt()
        self.update()

    def _announce_voice_prompt(self) -> None:
        if self.mode != 'voice' or self.voice_round is None or self.celebrating or self.voice_status != 'ready' or not self.bear_calibrated:
            return
        game = self.voice_round
        marker = (game.kind, game.level, game.turn)
        if self.voice_prompted == marker:
            return
        self.voice_prompted = marker
        player = game.current_player
        if f'name_{player}' in self.sounds.effects:
            self.sounds.play(f'name_{player}')
        prompt = {'arabic': 'ask_ar', 'word_garden': 'ask_word', 'places': 'ask_place',
                  'animals': 'ask_animal', 'story': 'ask_story', 'village': 'ask_village'}[game.kind]
        def play_prompt():
            if self.mode == 'voice' and self.voice_round is game and not self.celebrating and not self.voice_busy and (game.kind, game.level, game.turn) == marker:
                self.sounds.play(prompt)
                if game.kind in ('word_garden', 'places'):
                    QTimer.singleShot(1600, lambda: self.sounds.play(f'letter_{game.letter.lower()}') if self.mode == 'voice' and self.voice_round is game and not self.voice_busy and (game.kind, game.level, game.turn) == marker else None)
        QTimer.singleShot(750, play_prompt)

    def _on_voice_result(self, request_id: int, text: str, error: str) -> None:
        if self.mode != 'voice' or self.voice_round is None or request_id != self.voice_request:
            return
        self.voice_busy = False
        game = self.voice_round
        item = game.item if game.kind == 'arabic' else None
        if not error and game.accept(text):
            self.voice_last_item = item
            self.voice_feedback = 'Wonderful! A team star!'
            if item is not None:
                self.sounds.play(f'ar_{item.picture}')
            else:
                self.sounds.play('good')
            if game.complete:
                self.celebrating = True
                self.next_gesture.reset()
                self._record_activity(game.kind, game.level)
                QTimer.singleShot(1000, lambda: self.sounds.play('victory') if self.mode == 'voice' and self.voice_round is game and self.celebrating else None)
            else:
                self.voice_prompted = None
                QTimer.singleShot(2200, lambda: self._resume_voice_prompt(game, request_id))
        else:
            self.voice_feedback = "Let's try together!"
            self.sounds.play('try')
            self.voice_prompted = None
            QTimer.singleShot(1800, lambda: self._resume_voice_prompt(game, request_id))
        self.update()

    def _resume_voice_prompt(self, game: VoiceRound, request_id: int) -> None:
        if self.mode == 'voice' and self.voice_round is game and self.voice_request == request_id and not self.celebrating:
            self.voice_feedback = ''
            self.voice_last_item = None
            self._announce_voice_prompt()
            self.update()

    def _voice_hint(self) -> None:
        if self.voice_round is None or self.voice_busy or self.celebrating:
            return
        if self.voice_round.kind == 'arabic':
            self.sounds.play(f'ar_{self.voice_round.item.picture}')
        elif self.voice_round.kind in ('word_garden', 'places'):
            prefix = 'example' if self.voice_round.kind == 'word_garden' else 'places'
            self.sounds.play(f'{prefix}_{self.voice_round.letter.lower()}')
        else:
            prompt = {'animals': 'ask_animal', 'story': 'ask_story', 'village': 'ask_village'}[self.voice_round.kind]
            self.sounds.play(prompt)

    def _turn(self, player: int, clockwise: bool, manual: bool = False) -> None:
        if self.mode == "bear":
            if self.bear is not None and (self.bear_calibrated or manual) and not self.paused and not self.celebrating and self.bear.open_next_gate(player):
                self.sounds.play(f"mirror{player}")
                self.sounds.play("success")
                self.flash[player] = (time.monotonic() + 0.45, clockwise)
                gate_count = self.bear.gates_open
                QTimer.singleShot(250, lambda: self.sounds.play("word_star") if self.mode == "bear" and self.bear is not None and self.bear.gates_open == gate_count and self.bear.moving else None)
            return
        if self.mode == 'team':
            if self.team is not None and (self.bear_calibrated or manual) and not self.paused and not self.celebrating and self.team.act(player):
                self.sounds.play(f'note_{player}' if self.team.kind == 'music' else 'success')
                self.flash[player] = (time.monotonic() + 0.45, clockwise)
            return
        if self.mode == 'voice':
            if (self.voice_round is not None and self.speech_worker is not None and self.voice_status == 'ready'
                    and not self.voice_busy and not self.paused and not self.celebrating
                    and (self.bear_calibrated or manual) and player == self.voice_round.current_player):
                self.voice_request += 1
                self.voice_busy = True
                self.voice_feedback = ''
                self.voice_status = 'listening'
                self.sounds.stop_all()
                self.speech_worker.listen(self.voice_request, 'ar' if self.voice_round.kind == 'arabic' else 'en')
                self.update()
            return
        if self.level is None or self.beam.solved or self.paused or self.celebrating:
            return
        for mirror in self.level.mirrors:
            if mirror.player == player:
                mirror.turn(clockwise)
        was_blocked = self.beam.blocked
        self.beam = trace(self.level)
        self.sounds.play(f"mirror{player}")
        if self.beam.solved:
            self.sounds.play("success")
        elif self.beam.blocked and not was_blocked:
            self.sounds.play("blocked")
        self.flash[player] = (time.monotonic() + 0.45, clockwise)
        self.hold = 0.0

    def _watch_tracking(self) -> None:
        if self.mode == 'voice':
            return
        if self.mode not in ("play", "bear", "team", "voice") or self.celebrating or not self.had_body or self.ignore_tracking_loss:
            return
        if self.camera_status == "starting":
            return
        now = time.monotonic()
        if self.bodies:
            self.missing_since = None
            return
        if self.missing_since is None:
            self.missing_since = now
        elif now - self.missing_since > 3.0 and not self.paused:
            self._pause('tracking')

    def _on_preview(self, image) -> None:
        self.preview = image

    def _tracking_reset(self) -> None:
        self.raised.clear()
        self.armed.clear()
        self.both_since.clear()
        if not self.celebrating:
            self.next_gesture.reset()
            if self.mode in ("bear", "team", "voice") and self.worker is not None:
                self.bear_calibrated = False
        self.wait_for_arms_down = True

    def _on_status(self, status: str) -> None:
        self.camera_status = status
        if status == "missing":
            self.preview = None
            self._watch_tracking()

    def _on_bodies(self, bodies) -> None:
        if self.celebrating:
            self.bodies = list(bodies)
            return
        self.bodies = list(bodies)
        now = time.monotonic()
        if self.bodies:
            self.had_body = True
            self.missing_since = None
            if self.pause_reason == "tracking":
                self._resume(manual=False)
        arms_up = any(body.left_up or body.right_up for body in self.bodies)
        if self.wait_for_arms_down:
            if not self.bodies:
                return
            if arms_up:
                return
            self.wait_for_arms_down = False
            if self.paused and self.pause_reason == "arms":
                self._resume(manual=False)
                self.wait_for_arms_down = False
            return
        if self.mode not in ("play", "bear", "team", "voice") or (self.mode == "play" and self.level is None):
            return
        present = {body.player for body in self.bodies}
        for player in list(self.both_since):
            if player not in present:
                self.both_since.pop(player, None)
        for key in list(self.raised):
            if key[0] not in present:
                self.raised.pop(key, None)
        for body in self.bodies:
            index = body.player
            if index is None:
                continue
            if body.left_up and body.right_up:
                self.both_since.setdefault(index, now)
                if now - self.both_since[index] > 1.5 and not self.paused:
                    self._pause('arms')
                continue
            self.both_since.pop(index, None)
            self._arm(index, "left", body.left_up, now, clockwise=False)
            self._arm(index, "right", body.right_up, now, clockwise=True)

    def _on_poses(self, bodies) -> None:
        if self.mode == "home":
            if self.bear_menu_gesture.update(bodies, time.monotonic()):
                if self.home_focus == 0:
                    self._begin(self._continue_number())
                elif self.home_focus == 1:
                    self._open_bear_menu()
                else:
                    self._open_hub()
            return
        if self.mode == "bear_select":
            if self.bear_menu_gesture.update(bodies, time.monotonic()):
                self._begin_bear(self._bear_continue_number())
            return
        if self.mode == 'hub':
            if self.hub_gesture.update(bodies, time.monotonic()):
                self._open_activity(HUB_KINDS[self.hub_focus])
            return
        if self.mode == 'activity_select':
            if self.activity_gesture.update(bodies, time.monotonic()):
                self._begin_activity(self.selection_kind, self._activity_continue(self.selection_kind))
            return
        if self.celebrating and self.next_gesture.update(bodies, time.monotonic()):
            self._after_win()

    def _arm(self, player: int, side: str, up: bool, now: float, clockwise: bool) -> None:
        key = (player, side)
        if not up:
            self.raised.pop(key, None)
            self.armed.discard(key)
            return
        if key in self.armed or self.paused:
            return
        self.raised.setdefault(key, now)
        if now - self.raised[key] >= 0.25:
            self.armed.add(key)
            self._turn(player, clockwise)

    def _resume(self, manual: bool = True) -> None:
        if manual and self.pause_reason == "tracking":
            self.ignore_tracking_loss = True
        self.paused = False
        self.pause_reason = ""
        self.wait_for_arms_down = True
        if self.mode == 'voice' and self.speech_worker is None:
            self.voice_feedback = ''
            self.voice_prompted = None
            self._ensure_speech()

    def _pause(self, reason: str) -> None:
        self.paused = True
        self.pause_reason = reason
        self.wait_for_arms_down = True
        if self.mode == 'voice':
            self._stop_speech()

    def keyPressEvent(self, event) -> None:
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_M:
            if self.sounds.toggle():
                self.sounds.play("menu")
            self.update()
            return
        if key == Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
            return
        if self.mode == 'arabic_live':
            if key == Qt.Key.Key_Escape:
                self._open_hub()
            return
        if self.mode == "home":
            self._home_key(key)
            return
        if self.mode == "bear_select":
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._begin_bear(self._bear_continue_number())
            elif key == Qt.Key.Key_Escape:
                self._stop_speech()
                self.mode = "home"
                if self.worker is not None:
                    self.worker.require_three_players = False
                    self.worker.calibrate_for_three = False
                    self.worker.reset_tracking = True
            return
        if self.mode == 'hub':
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._open_activity(HUB_KINDS[self.hub_focus])
            elif key == Qt.Key.Key_Escape:
                self.mode = 'home'
            return
        if self.mode == 'activity_select':
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._begin_activity(self.selection_kind, self._activity_continue(self.selection_kind))
            elif key == Qt.Key.Key_Escape:
                self._open_hub()
            return
        if self.mode == "play" and key == Qt.Key.Key_H:
            self.hint_step = (self.hint_step + 1) % 4
            self.sounds.play("hint")
            return
        if self.celebrating:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._after_win()
            elif key == Qt.Key.Key_R:
                if self.mode == "bear" and self.bear is not None:
                    self._begin_bear(self.bear.level)
                elif self.mode == 'team' and self.team is not None:
                    self._begin_team(self.team.kind, self.team.level)
                elif self.mode == 'voice' and self.voice_round is not None:
                    self._begin_voice(self.voice_round.kind, self.voice_round.level)
                elif self.level is not None:
                    self._begin(self.level.number)
            elif key == Qt.Key.Key_Escape:
                self.mode = "home"
            return
        if self.paused:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_P, Qt.Key.Key_Escape):
                self._resume()
            elif key == Qt.Key.Key_R:
                if self.mode == "bear" and self.bear is not None:
                    self._begin_bear(self.bear.level)
                elif self.mode == 'team' and self.team is not None:
                    self._begin_team(self.team.kind, self.team.level)
                elif self.mode == 'voice' and self.voice_round is not None:
                    self._begin_voice(self.voice_round.kind, self.voice_round.level)
                elif self.level is not None:
                    self._begin(self.level.number)
            return
        if key in (Qt.Key.Key_P, Qt.Key.Key_Escape):
            self._pause('key')
            return
        mapped = KEYS.get(key)
        if mapped:
            self._turn(*mapped, manual=True)
        self.update()

    def _home_key(self, key: int) -> None:
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._begin(self._continue_number())
            return
        if key == Qt.Key.Key_B:
            self._open_bear_menu()
            return
        numbers = {
            Qt.Key.Key_1: 1,
            Qt.Key.Key_2: 2,
            Qt.Key.Key_3: 3,
            Qt.Key.Key_4: 4,
            Qt.Key.Key_5: 5,
            Qt.Key.Key_6: 6,
        }
        number = numbers.get(key)
        if number:
            self._begin(number)

    def _after_win(self) -> None:
        if self.mode == "bear" and self.bear is not None:
            nxt = self.bear.level + 1
            if nxt <= len(BEAR_LEVELS):
                self._begin_bear(nxt)
            else:
                self._open_bear_menu()
            return
        if self.mode == 'team' and self.team is not None:
            kind, nxt = self.team.kind, self.team.level + 1
            if nxt <= activity_info(kind)['levels']:
                self._begin_team(kind, nxt)
            else:
                self._open_activity(kind)
            return
        if self.mode == 'voice' and self.voice_round is not None:
            kind, nxt = self.voice_round.kind, self.voice_round.level + 1
            if nxt <= activity_info(kind)['levels']:
                self._begin_voice(kind, nxt)
            else:
                self._open_activity(kind)
            return
        if self.level is None:
            self.mode = "home"
            return
        nxt = self.level.number + 1
        if nxt <= 6:
            self._begin(nxt)
        else:
            self.mode = "home"

    def mousePressEvent(self, event) -> None:
        point = self._logical(event.position())
        if point is None:
            return
        x, y = point
        for rect, action in self.hotspots:
            if action and rect.contains(x, y):
                self._activate(action)
                return

    def _activate(self, action: tuple) -> None:
        kind = action[0]
        if kind == "sound":
            if self.sounds.toggle():
                self.sounds.play("menu")
        elif kind not in ("play", "level", "restart", "next", "hint"):
            self.sounds.play("menu")
        if kind == "play":
            self._begin(self._continue_number())
        elif kind == "level":
            self._begin(action[1])
        elif kind == "bear_menu":
            self._open_bear_menu()
        elif kind == "bear_play":
            self._begin_bear(self._bear_continue_number())
        elif kind == "bear_level":
            self._begin_bear(action[1])
        elif kind == 'hub':
            self._open_hub()
        elif kind == 'activity':
            self._open_activity(action[1])
        elif kind == 'activity_play':
            self._begin_activity(self.selection_kind, self._activity_continue(self.selection_kind))
        elif kind == 'activity_level':
            self._begin_activity(self.selection_kind, action[1])
        elif kind == 'voice_listen' and self.voice_round is not None:
            self._turn(self.voice_round.current_player, False, manual=True)
        elif kind == 'voice_hint' and self.voice_round is not None:
            self._voice_hint()
        elif kind == "hint":
            self.hint_step = (self.hint_step + 1) % 4
            self.sounds.play("hint")
        elif kind == "pause":
            self._pause('key')
        elif kind == "resume":
            self._resume()
        elif kind == "restart":
            if self.mode == "bear" and self.bear is not None:
                self._begin_bear(self.bear.level)
            elif self.mode == 'team' and self.team is not None:
                self._begin_team(self.team.kind, self.team.level)
            elif self.mode == 'voice' and self.voice_round is not None:
                self._begin_voice(self.voice_round.kind, self.voice_round.level)
            elif self.level is not None:
                self._begin(self.level.number)
        elif kind == "home":
            self._stop_speech()
            self.mode = "home"
            self.celebrating = False
            self.next_gesture.reset()
            self.bear_menu_gesture.reset()
            if self.worker is not None:
                self.worker.require_three_players = False
                self.worker.calibrate_for_three = False
                self.worker.reset_tracking = True
        elif kind == "next":
            self._after_win()
        self.update()

    def _logical(self, pos) -> tuple[float, float] | None:
        ox, oy, scale = self._view
        if scale <= 0:
            return None
        return (pos.x() - ox) / scale, (pos.y() - oy) / scale

    def closeEvent(self, event) -> None:
        self._stop_arabic_tutor()
        self._stop_speech()
        if not self._stop_camera():
            event.ignore()
            return
        event.accept()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = min(self.width() / VIEW_W, self.height() / VIEW_H)
        ox = (self.width() - VIEW_W * scale) / 2
        oy = (self.height() - VIEW_H * scale) / 2
        self._view = (ox, oy, scale)
        painter.translate(ox, oy)
        painter.scale(scale, scale)
        self.hotspots = []
        try:
            self._background(painter)
            if self.mode == "home":
                self._home(painter)
            elif self.mode == "bear_select":
                self._bear_menu(painter)
            elif self.mode == "bear":
                self._bear_play(painter)
            elif self.mode == 'hub':
                self._hub(painter)
            elif self.mode == 'activity_select':
                self._activity_menu(painter)
            elif self.mode == 'team':
                self._team_play(painter)
            elif self.mode == 'voice':
                self._voice_play(painter)
            elif self.mode == 'arabic_live':
                self._arabic_live_play(painter)
            else:
                self._play(painter)
            if self.mode != 'arabic_live':
                self._button(painter, QRectF(16, 16, 132, 42), "Sound on" if self.sounds.enabled else "Sound off", ("sound",))
        finally:
            painter.end()

    def _background(self, painter: QPainter) -> None:
        if self.mode == "bear" and self.bear is not None:
            scenes = ("bear_forest", "bear_meadow", "bear_sunset")
            name = scenes[min(2, (self.bear.level - 1) // 4)]
        elif self.mode == "bear_select":
            name = "bear_forest"
        elif self.mode == 'team' and self.team is not None:
            name = TEAM_GAMES[self.team.kind]['scene']
        elif self.mode == 'arabic_live':
            name = 'scene_music'
        elif self.mode == 'voice' and self.voice_round is not None:
            name = VOICE_GAMES[self.voice_round.kind]['scene']
        elif self.mode == 'activity_select' and self.selection_kind:
            name = activity_info(self.selection_kind)['scene']
        elif self.mode == 'hub':
            name = 'bear_meadow'
        else:
            name = "courtyard"
        pixmap = self.art.get(name)
        if pixmap is not None:
            painter.drawPixmap(QRectF(0, 0, VIEW_W, VIEW_H), pixmap, QRectF(pixmap.rect()))
            return
        painter.fillRect(QRectF(0, 0, VIEW_W, VIEW_H), QColor("#16324F"))

    def _home(self, painter: QPainter) -> None:
        self._shade(painter, 150)
        panel = QRectF(150, 70, 980, 500)
        self._panel(painter, panel, 28)
        self._title(painter, QRectF(180, 88, 920, 54), "Magic Mirror Maze", 42)
        font = self._font(20)
        painter.setFont(font)
        painter.setPen(GOLD)
        painter.drawText(
            QRectF(180, 146, 920, 32),
            Qt.AlignmentFlag.AlignCenter,
            "Three mirrors. One light. Play together.",
        )
        lines = (
            "Three players stand left, middle, and right. Raise an arm to play.",
            "Mirror Maze: guide the light together. Bear Adventure: help Bear home.",
            "Wait for a game to glow, then hold one arm up to choose it.",
        )
        painter.setPen(QColor("#F4F7FB"))
        painter.setFont(self._font(18))
        for index, line in enumerate(lines):
            painter.drawText(QRectF(200, 196 + index * 32, 880, 30), Qt.AlignmentFlag.AlignCenter, line)
        stars = len(self.cleared)
        painter.setPen(GOLD)
        painter.setFont(self._font(18, bold=True))
        painter.drawText(QRectF(200, 300, 880, 28), Qt.AlignmentFlag.AlignCenter, f"Team stars  {stars} / 6")
        self._button(painter, QRectF(205, 342, 270, 58), "Mirror Maze", ("play",), fill="#F0C14A" if self.home_focus == 0 else "#314E79")
        self._button(painter, QRectF(505, 342, 270, 58), "Bear Adventure", ("bear_menu",), fill="#F0C14A" if self.home_focus == 1 else "#3D8F68")
        self._button(painter, QRectF(805, 342, 270, 58), "More Games", ("hub",), fill="#F0C14A" if self.home_focus == 2 else "#704D91")
        for number, level in enumerate(campaign(), start=1):
            rect = QRectF(176 + (number - 1) * 156, 430, 146, 92)
            open_level = self._unlocked(number)
            name = level.name if open_level else "Locked"
            mark = "★" if number in self.cleared else str(number)
            self._button(
                painter,
                rect,
                f"{mark}\n{name}",
                ("level", number) if open_level else None,
                fill="#1E3350" if open_level else "#243044",
            )
        self._camera_card(painter, QRectF(992, 584, 256, 120))

    def _hub(self, painter: QPainter) -> None:
        self._shade(painter, 115)
        self._panel(painter, QRectF(150, 42, 980, 526), 28)
        self._title(painter, QRectF(180, 60, 920, 54), "Play & Learn Together", 38)
        painter.setPen(QColor("#FFF8E8"))
        painter.setFont(self._font(18, bold=True))
        painter.drawText(QRectF(190, 122, 900, 30), Qt.AlignmentFlag.AlignCenter,
                         "Choose a game to play together  ·  مل کر کھیلیں")
        painter.setPen(GOLD)
        painter.setFont(self._font(15, bold=True))
        instruction = "Click a game, or wait for it to glow and hold up one arm."
        if self.hub_gesture.progress:
            instruction = f"Keep your arm up to choose {activity_info(HUB_KINDS[self.hub_focus])['title']}... {int(self.hub_gesture.progress * 100)}%"
        painter.drawText(QRectF(190, 158, 900, 30), Qt.AlignmentFlag.AlignCenter, instruction)
        for index, kind in enumerate(HUB_KINDS):
            info = activity_info(kind)
            col, row = index % 4, index // 4
            rect = QRectF(180 + col * 231, 205 + row * 82, 220, 73)
            selected = index == self.hub_focus
            self._button(painter, rect, f"{info['title']}\n{info['urdu']}", ('activity', kind),
                         fill="#F0C14A" if selected else "#35526C")
        self._button(painter, QRectF(205, 478, 215, 57), "Home", ("home",), fill="#314E79")
        self._camera_card(painter, QRectF(992, 584, 256, 120))

    def _activity_menu(self, painter: QPainter) -> None:
        info = activity_info(self.selection_kind)
        cleared = self.activity_cleared.get(self.selection_kind, [])
        self._shade(painter, 115)
        self._panel(painter, QRectF(150, 42, 980, 526), 28)
        self._title(painter, QRectF(180, 60, 920, 54), info['title'], 38)
        painter.setPen(QColor("#FFF8E8"))
        painter.setFont(self._font(19, bold=True))
        painter.drawText(QRectF(190, 122, 900, 30), Qt.AlignmentFlag.AlignCenter,
                         f"{info['urdu']}   ·   Three friends, one team!")
        painter.setPen(GOLD)
        painter.setFont(self._font(16, bold=True))
        instruction = "Lower an arm, then hold it up for 2 seconds to start."
        if self.activity_gesture.ready:
            instruction = "Raise one arm for 2 seconds to start!"
        if self.activity_gesture.progress:
            instruction = f"Keep your arm up... {int(self.activity_gesture.progress * 100)}%"
        painter.drawText(QRectF(190, 158, 900, 28), Qt.AlignmentFlag.AlignCenter, instruction)
        painter.setFont(self._font(15))
        painter.drawText(QRectF(190, 188, 900, 24), Qt.AlignmentFlag.AlignCenter,
                         f"Team progress: {len(cleared)} / {info['levels']} levels")
        for index in range(info['levels']):
            number = index + 1
            col, row = index % 4, index // 4
            offset = 231 if info['levels'] == 2 else 0
            rect = QRectF(180 + offset + col * 231, 222 + row * 75, 220, 66)
            unlocked = self._activity_unlocked(self.selection_kind, number)
            mark = '★' if number in cleared else str(number)
            self._button(painter, rect, f"{mark}   Level {number}" if unlocked else f"{number}   Locked",
                         ('activity_level', number) if unlocked else None, fill="#365A69" if unlocked else "#2D3B4B")
        self._button(painter, QRectF(205, 478, 215, 57), "Games", ('hub',), fill="#314E79")
        self._button(painter, QRectF(440, 478, 400, 57), "Play" if not cleared else "Continue",
                     ('activity_play',), fill="#F0C14A")
        self._camera_card(painter, QRectF(992, 584, 256, 120))

    def _bear_menu(self, painter: QPainter) -> None:
        self._shade(painter, 105)
        self._panel(painter, QRectF(150, 42, 980, 526), 28)
        self._title(painter, QRectF(180, 60, 920, 54), "Help the Lost Bear", 40)
        painter.setPen(QColor("#FFF8E8"))
        painter.setFont(self._font(18, bold=True))
        painter.drawText(QRectF(190, 122, 900, 30), Qt.AlignmentFlag.AlignCenter,
                         "Three friends, three gates!   ·   ریچھ کو گھر پہنچائیں")
        painter.setPen(GOLD)
        painter.setFont(self._font(16, bold=True))
        instruction = "Lower an arm, then hold it up for 2 seconds to start."
        if self.bear_menu_gesture.ready:
            instruction = "Raise one arm for 2 seconds to start!"
        if self.bear_menu_gesture.progress:
            instruction = f"Keep your arm up... {int(self.bear_menu_gesture.progress * 100)}%"
        painter.drawText(QRectF(190, 158, 900, 28), Qt.AlignmentFlag.AlignCenter, instruction)
        painter.setFont(self._font(15))
        painter.drawText(QRectF(190, 188, 900, 24), Qt.AlignmentFlag.AlignCenter,
                         f"Bear's journey: {len(self.bear_cleared)} / {len(BEAR_LEVELS)} levels completed")
        for index, level in enumerate(BEAR_LEVELS):
            number = index + 1
            column, row = index % 4, index // 4
            rect = QRectF(180 + column * 231, 222 + row * 75, 220, 66)
            unlocked = self._bear_unlocked(number)
            mark = "★" if number in self.bear_cleared else str(number)
            label = f"{mark}  {level.name}" if unlocked else f"{number}  Locked"
            self._button(painter, rect, label, ("bear_level", number) if unlocked else None,
                         fill="#365A69" if unlocked else "#2D3B4B")
        self._button(painter, QRectF(205, 478, 215, 57), "Back", ("home",), fill="#314E79")
        self._button(painter, QRectF(440, 478, 400, 57), "Play" if not self.bear_cleared else "Continue",
                     ("bear_play",), fill="#F0C14A")
        self._camera_card(painter, QRectF(992, 584, 256, 120))

    def _bear_play(self, painter: QPainter) -> None:
        if self.bear is None:
            return
        level = BEAR_LEVELS[self.bear.level - 1]
        self._title(painter, QRectF(285, 10, 710, 46), "Help the Lost Bear", 30)
        self._button(painter, QRectF(1140, 16, 124, 42), "Pause", ("pause",), fill="#314E79")
        self._panel(painter, QRectF(270, 65, 740, 130), 20)
        painter.setPen(QColor(level.accent))
        painter.setFont(self._font(15, bold=True))
        painter.drawText(QRectF(290, 70, 700, 24), Qt.AlignmentFlag.AlignCenter,
                         f"LEVEL {self.bear.level} OF {len(BEAR_LEVELS)}  ·  {level.name.upper()}")
        if not self.bear_calibrated:
            message = "THREE FRIENDS: STEP INTO THE CAMERA!"
            urdu = "تینوں بچے کیمرے کے سامنے آئیں"
            color = QColor("#FFF7E0")
        elif self.bear.moving:
            message = "The gate is open! Watch Bear walk."
            urdu = "ریچھ چل رہا ہے!"
            color = QColor("#FFF7E0")
        elif self.bear.home:
            message = "Bear is home! Hooray!"
            urdu = "ریچھ گھر پہنچ گیا!"
            color = QColor("#FFF7E0")
        else:
            player = self.bear.current_player
            name, hex_color, _ = PLAYERS[player]
            child = self.players[player - 1]
            message = f"{child['name'].upper()}  ·  {name.upper()}: RAISE AN ARM!"
            urdu_name = child["urdu"] or URDU_COLORS[player]
            urdu = f"{urdu_name}  ·  {URDU_COLORS[player]}  ·  اپنا ہاتھ اوپر کریں"
            color = QColor(hex_color).lighter(155)
        painter.setPen(color)
        painter.setFont(self._font(27, bold=True))
        painter.drawText(QRectF(290, 95, 700, 38), Qt.AlignmentFlag.AlignCenter, message)
        painter.setPen(QColor("#FFF7E0"))
        painter.setFont(self._font(18, bold=True))
        painter.drawText(QRectF(290, 130, 700, 28), Qt.AlignmentFlag.AlignCenter, urdu)
        painter.setPen(QColor("#F6E8BF"))
        painter.setFont(self._font(14, bold=True))
        stars = "★" * self.bear.gates_open + "☆" * (3 - self.bear.gates_open)
        painter.drawText(QRectF(290, 165, 700, 22), Qt.AlignmentFlag.AlignCenter,
                         f"{stars}   TEAM STARS / ٹیم کے ستارے")

        for index, player in enumerate(level.order):
            self._bear_gate(painter, 280 + index * 250, 485, player,
                            opened=index == self.bear.gates_open - 1 and (self.bear.moving or self.bear.home),
                            active=self.bear_calibrated and not self.bear.moving and not self.bear.home and index == self.bear.gates_open)
        if self.bear.moving and self.bear.gates_open:
            gate_x = 280 + (self.bear.gates_open - 1) * 250
            self._bear_sparkles(painter, gate_x, 350, level.accent)

        bear_x = 155 + self.bear.position * 250 + max(0.0, self.bear.position - 2) * 185
        bob = math.sin(time.monotonic() * 10) * 4 if self.bear.moving else 0
        if not self.celebrating:
            self._sprite(painter, "bear", bear_x, 493 + bob, 195, anchor=1.0)
        self._panel(painter, QRectF(16, 568, 980, 42), 14)
        painter.setPen(QColor("#FFF8E8"))
        painter.setFont(self._font(16, bold=True))
        if self.wait_for_arms_down and self.bodies and not self.celebrating:
            instruction = "Everyone lower your arms first, then the player whose color is shown can raise one."
        else:
            instruction = "Each child opens their own color gate. Lower your arm after your turn."
        painter.drawText(QRectF(28, 568, 956, 42), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, instruction)
        self._bear_cards(painter)
        self._camera_card(painter, QRectF(1008, 508, 256, 196))
        if self.celebrating:
            self._overlay_card(painter, "Bear is home!\nریچھ گھر پہنچ گیا!", win=True)
            painter.save()
            painter.translate(1115, 475)
            painter.rotate(math.sin(time.monotonic() * 4) * 5)
            self._sprite(painter, "bear", 0, 0, 200, anchor=1.0)
            painter.restore()
        elif self.paused:
            text = {
                "tracking": "Step back into the camera. Press P to use keys.",
                "arms": "Paused. Lower both arms to continue.",
            }.get(self.pause_reason, "Paused.")
            self._overlay_card(painter, text, win=False)

    def _bear_gate(self, painter: QPainter, x: float, bottom: float, player: int, opened: bool, active: bool) -> None:
        name, hex_color, badge = PLAYERS[player]
        color = QColor(hex_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(60, 42, 28, 85))
        painter.drawEllipse(QRectF(x - 72, bottom - 10, 144, 24))
        if active:
            glow = QColor(color.lighter(150))
            glow.setAlpha(80 + int(30 * (1 + math.sin(time.monotonic() * 4))))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(glow, 12))
            painter.drawRoundedRect(QRectF(x - 62, bottom - 173, 124, 174), 36, 36)
        frame = QPainterPath()
        frame.moveTo(x - 53, bottom)
        frame.lineTo(x - 53, bottom - 113)
        frame.quadTo(x - 53, bottom - 168, x, bottom - 168)
        frame.quadTo(x + 53, bottom - 168, x + 53, bottom - 113)
        frame.lineTo(x + 53, bottom)
        painter.setPen(QPen(QColor("#633B25"), 15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(frame)
        painter.setPen(QPen(QColor("#F9D98C"), 3))
        painter.drawPath(frame)
        if not opened:
            door = QPainterPath()
            door.moveTo(x - 43, bottom - 2)
            door.lineTo(x - 43, bottom - 112)
            door.quadTo(x - 43, bottom - 153, x, bottom - 153)
            door.quadTo(x + 43, bottom - 153, x + 43, bottom - 112)
            door.lineTo(x + 43, bottom - 2)
            door.closeSubpath()
            painter.setBrush(QColor("#A96537"))
            painter.setPen(QPen(QColor("#E7B77B"), 3))
            painter.drawPath(door)
            painter.setPen(QPen(QColor("#774326"), 3))
            painter.drawLine(QPointF(x, bottom - 150), QPointF(x, bottom - 2))
            painter.setBrush(color)
            painter.setPen(QPen(QColor("#FFF3CD"), 3))
            painter.drawEllipse(QPointF(x, bottom - 80), 24, 24)
            self._badge_mark(painter, badge, x, bottom - 80, 12)
        else:
            painter.setPen(QPen(QColor("#B78048"), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(x - 49, bottom - 3), QPointF(x - 77, bottom - 20))
            painter.drawLine(QPointF(x + 49, bottom - 3), QPointF(x + 77, bottom - 20))
        label = QRectF(x - 72, bottom - 218, 144, 39)
        painter.setPen(QPen(QColor("#FFF3CD"), 2))
        painter.setBrush(color.darker(125))
        painter.drawRoundedRect(label, 15, 15)
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(self._font(14, bold=True))
        painter.drawText(label, Qt.AlignmentFlag.AlignCenter, f"{self.players[player - 1]['name'].upper()} · {name.upper()}")

    def _bear_sparkles(self, painter: QPainter, x: float, y: float, accent: str) -> None:
        now = time.monotonic()
        for index in range(7):
            angle = index * math.tau / 7 + now * 1.7
            distance = 48 + 14 * math.sin(now * 4 + index)
            px = x + math.cos(angle) * distance
            py = y + math.sin(angle) * distance
            color = QColor(accent if index % 2 else "#FFF4BB")
            painter.setPen(QPen(color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(px - 6, py), QPointF(px + 6, py))
            painter.drawLine(QPointF(px, py - 6), QPointF(px, py + 6))

    def _team_play(self, painter: QPainter) -> None:
        if self.team is None:
            return
        info = TEAM_GAMES[self.team.kind]
        self._title(painter, QRectF(275, 10, 730, 46), info['title'], 30)
        self._button(painter, QRectF(1140, 16, 124, 42), "Pause", ("pause",), fill="#314E79")
        self._panel(painter, QRectF(270, 65, 740, 130), 20)
        painter.setPen(GOLD)
        painter.setFont(self._font(15, bold=True))
        painter.drawText(QRectF(290, 70, 700, 24), Qt.AlignmentFlag.AlignCenter,
                         f"ROUND {self.team.level} OF 12  ·  {info['prompt']}")
        if not self.bear_calibrated:
            message = "THREE FRIENDS: STEP INTO THE CAMERA!"
            urdu = "تینوں بچے کیمرے کے سامنے آئیں"
            color = QColor("#FFF7E0")
        elif self.team.animation:
            message = "Wonderful! The team is helping!"
            urdu = "شاباش! سب مل کر کھیلیں"
            color = QColor("#FFF7E0")
        elif self.team.finished:
            message = "You did it together!"
            urdu = "شاباش! سب نے مل کر کیا"
            color = QColor("#FFF7E0")
        else:
            player = self.team.current_player
            color_name, hex_color, _ = PLAYERS[player]
            child = self.players[player - 1]
            message = f"{child['name'].upper()}  ·  {color_name.upper()}: RAISE AN ARM!"
            urdu = f"{child['urdu'] or URDU_COLORS[player]}  ·  اپنا ہاتھ اوپر کریں"
            color = QColor(hex_color).lighter(155)
        painter.setPen(color)
        painter.setFont(self._font(25, bold=True))
        painter.drawText(QRectF(290, 95, 700, 38), Qt.AlignmentFlag.AlignCenter, message)
        painter.setPen(QColor("#FFF7E0"))
        painter.setFont(self._font(18, bold=True))
        painter.drawText(QRectF(290, 130, 700, 28), Qt.AlignmentFlag.AlignCenter, urdu)
        painter.setPen(GOLD)
        painter.setFont(self._font(14, bold=True))
        stars = '★' * self.team.completed + '☆' * (3 - self.team.completed)
        painter.drawText(QRectF(290, 165, 700, 22), Qt.AlignmentFlag.AlignCenter,
                         f"{stars}   TEAM STARS / ٹیم کے ستارے")
        self._team_art(painter)
        self._panel(painter, QRectF(16, 568, 980, 42), 14)
        painter.setPen(QColor("#FFF8E8"))
        painter.setFont(self._font(16, bold=True))
        text = "Take turns. Raise one arm when your name and color are shown."
        if self.wait_for_arms_down and self.bodies and not self.celebrating:
            text = "Everyone lower your arms first. Then take turns helping together."
        painter.drawText(QRectF(28, 568, 956, 42), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        self._team_cards(painter, self.team.order, self.team.completed, self.team.current_player, bool(self.team.animation))
        self._camera_card(painter, QRectF(1008, 508, 256, 196))
        if self.celebrating:
            self._overlay_card(painter, "Wonderful! You did it together!\nشاباش!", win=True)
        elif self.paused:
            text = {"tracking": "Step back into the camera. Press P to use keys.",
                    "arms": "Paused. Lower both arms to continue."}.get(self.pause_reason, "Paused.")
            self._overlay_card(painter, text, win=False)

    def _team_art(self, painter: QPainter) -> None:
        if self.team is None:
            return
        kind = self.team.kind
        if kind == 'rainbow':
            colors = ('#FA6962', '#FFA64A', '#FFE572', '#76D77C', '#60BCF1', '#B79BEA')
            for index in range(self.team.completed * 2):
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(colors[index]), 15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawArc(QRectF(210 + index * 17, 200 + index * 17, 700 - index * 34, 520 - index * 34), 0, 180 * 16)
        elif kind == 'garden':
            for index in range(3):
                x = 300 + index * 240
                self._flower(painter, x, 490, index < self.team.completed, QColor(PLAYERS[self.team.order[index]][1]))
        elif kind == 'dragon':
            for index in range(3):
                x = 275 + index * 220 if index >= self.team.completed else 840 + index * 50
                y = 430 if index >= self.team.completed else 410
                if index == self.team.completed - 1 and self.team.animation:
                    progress = 1.0 - self.team.animation
                    start = 275 + index * 220
                    x = start + (840 + index * 50 - start) * progress
                    y = 430 - 20 * progress - 65 * math.sin(math.pi * progress)
                self._fruit(painter, x, y, index)
        elif kind == 'castle':
            for index, x in enumerate((402, 645, 888)):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 226, 110, 100) if index < self.team.completed else QColor(22, 28, 41, 155))
                painter.drawEllipse(QPointF(x, 360), 62, 70)
                if index < self.team.completed:
                    self._bear_sparkles(painter, x, 350, '#FFE789')
        elif kind == 'music':
            for index, x in enumerate((300, 540, 780)):
                color = QColor(PLAYERS[self.team.order[index]][1])
                painter.setPen(QPen(QColor('#FFF5D1'), 4))
                painter.setBrush(color if index < self.team.completed else color.darker(180))
                painter.drawEllipse(QPointF(x, 395), 67, 67)
                painter.setPen(QColor('#FFFFFF'))
                painter.setFont(self._font(66, bold=True))
                painter.drawText(QRectF(x - 65, 335, 130, 120), Qt.AlignmentFlag.AlignCenter, '♪')
                if index < self.team.completed:
                    self._bear_sparkles(painter, x, 360, '#FFE789')

    def _arabic_live_play(self, painter: QPainter) -> None:
        state = self.arabic_state or ArabicTutorState([]).snapshot()
        self._title(painter, QRectF(250, 10, 780, 50), 'Arabic Pictures  ·  عربی الفاظ', 31)
        self._panel(painter, QRectF(180, 75, 920, 110), 22)
        labels = {
            'connecting': ('Connecting to the voice tutor…', 'استاد کی آواز تیار ہو رہی ہے'),
            'speaking': ('The tutor is speaking', 'استاد بول رہی ہیں'),
            'listening': ('Listening — just speak naturally', 'ہم سن رہے ہیں، بولیں'),
            'missing_key': ('OpenAI API key needed. Set it and restart the game.', 'اوپن اے آئی کی چابی درکار ہے'),
            'microphone_error': ('Microphone unavailable. Check Ubuntu sound settings.', 'مائیک دستیاب نہیں ہے'),
            'audio_error': ('Audio playback unavailable. Check Ubuntu sound settings.', 'آواز دستیاب نہیں ہے'),
            'service_error': ('Connection lost. Check the internet and restart the tutor.', 'کنکشن ختم ہو گیا، دوبارہ شروع کریں'),
            'camera_error': ('Could not release the camera. Press Esc and try again.', 'کیمرہ بند نہیں ہو سکا'),
        }
        title, urdu = labels.get(self.arabic_status, ('Getting ready…', 'تیار ہو رہے ہیں'))
        painter.setPen(QColor('#A9F4C1') if self.arabic_status == 'listening' else GOLD)
        painter.setFont(self._font(24, bold=True))
        painter.drawText(QRectF(200, 88, 880, 38), Qt.AlignmentFlag.AlignCenter, title)
        painter.setPen(QColor('#FFF8E8'))
        painter.setFont(self._font(20, bold=True))
        painter.drawText(QRectF(200, 128, 880, 35), Qt.AlignmentFlag.AlignCenter, urdu)
        self._panel(painter, QRectF(180, 205, 920, 370), 26)
        if state['stage'] == 'names':
            painter.setPen(QColor('#FFFFFF'))
            painter.setFont(self._font(34, bold=True))
            painter.drawText(QRectF(220, 260, 840, 70), Qt.AlignmentFlag.AlignCenter, 'ہمارے ساتھ آج کون کون ہے؟')
            painter.setPen(GOLD)
            painter.setFont(self._font(25, bold=True))
            painter.drawText(QRectF(220, 360, 840, 65), Qt.AlignmentFlag.AlignCenter, 'اپنے نام بتائیے')
            painter.setPen(QColor('#FFF8E8'))
            painter.setFont(self._font(18))
            painter.drawText(QRectF(230, 445, 820, 45), Qt.AlignmentFlag.AlignCenter, 'ایک، دو یا تین بچے مل کر کھیل سکتے ہیں')
        elif state['stage'] == 'choose':
            painter.setPen(QColor('#FFFFFF'))
            painter.setFont(self._font(36, bold=True))
            painter.drawText(QRectF(220, 245, 840, 60), Qt.AlignmentFlag.AlignCenter, 'آسان یا مشکل؟')
            painter.setPen(GOLD)
            painter.setFont(self._font(27, bold=True))
            painter.drawText(QRectF(220, 330, 840, 60), Qt.AlignmentFlag.AlignCenter, 'Say “Asaan” or “Mushkil”')
            painter.setPen(QColor('#FFF8E8'))
            painter.setFont(self._font(19))
            painter.drawText(QRectF(230, 425, 820, 60), self._wrap(), 'Easy: say the word.  ·  Hard: say the whole Arabic phrase.')
        elif state['stage'] in ('playing', 'awaiting_advance'):
            self._sprite(painter, f"vocab_{state['picture']}", 410, 390, 235)
            painter.setPen(QColor('#FFFFFF'))
            painter.setFont(self._font(48, bold=True))
            painter.drawText(QRectF(570, 235, 440, 75), Qt.AlignmentFlag.AlignCenter, state['question'])
            painter.setFont(self._font(20, bold=True))
            painter.drawText(QRectF(570, 310, 440, 35), Qt.AlignmentFlag.AlignCenter,
                             f"{state['child']}، بتائیں یہ کیا ہے؟")
            painter.setPen(GOLD)
            painter.setFont(self._font(21, bold=True))
            instruction = 'عربی میں لفظ بتائیں' if state['difficulty'] == 'easy' else 'عربی میں مکمل جملہ بولیں'
            painter.drawText(QRectF(570, 385, 440, 50), Qt.AlignmentFlag.AlignCenter, instruction)
        else:
            painter.setPen(GOLD)
            painter.setFont(self._font(36, bold=True))
            painter.drawText(QRectF(220, 285, 840, 65), Qt.AlignmentFlag.AlignCenter, 'أَحْسَنْتُمْ!  ·  Wonderful together!')
            painter.setPen(QColor('#FFFFFF'))
            painter.setFont(self._font(22, bold=True))
            painter.drawText(QRectF(220, 385, 840, 70), self._wrap(), 'Say “again” to play again, or “home” to finish.')
        self._panel(painter, QRectF(180, 590, 920, 80), 16)
        painter.setPen(QColor('#FFF8E8'))
        painter.setFont(self._font(16, bold=True))
        if self.arabic_transcript:
            painter.drawText(QRectF(200, 594, 880, 38), self._wrap(), self.arabic_transcript)
        painter.setFont(self._font(12))
        painter.setPen(GOLD)
        painter.drawText(QRectF(200, 640, 880, 22), Qt.AlignmentFlag.AlignCenter,
                         'Live voice uses OpenAI while this activity is open  ·  Say “home” to leave')

    def _voice_play(self, painter: QPainter) -> None:
        game = self.voice_round
        if game is None:
            return
        info = VOICE_GAMES[game.kind]
        self._title(painter, QRectF(275, 10, 730, 46), info['title'], 30)
        self._button(painter, QRectF(1140, 16, 124, 42), "Pause", ("pause",), fill="#314E79")
        self._panel(painter, QRectF(270, 65, 740, 130), 20)
        painter.setPen(GOLD)
        painter.setFont(self._font(15, bold=True))
        painter.drawText(QRectF(290, 70, 700, 24), Qt.AlignmentFlag.AlignCenter,
                         f"LEVEL {game.level} OF {info['levels']}  ·  {info['urdu']}")
        if self.voice_status == 'loading':
            message, urdu = 'GETTING THE MICROPHONE READY...', 'مائیک تیار ہو رہا ہے'
        elif self.voice_status == 'unavailable':
            message, urdu = 'MICROPHONE OR SPEECH MODEL UNAVAILABLE', 'مائیک دستیاب نہیں ہے'
        elif self.voice_status == 'listening':
            message, urdu = 'LISTENING... SPEAK NOW!', 'اب بولیں، ہم سن رہے ہیں'
        elif self.voice_status == 'thinking':
            message, urdu = 'LISTENING FINISHED. ONE MOMENT...', 'ایک لمحہ...'
        elif not self.bear_calibrated and not self.celebrating:
            message, urdu = 'THREE FRIENDS: STEP INTO THE CAMERA!', 'تینوں بچے کیمرے کے سامنے آئیں'
        elif self.celebrating:
            message, urdu = 'WONDERFUL! TOGETHER!', 'شاباش! سب نے مل کر کیا'
        elif self.voice_feedback:
            message, urdu = self.voice_feedback, 'ہم سب مل کر سیکھ رہے ہیں'
        else:
            child = self.players[game.current_player - 1]
            message = f"{child['name'].upper()}: RAISE AN ARM TO SPEAK!"
            urdu = f"{child['urdu'] or child['name']}  ·  ہاتھ اٹھائیں، پھر بولیں"
        painter.setPen(QColor('#FFE797' if self.voice_status != 'listening' else '#A9F4C1'))
        painter.setFont(self._font(23, bold=True))
        painter.drawText(QRectF(290, 95, 700, 38), Qt.AlignmentFlag.AlignCenter, message)
        painter.setPen(QColor('#FFF7E0'))
        painter.setFont(self._font(18, bold=True))
        painter.drawText(QRectF(290, 130, 700, 28), Qt.AlignmentFlag.AlignCenter, urdu)
        painter.setPen(GOLD)
        painter.setFont(self._font(14, bold=True))
        stars = '★' * game.turn + '☆' * (3 - game.turn)
        mic = 'MIC ON · LISTENING' if self.voice_status == 'listening' else 'MIC OFF'
        painter.drawText(QRectF(290, 165, 700, 22), Qt.AlignmentFlag.AlignCenter,
                         f"{stars}   TEAM STARS  ·  {mic}")
        self._voice_art(painter, game)
        can_listen = self.voice_status == 'ready' and not self.voice_busy and not self.paused and not self.celebrating
        self._button(painter, QRectF(1020, 220, 244, 60), 'Speak / بولیں', ('voice_listen',) if can_listen else None,
                     fill='#3D8F68' if can_listen else '#35485B')
        self._button(painter, QRectF(1020, 294, 244, 55), 'Hear a hint / سنیں', ('voice_hint',) if not self.voice_busy else None,
                     fill='#526590')
        self._panel(painter, QRectF(16, 568, 980, 42), 14)
        painter.setPen(QColor('#FFF8E8'))
        painter.setFont(self._font(15, bold=True))
        line = 'Take turns. Raise an arm, then speak when the screen says LISTENING.'
        if self.voice_status == 'unavailable':
            line = 'Microphone or local speech model unavailable. Choose another game and check setup.'
        painter.drawText(QRectF(28, 568, 956, 42), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, line)
        self._team_cards(painter, (1, 2, 3), game.turn, game.current_player, self.voice_busy)
        self._camera_card(painter, QRectF(1008, 508, 256, 196))
        if self.celebrating:
            if game.kind == 'story' and len(game.answers) == 3:
                story = f"{game.answers[0]} met {game.answers[1]}. Together they found {game.answers[2]}!"
                self._overlay_card(painter, f"Our story: {story}", win=True)
            else:
                self._overlay_card(painter, "Wonderful! You did it together!\nشاباش!", win=True)
        elif self.paused:
            text = {"tracking": "Step back into the camera. Press P to use keys.",
                    "arms": "Paused. Lower both arms to continue."}.get(self.pause_reason, "Paused.")
            self._overlay_card(painter, text, win=False)

    def _voice_art(self, painter: QPainter, game: VoiceRound) -> None:
        self._panel(painter, QRectF(170, 210, 780, 230 if game.kind != 'arabic' else 325), 24)
        painter.setPen(QColor('#FFF8E8'))
        if game.kind == 'arabic':
            item = self.voice_last_item or game.item
            self._sprite(painter, f'vocab_{item.picture}', 345, 363, 205)
            painter.setFont(self._font(48, bold=True))
            painter.drawText(QRectF(500, 230, 400, 75), Qt.AlignmentFlag.AlignCenter, 'ما هذا؟')
            painter.setFont(self._font(18, bold=True))
            painter.drawText(QRectF(500, 304, 400, 35), Qt.AlignmentFlag.AlignCenter, 'Mā hādhā?  ·  What is this?')
            painter.setPen(GOLD)
            painter.setFont(self._font(31, bold=True))
            painter.drawText(QRectF(500, 350, 400, 55), Qt.AlignmentFlag.AlignCenter, f'هذا {item.word}')
            painter.setPen(QColor('#FFF8E8'))
            painter.setFont(self._font(19, bold=True))
            painter.drawText(QRectF(490, 414, 420, 42), Qt.AlignmentFlag.AlignCenter, f'Hādhā {item.roman}  ·  {item.meaning}')
            painter.setFont(self._font(15))
            painter.drawText(QRectF(210, 485, 700, 30), Qt.AlignmentFlag.AlignCenter, 'Hear a hint, then say the Arabic word or the whole phrase.')
            return
        if game.kind in ('word_garden', 'places'):
            painter.setPen(QPen(QColor('#FFF1BE'), 4))
            painter.setBrush(QColor('#6B58A2'))
            painter.drawEllipse(QPointF(310, 320), 78, 78)
            painter.setPen(QColor('#FFFFFF'))
            painter.setFont(self._font(88, bold=True))
            painter.drawText(QRectF(235, 240, 150, 150), Qt.AlignmentFlag.AlignCenter, game.letter)
            painter.setFont(self._font(22, bold=True))
            title = 'Say an English word that starts with:' if game.kind == 'word_garden' else 'Name a city or country starting with:'
            painter.drawText(QRectF(415, 236, 480, 52), self._wrap(), title)
            examples = WORD_HINTS[game.letter] if game.kind == 'word_garden' else PLACES[game.letter][:3]
            painter.setPen(GOLD)
            painter.setFont(self._font(21, bold=True))
            painter.drawText(QRectF(410, 309, 490, 55), self._wrap(), '  ·  '.join(word.title() for word in examples))
        elif game.kind == 'animals':
            painter.setFont(self._font(27, bold=True))
            painter.drawText(QRectF(205, 230, 710, 60), self._wrap(), 'Say one of these animal names!')
            painter.setPen(GOLD)
            painter.setFont(self._font(21, bold=True))
            painter.drawText(QRectF(205, 305, 710, 55), self._wrap(), 'Cat  ·  Bird  ·  Rabbit')
        elif game.kind == 'village':
            painter.setFont(self._font(27, bold=True))
            painter.drawText(QRectF(205, 235, 710, 65), self._wrap(), 'Say any English word to build a house!')
            painter.setPen(GOLD)
            painter.setFont(self._font(20, bold=True))
            painter.drawText(QRectF(205, 315, 710, 45), self._wrap(), 'A house for every friend — together!')
        else:
            painter.setFont(self._font(27, bold=True))
            painter.drawText(QRectF(205, 230, 710, 60), self._wrap(), 'Say a word for our story!')
            painter.setPen(GOLD)
            painter.setFont(self._font(20, bold=True))
            answer = '  ·  '.join(game.answers) if game.answers else 'Together we will make a little story.'
            painter.drawText(QRectF(205, 305, 710, 55), self._wrap(), answer)
        for index in range(3):
            x = 300 + index * 240
            done = index < game.turn
            if game.kind == 'village' and done:
                self._sprite(painter, 'vocab_house', x, 535, 135, anchor=1.0)
            elif game.kind == 'animals' and done:
                animal = game.answers[index]
                asset = 'animal_rabbit' if animal == 'rabbit' else 'animal_bird' if animal in ('bird', 'duck') else 'animal_cat'
                self._sprite(painter, asset, x, 535, 135, anchor=1.0)
            elif game.kind in ('word_garden', 'places'):
                self._flower(painter, x, 535, done, QColor(PLAYERS[index + 1][1]))
            elif done:
                self._bear_sparkles(painter, x, 480, '#FFE789')

    def _flower(self, painter: QPainter, x: float, bottom: float, bloomed: bool, color: QColor) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#76523A'))
        painter.drawEllipse(QRectF(x - 54, bottom - 10, 108, 24))
        if not bloomed:
            painter.setBrush(QColor('#B7E69E'))
            painter.drawEllipse(QRectF(x - 12, bottom - 27, 24, 18))
            return
        painter.setPen(QPen(QColor('#338655'), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(x, bottom - 3), QPointF(x, bottom - 100))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#55B96C'))
        painter.drawEllipse(QRectF(x - 40, bottom - 70, 43, 22))
        painter.drawEllipse(QRectF(x, bottom - 88, 43, 22))
        painter.setBrush(color.lighter(140))
        for index in range(6):
            angle = index * math.tau / 6
            painter.drawEllipse(QPointF(x + math.cos(angle) * 31, bottom - 120 + math.sin(angle) * 31), 23, 23)
        painter.setBrush(QColor('#FFE878'))
        painter.drawEllipse(QPointF(x, bottom - 120), 22, 22)

    def _fruit(self, painter: QPainter, x: float, y: float, index: int) -> None:
        color = QColor(('#FF7474', '#FFD05F', '#F29255')[index])
        painter.setPen(QPen(QColor('#FFF0CB'), 3))
        painter.setBrush(color)
        painter.drawEllipse(QPointF(x, y), 37, 35)
        painter.setPen(QPen(QColor('#745331'), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(x, y - 31), QPointF(x + 2, y - 45))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#64B973'))
        painter.drawEllipse(QRectF(x + 2, y - 47, 24, 12))

    def _bear_cards(self, painter: QPainter) -> None:
        if self.bear is None:
            return
        level = BEAR_LEVELS[self.bear.level - 1]
        self._team_cards(painter, level.order, self.bear.gates_open, self.bear.current_player, self.bear.moving)

    def _team_cards(self, painter: QPainter, order: tuple[int, int, int], completed: int,
                    current_player: int | None, moving: bool) -> None:
        for player in (1, 2, 3):
            name, color, badge = PLAYERS[player]
            rect = QRectF(16 + (player - 1) * 328, 620, 316, 84)
            self._panel(painter, rect, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(rect.left() + 30, rect.center().y()), 19, 19)
            self._badge_mark(painter, badge, rect.left() + 30, rect.center().y(), 10)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(self._font(17, bold=True))
            painter.drawText(QRectF(rect.left() + 60, rect.top() + 9, 240, 26),
                             Qt.AlignmentFlag.AlignVCenter, f"{self.players[player - 1]['name'].upper()}  ·  {name.upper()}")
            gate_index = order.index(player)
            if gate_index < completed:
                state = "TEAM STAR!"
                state_color = QColor("#A8E8AA")
            elif not self.bear_calibrated:
                state = "FIND 3 FRIENDS IN CAMERA"
                state_color = QColor("#FFE18A")
            elif self.mode == 'voice' and moving and player == current_player:
                state = 'SPEAK NOW!'
                state_color = QColor('#A8E8AA')
            elif not moving and player == current_player:
                state = "YOUR TURN — RAISE AN ARM!"
                state_color = QColor("#FFE18A")
            else:
                state = "GET READY"
                state_color = QColor("#CBD6E5")
            painter.setPen(state_color)
            painter.setFont(self._font(14, bold=True))
            painter.drawText(QRectF(rect.left() + 60, rect.top() + 40, 240, 26),
                             Qt.AlignmentFlag.AlignVCenter, state)

    def _play(self, painter: QPainter) -> None:
        assert self.level is not None
        for stone in self.level.blockers:
            self._stone(painter, stone)
        self._beam(painter)
        self._lantern(painter)
        for mirror in self.level.mirrors:
            self._mirror(painter, mirror)
        self._chest(painter)
        if self.beam.solved and self.hold < 1:
            self._ring(painter, self.level.chest[0], self.level.chest[1], self.hold)
        self._title(painter, QRectF(300, 10, 680, 42), "Magic Mirror Maze", 30)
        painter.setFont(self._font(16, bold=True))
        painter.setPen(GOLD)
        painter.drawText(
            QRectF(300, 50, 680, 24),
            Qt.AlignmentFlag.AlignCenter,
            f"Level {self.level.number}  ·  {self.level.name}",
        )
        self._button(painter, QRectF(1036, 16, 110, 42), "Hint", ("hint",), fill="#314E79")
        self._button(painter, QRectF(1154, 16, 110, 42), "Pause", ("pause",), fill="#314E79")
        self._instruction(painter)
        self._cards(painter)
        self._camera_card(painter, QRectF(1008, 508, 256, 196))
        if self.celebrating:
            self._overlay_card(painter, "The chest is open. You did it together!", win=True)
        elif self.paused:
            text = {
                "tracking": "Step back into the camera. Press P to use keys.",
                "arms": "Paused. Lower both arms to continue.",
            }.get(self.pause_reason, "Paused.")
            self._overlay_card(painter, text, win=False)

    def _instruction(self, painter: QPainter) -> None:
        assert self.level is not None
        if self.hint_step:
            text = self.level.hints[self.hint_step - 1]
        elif self.camera_status == "missing":
            text = "No camera. Keys A D, F H, and J L still turn the mirrors."
        elif self.beam.looping:
            text = "The light is going in a circle. Turn a mirror to let it out."
        elif self.beam.blocked:
            text = "The stones stopped the light. Try another face."
        elif self.beam.reached_chest and not self.beam.solved:
            text = "The chest needs light from all three mirrors."
        else:
            text = "Raise one arm to turn your mirror. Left and right are your own arms."
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(12, 22, 40, 190))
        painter.drawRoundedRect(QRectF(16, 568, 980, 42), 14, 14)
        painter.setPen(QColor("#F7F1DE"))
        painter.setFont(self._font(16, bold=True))
        painter.drawText(QRectF(28, 568, 956, 42), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

    def _cards(self, painter: QPainter) -> None:
        for index, mirror in enumerate(self.level.mirrors if self.level else []):
            rect = QRectF(16 + index * 328, 620, 316, 84)
            self._panel(painter, rect, 16)
            painter.setBrush(QColor(mirror.color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(rect.left() + 28, rect.center().y()), 16, 16)
            self._badge_mark(painter, mirror.badge, rect.left() + 28, rect.center().y(), 9)
            if mirror.player in self.beam.hit:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#FFF1A8"), 3))
                painter.drawEllipse(QPointF(rect.left() + 28, rect.center().y()), 20, 20)
            painter.setPen(QColor("#F4F7FB"))
            painter.setFont(self._font(16, bold=True))
            painter.drawText(
                QRectF(rect.left() + 52, rect.top() + 8, 150, 28),
                Qt.AlignmentFlag.AlignVCenter,
                f"Player {mirror.player}",
            )
            left_key, right_key = KEY_LABELS[mirror.player]
            flashing = self.flash.get(mirror.player)
            active = flashing is not None and flashing[0] > time.monotonic()
            self._arrow(painter, QRectF(rect.right() - 118, rect.top() + 22, 48, 42), left_key, active and not flashing[1])
            self._arrow(painter, QRectF(rect.right() - 62, rect.top() + 22, 48, 42), right_key, active and flashing[1])

    def _arrow(self, painter: QPainter, rect: QRectF, letter: str, hot: bool) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#F0C14A") if hot else QColor("#1E3350"))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(INK if hot else GOLD)
        painter.setFont(self._font(16, bold=True))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, letter)

    def _camera_card(self, painter: QPainter, rect: QRectF) -> None:
        self._panel(painter, rect, 16)
        picture = rect.adjusted(10, 28, -10, -28)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#081018"))
        painter.drawRoundedRect(picture, 8, 8)
        if self.preview is not None:
            painter.drawImage(picture, self.preview)
        painter.setPen(GOLD)
        painter.setFont(self._font(13, bold=True))
        camera_on = self.camera_status in ("ok", "keyboard") and self.preview is not None
        label = "Camera on" if camera_on else "Camera off · keys work"
        painter.drawText(QRectF(rect.left(), rect.top() + 4, rect.width(), 22), Qt.AlignmentFlag.AlignCenter, label)
        count = len(self.bodies)
        if camera_on and count == 0:
            tracking_label = "0/3 tracked · stand apart"
        elif self.mode in ("play", "bear", "team", "voice") and not self.celebrating and count and self.wait_for_arms_down:
            tracking_label = f"{count}/3 tracked · lower arms"
        else:
            tracking_label = f"{count}/3 tracked"
        painter.drawText(
            QRectF(rect.left(), rect.bottom() - 24, rect.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            tracking_label,
        )

    def _overlay_card(self, painter: QPainter, text: str, win: bool) -> None:
        self._shade(painter, 90)
        card = QRectF(250, 150, 760, 250)
        self._panel(painter, card, 24)
        painter.setPen(QColor("#FFF6D8"))
        painter.setFont(self._font(26, bold=True))
        painter.drawText(QRectF(270, 170, 720, 80), self._wrap(), text)
        if win:
            painter.setFont(self._font(16, bold=True))
            painter.setPen(GOLD)
            has_next = (self.mode == "bear" and self.bear is not None and self.bear.level < len(BEAR_LEVELS)) or (
                self.mode == "play" and self.level is not None and self.level.number < 6
            ) or (self.mode == 'team' and self.team is not None and self.team.level < activity_info(self.team.kind)['levels']) or (
                self.mode == 'voice' and self.voice_round is not None and self.voice_round.level < activity_info(self.voice_round.kind)['levels'])
            destination = "Next" if has_next else "Home"
            instruction = "Lower an arm to get ready."
            if self.next_gesture.ready:
                instruction = f"Raise one arm for 2 seconds: {destination}"
            if self.next_gesture.progress:
                instruction = f"Keep your arm up... {int(self.next_gesture.progress * 100)}%"
            painter.drawText(QRectF(270, 243, 720, 30), Qt.AlignmentFlag.AlignCenter, instruction)
            if has_next:
                self._button(painter, QRectF(290, 280, 210, 52), "Next", ("next",), fill="#F0C14A")
            else:
                self._button(painter, QRectF(290, 280, 210, 52), "Home", ("home",), fill="#F0C14A")
            self._button(painter, QRectF(520, 280, 210, 52), "Replay", ("restart",), fill="#314E79")
            self._button(painter, QRectF(750, 280, 210, 52), "Home", ("home",), fill="#314E79")
        else:
            if self.mode in ("bear", "team", "voice"):
                self._button(painter, QRectF(290, 280, 210, 52), "Resume", ("resume",), fill="#F0C14A")
                self._button(painter, QRectF(520, 280, 210, 52), "Restart", ("restart",), fill="#314E79")
                self._button(painter, QRectF(750, 280, 210, 52), "Home", ("home",), fill="#314E79")
            else:
                self._button(painter, QRectF(290, 280, 160, 52), "Resume", ("resume",), fill="#F0C14A")
                self._button(painter, QRectF(466, 280, 150, 52), "Hint", ("hint",), fill="#314E79")
                self._button(painter, QRectF(632, 280, 170, 52), "Restart", ("restart",), fill="#314E79")
                self._button(painter, QRectF(818, 280, 150, 52), "Home", ("home",), fill="#314E79")

    def _beam(self, painter: QPainter) -> None:
        if len(self.beam.points) < 2:
            return
        path = QPainterPath()
        path.moveTo(*self.beam.points[0])
        for point in self.beam.points[1:]:
            path.lineTo(*point)
        glow = QColor("#FFE08A")
        glow.setAlpha(120)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(glow, 48, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(QColor("#FFF6C4"), 22, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)

    def _lantern(self, painter: QPainter) -> None:
        assert self.level is not None
        x, y = self.level.lantern
        if not self._sprite(painter, "lantern", x, y, 120):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#C9A227"))
            painter.drawRoundedRect(QRectF(x - 24, y - 36, 48, 70), 8, 8)

    def _chest(self, painter: QPainter) -> None:
        assert self.level is not None
        x, y = self.level.chest
        name = "chest_open" if self.hold >= 1 else "chest_closed"
        if not self._sprite(painter, name, x, y, 130):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F0C14A") if self.hold >= 1 else QColor("#C9842A"))
            painter.drawRoundedRect(QRectF(x - 50, y - 36, 100, 72), 12, 12)

    def _mirror(self, painter: QPainter, mirror: Mirror) -> None:
        names = {1: "mirror_blue", 2: "mirror_green", 3: "mirror_orange"}
        if not self._sprite(painter, names[mirror.player], mirror.x, mirror.y, 124, anchor=0.36):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(mirror.color))
            painter.drawEllipse(QPointF(mirror.x, mirror.y + 28), 40, 14)
            painter.setBrush(QColor("#F4E2B0"))
            painter.drawRoundedRect(QRectF(mirror.x - 28, mirror.y - 16, 56, 44), 8, 8)
        face = self.face.get(mirror.player, float(mirror.angle))
        dx = 32
        dy = -30 + face * 60
        painter.setPen(QPen(QColor("#1A2433"), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(mirror.x - dx, mirror.y - dy), QPointF(mirror.x + dx, mirror.y + dy))
        painter.setPen(QPen(QColor("#F7FBFF"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(mirror.x - dx, mirror.y - dy), QPointF(mirror.x + dx, mirror.y + dy))
        if mirror.player in self.beam.hit:
            painter.setPen(QPen(QColor("#FFF1A8"), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(mirror.x, mirror.y), 46, 46)
        self._number(painter, mirror)

    def _number(self, painter: QPainter, mirror: Mirror) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(mirror.color))
        painter.drawEllipse(QPointF(mirror.x, mirror.y + 62), 14, 14)
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(self._font(14, bold=True))
        painter.drawText(QRectF(mirror.x - 14, mirror.y + 48, 28, 28), Qt.AlignmentFlag.AlignCenter, str(mirror.player))

    def _stone(self, painter: QPainter, stone: Blocker) -> None:
        rect = QRectF(stone.x, stone.y, stone.w, stone.h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#5C6B73"))
        painter.drawRoundedRect(rect, 18, 18)
        painter.setBrush(QColor("#7D8C86"))
        painter.drawRoundedRect(rect.adjusted(16, 10, -30, -18), 12, 12)
        painter.setBrush(QColor("#3E8F55"))
        painter.drawEllipse(QPointF(rect.center().x(), rect.top() + 16), 22, 10)

    def _sprite(self, painter: QPainter, name: str, x: float, y: float, height: float, anchor: float = 0.5) -> bool:
        pixmap = self.art.get(name)
        if pixmap is None and name.startswith('vocab_') and Path(name).name == name:
            pixmap = self.vocab_art.get(name)
            if pixmap is None:
                path = _art_dir() / f'{name}.png'
                if path.is_file():
                    pixmap = QPixmap(str(path))
                    if not pixmap.isNull():
                        self.vocab_art[name] = pixmap
                        if len(self.vocab_art) > 8:
                            self.vocab_art.popitem(last=False)
            elif pixmap is not None:
                self.vocab_art.move_to_end(name)
        if pixmap is None or pixmap.isNull():
            return False
        width = pixmap.width() * height / pixmap.height()
        top = y - height * anchor
        target = QRectF(x - width / 2, top, width, height)
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        return True

    def _ring(self, painter: QPainter, x: float, y: float, amount: float) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#FFF1A8"), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        rect = QRectF(x - 78, y - 78, 156, 156)
        painter.drawArc(rect, 90 * 16, int(-360 * 16 * amount))

    def _shade(self, painter: QPainter, alpha: int) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(6, 10, 20, alpha))
        painter.drawRect(QRectF(0, 0, VIEW_W, VIEW_H))

    def _panel(self, painter: QPainter, rect: QRectF, radius: float) -> None:
        painter.setPen(QPen(QColor("#E3B341"), 3))
        painter.setBrush(QColor(12, 24, 46, 236))
        painter.drawRoundedRect(rect, radius, radius)

    def _title(self, painter: QPainter, rect: QRectF, text: str, size: int) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(18, 16, 48, 170))
        painter.drawRoundedRect(rect.adjusted(-10, 0, 10, 0), 18, 18)
        painter.setPen(GOLD)
        painter.setFont(self._font(size, bold=True))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _button(self, painter: QPainter, rect: QRectF, text: str, action: tuple | None, fill: str = "#314E79") -> None:
        self.hotspots.append((rect, action))
        painter.setPen(QPen(QColor("#F0D78C"), 2))
        color = QColor(fill)
        if action is None:
            color.setAlpha(140)
        painter.setBrush(color)
        painter.drawRoundedRect(rect, 14, 14)
        painter.setPen(INK if fill == "#F0C14A" else QColor("#F7F1DE"))
        painter.setFont(self._font(16, bold=True))
        painter.drawText(rect, self._wrap(), text)

    def _badge_mark(self, painter: QPainter, kind: str, x: float, y: float, radius: float) -> None:
        painter.setPen(QPen(QColor("#FFF6D8"), 2))
        painter.setBrush(QColor("#FFF6D8"))
        if kind == "leaf":
            path = QPainterPath()
            path.moveTo(x, y - radius)
            path.quadTo(x + radius, y, x, y + radius)
            path.quadTo(x - radius * 0.2, y, x, y - radius)
            painter.drawPath(path)
            return
        if kind == "sun":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(x, y), radius * 0.45, radius * 0.45)
            for step in range(8):
                angle = step * math.pi / 4
                painter.drawLine(
                    QPointF(x + math.cos(angle) * radius * 0.6, y + math.sin(angle) * radius * 0.6),
                    QPointF(x + math.cos(angle) * radius, y + math.sin(angle) * radius),
                )
            return
        path = QPainterPath()
        for step in range(10):
            angle = -math.pi / 2 + step * math.pi / 5
            dist = radius if step % 2 == 0 else radius * 0.45
            point = QPointF(x + math.cos(angle) * dist, y + math.sin(angle) * dist)
            if step == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        path.closeSubpath()
        painter.drawPath(path)

    def _wrap(self):
        return Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap

    def _font(self, size: int, bold: bool = False) -> QFont:
        font = QFont("Sans Serif", size)
        font.setPixelSize(size)
        font.setBold(bold)
        return font
