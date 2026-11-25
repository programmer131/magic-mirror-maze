"""Recognize a deliberate victory gesture despite brief pose dropouts."""

from dataclasses import dataclass, field


@dataclass
class _Hand:
    ready: bool = False
    started: float | None = None
    last_up: float | None = None


@dataclass
class _Track:
    x: float
    seen: float
    left: _Hand = field(default_factory=_Hand)
    right: _Hand = field(default_factory=_Hand)


class NextGesture:
    def __init__(self) -> None:
        self.tracks: list[_Track] = []
        self.progress = 0.0

    @property
    def ready(self) -> bool:
        return any(track.left.ready or track.right.ready for track in self.tracks)

    def reset(self) -> None:
        self.tracks.clear()
        self.progress = 0.0

    def update(self, bodies, now: float) -> bool:
        self.tracks = [track for track in self.tracks if now - track.seen <= 0.8]
        pairs = sorted(
            (abs(body.x - track.x), index, track_index)
            for index, body in enumerate(bodies)
            for track_index, track in enumerate(self.tracks)
            if abs(body.x - track.x) <= 0.18
        )
        matched_bodies: set[int] = set()
        matched_tracks: set[int] = set()
        matches = []
        for _, body_index, track_index in pairs:
            if body_index not in matched_bodies and track_index not in matched_tracks:
                matched_bodies.add(body_index)
                matched_tracks.add(track_index)
                matches.append((bodies[body_index], self.tracks[track_index]))
        for index, body in enumerate(bodies):
            if index not in matched_bodies:
                track = _Track(body.x, now)
                self.tracks.append(track)
                matches.append((body, track))

        for body, track in matches:
            track.x = body.x
            track.seen = now
            for hand, visible, up in (
                (track.left, body.left_visible, body.left_up),
                (track.right, body.right_visible, body.right_up),
            ):
                if visible and not up:
                    hand.ready = True
                    hand.started = None
                    hand.last_up = None
                elif visible and up and hand.ready:
                    if hand.started is None or (hand.last_up is not None and now - hand.last_up > 0.8):
                        hand.started = now
                    hand.last_up = now
                    if now - hand.started >= 2.0:
                        self.reset()
                        return True
                elif hand.last_up is not None and now - hand.last_up > 0.8:
                    hand.started = None
                    hand.last_up = None

        self.progress = max(
            (min(1.0, (now - hand.started) / 2.0)
             for track in self.tracks for hand in (track.left, track.right) if hand.started is not None),
            default=0.0,
        )
        return False
