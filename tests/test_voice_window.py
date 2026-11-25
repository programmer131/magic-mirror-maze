import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from magic_mirror.window import MazeWindow


class VoiceWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MazeWindow(camera=-1)
        self.window._timer.stop()
        self.window.activity_cleared = {}
        with patch.object(self.window, '_ensure_speech'):
            self.window._begin_voice('arabic', 1)
        self.window.speech_worker = Mock()
        self.window.voice_status = 'ready'

    def tearDown(self):
        self.window.speech_worker = None
        self.window.close()

    def test_microphone_starts_only_when_current_child_gestures(self):
        self.window.speech_worker.listen.assert_not_called()
        self.window._turn(2, False)
        self.window.speech_worker.listen.assert_not_called()
        self.window._turn(1, False)
        self.window.speech_worker.listen.assert_called_once()
        self.assertEqual(self.window.speech_worker.listen.call_args.args[1], 'ar')

    def test_correct_answer_advances_and_unclear_answer_is_forgiving(self):
        self.window._turn(1, False)
        request = self.window.voice_request
        self.window._on_voice_result(request, 'هذا قلم', '')
        self.assertEqual(self.window.voice_round.current_player, 1)
        self.assertIn('try', self.window.voice_feedback.lower())
        self.window.voice_status = 'ready'
        self.window._turn(1, False)
        self.window._on_voice_result(self.window.voice_request, 'هذا كتاب', '')
        self.assertEqual(self.window.voice_round.current_player, 2)
        self.assertEqual(self.window.voice_round.answers, ['كتاب'])

    def test_old_speech_result_cannot_change_current_round(self):
        self.window._on_voice_result(-1, 'هذا كتاب', '')
        self.assertEqual(self.window.voice_round.current_player, 1)

    def test_three_children_complete_a_shared_arabic_round(self):
        with patch('magic_mirror.window.save_activity_progress') as save:
            for child, answer in enumerate(('هذا كتاب', 'هذا قلم', 'هذا باب'), 1):
                self.window.voice_status = 'ready'
                self.window._turn(child, False)
                self.window._on_voice_result(self.window.voice_request, answer, '')
                self.assertEqual(self.window.voice_round.turn, child)
            self.assertTrue(self.window.celebrating)
            self.assertEqual(self.window.voice_last_item.picture, 'door')
            save.assert_called_once()

    def test_voice_is_not_interrupted_by_tracking_loss(self):
        self.window.had_body = True
        self.window.missing_since = 0
        self.window._watch_tracking()
        self.assertFalse(self.window.paused)


if __name__ == '__main__':
    unittest.main()
