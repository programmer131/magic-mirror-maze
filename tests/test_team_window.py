import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from magic_mirror.pose_track import Body
from magic_mirror.window import MazeWindow


class TeamWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MazeWindow(camera=-1)
        self.window._timer.stop()
        self.window.activity_cleared = {}

    def tearDown(self):
        self.window.close()

    def test_each_child_contributes_once_in_order(self):
        self.window._begin_team('garden', 1)
        self.window._turn(2, False)
        self.assertEqual(self.window.team.completed, 0)
        self.window._turn(1, False)
        self.assertEqual(self.window.team.completed, 1)
        self.window.team.tick(2.0)
        self.window._turn(2, False)
        self.window.team.tick(2.0)
        self.window._turn(3, False)
        self.window.team.tick(2.0)
        with patch('magic_mirror.window.save_activity_progress') as save:
            self.window._tick()
            self.assertTrue(self.window.celebrating)
            save.assert_called_once()

    def test_next_round_stays_in_same_game(self):
        self.window.activity_cleared = {'rainbow': [1]}
        self.window._begin_team('rainbow', 1)
        self.window.celebrating = True
        self.window._after_win()
        self.assertEqual(self.window.team.kind, 'rainbow')
        self.assertEqual(self.window.team.level, 2)

    def test_more_games_can_be_selected_on_the_home_screen_by_gesture(self):
        self.window.mode = 'home'
        self.window.home_focus = 2
        with patch('magic_mirror.window.time.monotonic', return_value=1.0):
            self.window._on_poses([Body(0.2, False, False, 1)])
        for now in (1.1, 1.5, 2.0, 2.5, 3.0, 3.2):
            with patch('magic_mirror.window.time.monotonic', return_value=now):
                self.window._on_poses([Body(0.2, True, False, 1)])
        self.assertEqual(self.window.mode, 'hub')


if __name__ == '__main__':
    unittest.main()
