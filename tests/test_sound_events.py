import unittest
from unittest.mock import Mock

from PySide6.QtWidgets import QApplication

from magic_mirror.window import MazeWindow


class SoundEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MazeWindow(camera=-1)
        self.window._timer.stop()
        self.window.sounds = Mock()

    def tearDown(self):
        self.window.close()

    def test_start_and_mirror_turn_emit_sounds(self):
        self.window._begin(1)
        self.window._turn(1, False)
        self.window.sounds.play.assert_any_call('start')
        self.window.sounds.play.assert_any_call('mirror1')

    def test_victory_sound_plays_once(self):
        self.window._begin(1)
        self.window._mark_cleared = Mock()
        self.window.beam.solved = True
        self.window.hold = 0.999
        self.window._tick()
        self.window._tick()
        self.assertEqual(self.window.sounds.play.call_args_list.count(unittest.mock.call('victory')), 1)


if __name__ == '__main__':
    unittest.main()
