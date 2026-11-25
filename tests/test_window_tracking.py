import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from magic_mirror.pose_track import Body
from magic_mirror.window import MazeWindow


class TrackingWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MazeWindow(camera=-1)
        self.window._timer.stop()
        self.window._begin(1)

    def tearDown(self):
        self.window.close()

    def test_one_missing_player_does_not_interrupt_the_others(self):
        players = [Body(0.2, False, False, 1), Body(0.5, False, False, 2), Body(0.8, False, False, 3)]
        with patch('magic_mirror.window.time.monotonic', return_value=1.0):
            self.window._on_bodies(players)
        with patch('magic_mirror.window.time.monotonic', return_value=10.0):
            self.window._on_bodies([players[0], players[2]])
            self.window._watch_tracking()
            self.assertFalse(self.window.paused)
            self.assertEqual([mirror.angle for mirror in self.window.level.mirrors], [1, 1, 1])

    def test_no_players_pauses_after_grace_and_resume_does_not_repause(self):
        with patch('magic_mirror.window.time.monotonic', return_value=1.0):
            self.window._on_bodies([Body(0.2, False, False, 1)])
        with patch('magic_mirror.window.time.monotonic', return_value=2.0):
            self.window._on_bodies([])
            self.window._watch_tracking()
        with patch('magic_mirror.window.time.monotonic', return_value=3.2):
            self.window._watch_tracking()
            self.assertFalse(self.window.paused)
        with patch('magic_mirror.window.time.monotonic', return_value=5.2):
            self.window._watch_tracking()
            self.assertTrue(self.window.paused)
            self.assertEqual(self.window.pause_reason, 'tracking')
            self.window._activate(('resume',))
            self.window._watch_tracking()
            self.assertFalse(self.window.paused)
        with patch('magic_mirror.window.time.monotonic', return_value=30.0):
            self.window._watch_tracking()
            self.assertFalse(self.window.paused)

    def test_held_arm_turns_assigned_mirror_once_until_lowered(self):
        down = Body(0.8, False, False, 3)
        up = Body(0.8, True, False, 3)
        with patch('magic_mirror.window.time.monotonic', return_value=1.0):
            self.window._on_bodies([down])
            self.window._on_bodies([up])
        with patch('magic_mirror.window.time.monotonic', return_value=1.3):
            self.window._on_bodies([up])
        self.assertEqual([m.angle for m in self.window.level.mirrors], [1, 1, 0])
        with patch('magic_mirror.window.time.monotonic', return_value=1.6):
            self.window._on_bodies([up])
            self.window._on_bodies([down])
            self.window._on_bodies([up])
        self.assertEqual([m.angle for m in self.window.level.mirrors], [1, 1, 0])
        with patch('magic_mirror.window.time.monotonic', return_value=1.9):
            self.window._on_bodies([up])
        self.assertEqual([m.angle for m in self.window.level.mirrors], [1, 1, 1])

    def test_p_resumes_tracking_pause_and_suppresses_repeated_pause(self):
        self.window.paused = True
        self.window.pause_reason = 'tracking'
        self.window.had_body = True
        self.window.missing_since = 1.0
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_P, Qt.KeyboardModifier.NoModifier)
        with patch('magic_mirror.window.time.monotonic', return_value=10.0):
            self.window.keyPressEvent(event)
            self.window._watch_tracking()
        self.assertFalse(self.window.paused)

    def test_new_level_reenables_tracking_pause(self):
        self.window.ignore_tracking_loss = True
        self.window._begin(1)
        self.assertFalse(self.window.ignore_tracking_loss)

    def test_reassignment_requires_a_fresh_arms_down_gesture(self):
        self.window.wait_for_arms_down = False
        self.window._tracking_reset()
        held = Body(0.4, True, False, 1)
        with patch('magic_mirror.window.time.monotonic', return_value=2.0):
            self.window._on_bodies([held])
        with patch('magic_mirror.window.time.monotonic', return_value=3.0):
            self.window._on_bodies([held])
        self.assertEqual(self.window.level.mirrors[0].angle, 1)
        self.assertTrue(self.window.wait_for_arms_down)


if __name__ == '__main__':
    unittest.main()
