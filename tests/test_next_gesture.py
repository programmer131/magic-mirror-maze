import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from magic_mirror.pose_track import Body
from magic_mirror.window import MazeWindow


class NextGestureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MazeWindow(camera=-1)
        self.window._timer.stop()
        self.window._begin(1)
        self.window.celebrating = True
        self.window._after_win = Mock()

    def tearDown(self):
        self.window.close()

    def bodies_at(self, now, bodies):
        with patch('magic_mirror.window.time.monotonic', return_value=now):
            self.window._on_poses(bodies)

    def test_lower_then_hold_both_arms_advances_once(self):
        down = Body(0.2, False, False, 1)
        up = Body(0.2, True, True, 1)
        self.bodies_at(1.0, [up])
        self.bodies_at(4.0, [up])
        self.window._after_win.assert_not_called()
        self.bodies_at(4.1, [down])
        self.bodies_at(4.2, [up])
        self.bodies_at(4.7, [up])
        self.bodies_at(5.2, [up])
        self.bodies_at(5.7, [up])
        self.bodies_at(6.1, [up])
        self.window._after_win.assert_not_called()
        self.bodies_at(6.3, [up])
        self.bodies_at(9.0, [up])
        self.window._after_win.assert_called_once_with()

    def test_lost_tracking_requires_lowering_arms_again(self):
        down = Body(0.2, False, False, 1)
        up = Body(0.2, True, True, 1)
        self.bodies_at(1.0, [down])
        self.bodies_at(1.1, [up])
        self.bodies_at(2.0, [])
        self.bodies_at(3.0, [up])
        self.bodies_at(6.0, [up])
        self.window._after_win.assert_not_called()

    def test_any_one_assigned_player_can_advance(self):
        self.bodies_at(1.0, [Body(0.2, True, True, 1), Body(0.7, False, False, 3)])
        self.bodies_at(1.2, [Body(0.2, True, True, 1), Body(0.7, True, True, 3)])
        self.bodies_at(1.7, [Body(0.2, True, True, 1), Body(0.7, True, True, 3)])
        self.bodies_at(2.2, [Body(0.2, True, True, 1), Body(0.7, True, True, 3)])
        self.bodies_at(2.7, [Body(0.2, True, True, 1), Body(0.7, True, True, 3)])
        self.bodies_at(3.3, [Body(0.2, True, True, 1), Body(0.7, True, True, 3)])
        self.window._after_win.assert_called_once_with()

    def test_mirror_reassignment_does_not_cancel_unassigned_player_gesture(self):
        down = Body(0.4, False, False, None)
        up = Body(0.4, True, False, None)
        self.bodies_at(1.0, [down])
        self.bodies_at(1.1, [up])
        self.bodies_at(1.6, [up])
        self.window._tracking_reset()
        self.bodies_at(2.1, [up])
        self.bodies_at(2.6, [up])
        self.bodies_at(3.2, [up])
        self.window._after_win.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
