"""One webcam, up to three children, left and right arm raises.

MediaPipe is imported on the thread that builds the worker. Importing it
inside the camera thread aborts under Qt.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from .player_tracking import PlayerTracker, calibrate_three

cv2 = None
np = None
mp = None
mp_python = None
vision = None

LINKS = (
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (11, 12),
    (11, 23),
    (12, 24),
    (23, 24),
)
COLORS = ((61, 125, 255), (60, 179, 113), (240, 138, 36))


@dataclass
class Body:
    x: float
    left_up: bool
    right_up: bool
    player: int | None = None
    left_visible: bool = True
    right_visible: bool = True


def camera_sources(camera: int | None, dev: Path = Path('/dev')) -> list[str]:
    if camera is not None:
        return [str(dev / f'video{camera}')]
    by_id = dev / 'v4l' / 'by-id'
    stable = sorted(p for p in by_id.glob('*-video-index0') if p.exists())
    devices = sorted(dev.glob('video[0-9]*'))
    return [str(p) for p in stable + devices]


class CameraStream:
    def __init__(self, opener):
        self.opener = opener
        self.capture = None
        self.generation = 0

    def read(self):
        if self.capture is None:
            self.capture = self.opener()
            if self.capture is not None:
                self.generation += 1
        if self.capture is None:
            return False, None
        try:
            ok, frame = self.capture.read()
        except Exception:
            ok, frame = False, None
        if not ok or frame is None:
            self.close()
            return False, None
        return True, frame

    def close(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None


def _load() -> bool:
    global cv2, np, mp, mp_python, vision
    if cv2 is not None and mp is not None:
        return True
    try:
        import cv2 as _cv2
        import mediapipe as _mp
        import numpy as _np
        from mediapipe.tasks import python as _python
        from mediapipe.tasks.python import vision as _vision
    except Exception as exc:
        print(f"pose import: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False
    cv2 = _cv2
    np = _np
    mp = _mp
    mp_python = _python
    vision = _vision
    return True


def _visibility(point) -> float:
    value = getattr(point, "visibility", None)
    return 1.0 if value is None else float(value)


def square_frame(rgb):
    height, width = rgb.shape[:2]
    side = max(height, width)
    pad_x = (side - width) // 2
    pad_y = (side - height) // 2
    canvas = np.zeros((side, side, 3), dtype=np.uint8)
    canvas[pad_y : pad_y + height, pad_x : pad_x + width] = rgb
    return canvas, pad_x, pad_y, side, width, height


def _unmap(point, pad_x: int, pad_y: int, side: int, width: int, height: int):
    x = (float(point.x) * side - pad_x) / width
    y = (float(point.y) * side - pad_y) / height
    return x, y


def bodies_from_result(result, geometry) -> list[Body]:
    pad_x, pad_y, side, width, height = geometry
    found = []
    poses = getattr(result, "pose_landmarks", None) or []
    for pose in poses:
        if len(pose) < 25:
            continue
        joints = [_unmap(point, pad_x, pad_y, side, width, height) for point in pose]
        nose_x = joints[0][0]
        left_shoulder, right_shoulder = joints[11], joints[12]
        left_wrist, right_wrist = joints[15], joints[16]
        left_seen = _visibility(pose[15]) > 0.35 and _visibility(pose[11]) > 0.35
        right_seen = _visibility(pose[16]) > 0.35 and _visibility(pose[12]) > 0.35
        found.append(
            (
                nose_x,
                Body(
                    x=nose_x,
                    left_up=left_seen and left_wrist[1] < left_shoulder[1] - 0.04,
                    right_up=right_seen and right_wrist[1] < right_shoulder[1] - 0.04,
                    left_visible=left_seen,
                    right_visible=right_seen,
                ),
                joints,
            )
        )
    found.sort(key=lambda item: item[0])
    return found[:3]


def _draw(rgb, people) -> None:
    height, width = rgb.shape[:2]
    for _x, body, joints in people:
        color = COLORS[body.player - 1] if body.player else (180, 180, 180)
        points = {}
        for joint_index, (x, y) in enumerate(joints):
            if x < -0.05 or y < -0.05 or x > 1.05 or y > 1.05:
                continue
            points[joint_index] = (int(x * width), int(y * height))
        for start, end in LINKS:
            if start in points and end in points:
                cv2.line(rgb, points[start], points[end], color, 8, cv2.LINE_AA)
        for joint_index in (15, 16):
            if joint_index in points:
                cv2.circle(rgb, points[joint_index], 16, color, -1, cv2.LINE_AA)
                cv2.circle(rgb, points[joint_index], 16, (255, 255, 255), 2, cv2.LINE_AA)


class PoseWorker(QThread):
    bodies_ready = Signal(object)
    poses_ready = Signal(object)
    preview_ready = Signal(object)
    status_ready = Signal(str)
    tracking_reset = Signal()
    players_calibrated = Signal()

    def __init__(self, camera: int | None, model) -> None:
        super().__init__()
        self.camera = camera
        self.model = model
        self.running = True
        self.reset_tracking = False
        self.calibrate_for_three = False
        self.require_three_players = False
        _load()

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        if cv2 is None:
            self.status_ready.emit("missing")
            return
        recognizer = self._recognizer()
        stream = CameraStream(lambda: _open(self.camera))
        started = time.monotonic()
        last_stamp = 0
        warned = False
        tracker = PlayerTracker()
        generation = 0
        last_counts = None
        last_report = 0.0
        while self.running:
            if self.reset_tracking:
                tracker = PlayerTracker()
                self.reset_tracking = False
                self.tracking_reset.emit()
            ok, frame = stream.read()
            if not ok or frame is None:
                self.status_ready.emit("missing")
                self.bodies_ready.emit([])
                self.poses_ready.emit([])
                time.sleep(0.5)
                continue
            if stream.generation != generation:
                generation = stream.generation
                tracker = PlayerTracker()
                if self.require_three_players:
                    self.calibrate_for_three = True
                self.tracking_reset.emit()
            frame = cv2.flip(frame, 1)
            rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if recognizer is not None:
                try:
                    square, pad_x, pad_y, side, width, height = square_frame(rgb)
                    stamp = max(last_stamp + 1, int((time.monotonic() - started) * 1000))
                    last_stamp = stamp
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(square))
                    result = recognizer.detect_for_video(image, stamp)
                    people = bodies_from_result(result, (pad_x, pad_y, side, width, height))
                    positions = [item[1].x for item in people]
                    if self.calibrate_for_three:
                        assignments = calibrate_three(positions)
                        if assignments is None:
                            assignments = [None] * len(people)
                            tracker.reassigned = False
                        else:
                            tracker = PlayerTracker()
                            assignments = tracker.assign(positions)
                            self.calibrate_for_three = False
                            self.players_calibrated.emit()
                    else:
                        assignments = tracker.assign(positions)
                    if tracker.reassigned:
                        if self.require_three_players:
                            self.calibrate_for_three = True
                        self.tracking_reset.emit()
                    for person, player in zip(people, assignments):
                        person[1].player = player
                    counts = (len(people), sum(player is not None for player in assignments))
                    now = time.monotonic()
                    if counts != last_counts and now - last_report >= 2.0:
                        print(f"tracking: {counts[0]} detected, {counts[1]} assigned", file=sys.stderr)
                        last_counts, last_report = counts, now
                    _draw(rgb, people)
                    self.poses_ready.emit([person[1] for person in people])
                    self.bodies_ready.emit([person[1] for person in people if person[1].player is not None])
                except Exception as exc:
                    if not warned:
                        print(f"pose: {type(exc).__name__}: {exc}", file=sys.stderr)
                        warned = True
                    self.bodies_ready.emit([])
                    self.poses_ready.emit([])
            small = cv2.resize(rgb, (320, 180), interpolation=cv2.INTER_AREA)
            small = np.ascontiguousarray(small)
            preview = QImage(small.data, 320, 180, 320 * 3, QImage.Format.Format_RGB888).copy()
            self.preview_ready.emit(preview)
            self.status_ready.emit("ok" if recognizer is not None else "keyboard")
        stream.close()
        if recognizer is not None:
            recognizer.close()

    def _recognizer(self):
        if mp is None or not self.model.is_file():
            return None
        for delegate in (mp_python.BaseOptions.Delegate.GPU, mp_python.BaseOptions.Delegate.CPU):
            try:
                options = vision.PoseLandmarkerOptions(
                    base_options=mp_python.BaseOptions(model_asset_path=str(self.model), delegate=delegate),
                    running_mode=vision.RunningMode.VIDEO,
                    num_poses=3,
                    min_pose_detection_confidence=0.4,
                    min_pose_presence_confidence=0.4,
                    min_tracking_confidence=0.4,
                )
                recognizer = vision.PoseLandmarker.create_from_options(options)
                print(f"pose model: using {delegate.name}", file=sys.stderr)
                return recognizer
            except Exception as exc:
                print(f"pose model {delegate.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None


def _open(camera: int | None):
    for source in camera_sources(camera):
        api = cv2.CAP_V4L2
        capture = cv2.VideoCapture(source, api)
        if capture.isOpened():
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            print(f"camera: {source} {int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))}", file=sys.stderr)
            return capture
        capture.release()
    return None
