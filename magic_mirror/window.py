"""Magic Mirror Maze on one desktop screen."""

from __future__ import annotations

import math
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .board import Beam, Blocker, Level, Mirror, campaign, trace
from .pose_track import PoseWorker
from .progress import load_progress, save_progress

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
    def __init__(self, camera: int | None = 0) -> None:
        super().__init__()
        self.art = _load_art()
        self.cleared = load_progress()
        self.mode = "home"
        self.level: Level | None = None
        self.beam = Beam()
        self.paused = False
        self.pause_reason = ""
        self.hold = 0.0
        self.celebrating = False
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
        if camera is not None and camera >= 0:
            self.camera_status = "starting"
            model = _art_dir().parent / "models" / "pose_landmarker.task"
            self.worker = PoseWorker(camera, model)
            self.worker.bodies_ready.connect(self._on_bodies)
            self.worker.preview_ready.connect(self._on_preview)
            self.worker.status_ready.connect(self._on_status)
            self.worker.start()

    def _tick(self) -> None:
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
        self.level = campaign()[number - 1]
        self.beam = trace(self.level)
        self.mode = "play"
        self.paused = False
        self.pause_reason = ""
        self.hold = 0.0
        self.celebrating = False
        self.hint_step = 0
        self.face = {mirror.player: float(mirror.angle) for mirror in self.level.mirrors}
        self.flash.clear()
        self.raised.clear()
        self.armed.clear()
        self.both_since.clear()
        self.wait_for_arms_down = True
        self.missing_since = None
        self.update()

    def _turn(self, player: int, clockwise: bool) -> None:
        if self.level is None or self.beam.solved or self.paused or self.celebrating:
            return
        for mirror in self.level.mirrors:
            if mirror.player == player:
                mirror.turn(clockwise)
        self.beam = trace(self.level)
        self.flash[player] = (time.monotonic() + 0.45, clockwise)
        self.hold = 0.0

    def _watch_tracking(self) -> None:
        if self.mode != "play" or self.celebrating or not self.had_body:
            return
        if self.bodies or self.camera_status == "starting":
            self.missing_since = None
            return
        now = time.monotonic()
        if self.missing_since is None:
            self.missing_since = now
        elif now - self.missing_since > 1.0 and not self.paused:
            self.paused = True
            self.pause_reason = "tracking"
            self.wait_for_arms_down = True

    def _on_preview(self, image) -> None:
        self.preview = image

    def _on_status(self, status: str) -> None:
        self.camera_status = status
        if status == "missing":
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
                self.paused = False
                self.pause_reason = ""
                self.wait_for_arms_down = True
        arms_up = any(body.left_up or body.right_up for body in self.bodies)
        if self.wait_for_arms_down:
            if arms_up:
                return
            self.wait_for_arms_down = False
            if self.paused and self.pause_reason == "arms":
                self.paused = False
                self.pause_reason = ""
            return
        if self.mode != "play" or self.level is None:
            return
        for index, body in enumerate(self.bodies, start=1):
            if body.left_up and body.right_up:
                self.both_since.setdefault(index, now)
                if now - self.both_since[index] > 1.5 and not self.paused:
                    self.paused = True
                    self.pause_reason = "arms"
                    self.wait_for_arms_down = True
                continue
            self.both_since.pop(index, None)
            self._arm(index, "left", body.left_up, now, clockwise=False)
            self._arm(index, "right", body.right_up, now, clockwise=True)

    def _arm(self, player: int, side: str, up: bool, now: float, clockwise: bool) -> None:
        key = (player, side)
        if not up:
            self.raised.pop(key, None)
            self.armed.discard(key)
            return
        if key in self.armed or self.paused:
            return
        self.raised.setdefault(key, now)
        if now - self.raised[key] >= 0.45:
            self.armed.add(key)
            self._turn(player, clockwise)

    def keyPressEvent(self, event) -> None:
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
            return
        if self.mode == "home":
            self._home_key(key)
            return
        if key == Qt.Key.Key_H:
            self.hint_step = (self.hint_step + 1) % 4
            return
        if self.celebrating:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._after_win()
            elif key == Qt.Key.Key_R and self.level is not None:
                self._begin(self.level.number)
            elif key == Qt.Key.Key_Escape:
                self.mode = "home"
            return
        if self.paused:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_P, Qt.Key.Key_Escape):
                self.paused = False
                self.pause_reason = ""
                self.wait_for_arms_down = True
            elif key == Qt.Key.Key_R and self.level is not None:
                self._begin(self.level.number)
            return
        if key in (Qt.Key.Key_P, Qt.Key.Key_Escape):
            self.paused = True
            self.pause_reason = "key"
            self.wait_for_arms_down = True
            return
        mapped = KEYS.get(key)
        if mapped:
            self._turn(*mapped)
        self.update()

    def _home_key(self, key: int) -> None:
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._begin(self._continue_number())
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
        if kind == "play":
            self._begin(self._continue_number())
        elif kind == "level":
            self._begin(action[1])
        elif kind == "hint":
            self.hint_step = (self.hint_step + 1) % 4
        elif kind == "pause":
            self.paused = True
            self.pause_reason = "key"
            self.wait_for_arms_down = True
        elif kind == "resume":
            self.paused = False
            self.pause_reason = ""
            self.wait_for_arms_down = True
        elif kind == "restart" and self.level is not None:
            self._begin(self.level.number)
        elif kind == "home":
            self.mode = "home"
        elif kind == "next":
            self._after_win()
        self.update()

    def _logical(self, pos) -> tuple[float, float] | None:
        ox, oy, scale = self._view
        if scale <= 0:
            return None
        return (pos.x() - ox) / scale, (pos.y() - oy) / scale

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(1200)
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
            else:
                self._play(painter)
        finally:
            painter.end()

    def _background(self, painter: QPainter) -> None:
        pixmap = self.art.get("courtyard")
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
            "Stand left, middle, and right. Raise your own left or right arm to turn your mirror.",
            "One raise turns it once. Both arms, held up, pause the game.",
            "Keys work even when the camera cannot see anyone.",
        )
        painter.setPen(QColor("#F4F7FB"))
        painter.setFont(self._font(18))
        for index, line in enumerate(lines):
            painter.drawText(QRectF(200, 196 + index * 32, 880, 30), Qt.AlignmentFlag.AlignCenter, line)
        stars = len(self.cleared)
        painter.setPen(GOLD)
        painter.setFont(self._font(18, bold=True))
        painter.drawText(QRectF(200, 300, 880, 28), Qt.AlignmentFlag.AlignCenter, f"Team stars  {stars} / 6")
        play = QRectF(490, 342, 300, 58)
        label = "Play" if not self.cleared else "Continue"
        self._button(painter, play, label, ("play",), fill="#F0C14A")
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
        painter.drawText(
            QRectF(rect.left(), rect.bottom() - 24, rect.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            f"{count}/3 tracked",
        )

    def _overlay_card(self, painter: QPainter, text: str, win: bool) -> None:
        self._shade(painter, 90)
        card = QRectF(250, 150, 760, 250)
        self._panel(painter, card, 24)
        painter.setPen(QColor("#FFF6D8"))
        painter.setFont(self._font(26, bold=True))
        painter.drawText(QRectF(270, 170, 720, 80), self._wrap(), text)
        if win:
            if self.level is not None and self.level.number < 6:
                self._button(painter, QRectF(290, 280, 210, 52), "Next", ("next",), fill="#F0C14A")
            else:
                self._button(painter, QRectF(290, 280, 210, 52), "Home", ("home",), fill="#F0C14A")
            self._button(painter, QRectF(520, 280, 210, 52), "Replay", ("restart",), fill="#314E79")
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
