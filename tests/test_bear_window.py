import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from magic_mirror.pose_track import Body
from magic_mirror.window import MazeWindow


class BearWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MazeWindow(camera=-1)
        self.window._timer.stop()
        self.window.bear_cleared = []

    def tearDown(self):
        self.window.close()

    def test_correct_child_opens_only_one_gate(self):
        self.window._begin_bear(1)
        self.window._turn(2, False)
        self.assertEqual(self.window.bear.gates_open, 0)
        self.window._turn(1, False)
        self.assertEqual(self.window.bear.gates_open, 1)
        self.window._turn(2, False)
        self.assertEqual(self.window.bear.gates_open, 1)
        self.window.bear.tick(2.0)
        self.window._turn(2, False)
        self.assertEqual(self.window.bear.gates_open, 2)

    def test_camera_game_waits_until_all_three_players_are_calibrated(self):
        self.window.worker = SimpleNamespace(reset_tracking=False, calibrate_for_three=False)
        try:
            self.window._begin_bear(1)
            self.assertFalse(self.window.bear_calibrated)
            self.assertTrue(self.window.worker.calibrate_for_three)
            self.window._turn(1, False)
            self.assertEqual(self.window.bear.gates_open, 0)
            self.window._bear_players_ready()
            self.window._turn(1, False)
            self.assertEqual(self.window.bear.gates_open, 1)
        finally:
            self.window.worker = None

    def test_real_gesture_routes_to_the_correct_gate(self):
        self.window._begin_bear(1)
        down = [Body(0.2, False, False, 1), Body(0.5, False, False, 2), Body(0.8, False, False, 3)]
        with patch('magic_mirror.window.time.monotonic', return_value=1.0):
            self.window._on_bodies(down)
            self.window._on_bodies([Body(0.2, True, False, 1), *down[1:]])
        with patch('magic_mirror.window.time.monotonic', return_value=1.3):
            self.window._on_bodies([Body(0.2, True, False, 1), *down[1:]])
        self.assertEqual(self.window.bear.gates_open, 1)

    def test_wrong_childs_gesture_does_not_open_gate(self):
        self.window._begin_bear(1)
        down = [Body(0.2, False, False, 1), Body(0.5, False, False, 2), Body(0.8, False, False, 3)]
        wrong = [down[0], Body(0.5, True, False, 2), down[2]]
        with patch('magic_mirror.window.time.monotonic', return_value=1.0):
            self.window._on_bodies(down)
            self.window._on_bodies(wrong)
        with patch('magic_mirror.window.time.monotonic', return_value=1.3):
            self.window._on_bodies(wrong)
        self.assertEqual(self.window.bear.gates_open, 0)

    def test_bear_level_selector_starts_with_an_arm_gesture(self):
        self.window._open_bear_menu()
        with patch('magic_mirror.window.time.monotonic', return_value=1.0):
            self.window._on_poses([Body(0.2, False, False, 1)])
        for t in (1.1, 1.5, 2.0, 2.5, 3.0, 3.2):
            with patch('magic_mirror.window.time.monotonic', return_value=t):
                self.window._on_poses([Body(0.2, True, False, 1)])
        self.assertEqual(self.window.mode, 'bear')
        self.assertEqual(self.window.bear.level, 1)

    def test_bear_victory_advances_to_next_level(self):
        self.window.bear_cleared = [1]
        self.window._begin_bear(1)
        self.window.celebrating = True
        self.window._after_win()
        self.assertEqual(self.window.mode, 'bear')
        self.assertEqual(self.window.bear.level, 2)

    def test_completing_a_level_saves_once_and_unlocks_next(self):
        self.window._begin_bear(1)
        for player in (1, 2, 3):
            self.window._turn(player, False)
            self.window.bear.tick(2.0)
        with patch('magic_mirror.window.save_bear_progress') as save:
            self.window._tick()
            self.window._tick()
            save.assert_called_once_with([1])
        self.assertTrue(self.window.celebrating)
        self.assertTrue(self.window._bear_unlocked(2))


if __name__ == '__main__':
    unittest.main()
