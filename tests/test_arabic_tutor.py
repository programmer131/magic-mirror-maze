import unittest
import time
import base64
from unittest.mock import Mock, call, patch
from pathlib import Path
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication
from magic_mirror.arabic_tutor import ArabicTutorState, ArabicTutorWorker, session_update
from magic_mirror.arabic_catalog import TUTOR_ITEMS
from magic_mirror.window import MazeWindow


class ArabicTutorTests(unittest.TestCase):
    def test_catalog_has_100_readable_matching_pictures(self):
        self.assertEqual(len(TUTOR_ITEMS), 100)
        self.assertEqual(len({item.picture for item in TUTOR_ITEMS}), 100)
        folder = Path(__file__).resolve().parents[1] / 'assets'
        for item in TUTOR_ITEMS:
            self.assertTrue(QImageReader(str(folder / f'vocab_{item.picture}.png')).canRead(), item.picture)

    def test_feminine_picture_uses_correct_question_and_phrase(self):
        fan = next(i for i, item in enumerate(TUTOR_ITEMS) if item.picture == 'fan')
        state = ArabicTutorState(['Amna'], order=[fan])
        state.apply('choose_difficulty', {'difficulty': 'hard'})
        self.assertEqual(state.snapshot()['question'], 'ما هذه؟')
        self.assertFalse(state.apply('submit_answer', {'answer': 'هذا مروحة'})['ok'])
        self.assertTrue(state.apply('submit_answer', {'answer': 'هذه مروحة'})['ok'])

    def test_urdu_script_variant_is_accepted_for_the_arabic_word(self):
        fan = next(i for i, item in enumerate(TUTOR_ITEMS) if item.picture == 'fan')
        state = ArabicTutorState(['Amna'], order=[fan])
        state.apply('choose_difficulty', {'difficulty': 'easy'})
        self.assertTrue(state.apply('submit_answer', {'answer': 'مروحہ'})['ok'])

    def test_feminine_picture_draws_the_matching_question(self):
        app = QApplication.instance() or QApplication([])
        window = MazeWindow(camera=-1)
        window._timer.stop()
        fan = next(i for i, item in enumerate(TUTOR_ITEMS) if item.picture == 'fan')
        state = ArabicTutorState(['Amna'], order=[fan])
        state.apply('choose_difficulty', {'difficulty': 'easy'})
        window.arabic_state = state.snapshot()
        painter = Mock()
        with patch.object(window, '_sprite') as sprite, patch.object(window, '_panel'), patch.object(window, '_title'):
            window._arabic_live_play(painter)
        visible = ' '.join(str(arg) for call in painter.drawText.call_args_list for arg in call.args)
        self.assertIn('ما هذه؟', visible)
        self.assertNotIn('مروحة', visible)
        self.assertEqual(sprite.call_args.args[1], 'vocab_fan')
        window.close()

    def test_pencil_accepts_full_or_common_short_arabic_word(self):
        state = ArabicTutorState(['Amna'], order=[1])
        state.apply('choose_difficulty', {'difficulty': 'easy'})
        self.assertTrue(state.apply('submit_answer', {'answer': 'قلم رصاص'})['ok'])
        other = ArabicTutorState(['Amna'], order=[1])
        other.apply('choose_difficulty', {'difficulty': 'easy'})
        self.assertTrue(other.apply('submit_answer', {'answer': 'قلم'})['ok'])

    def test_hidden_word_is_not_sent_to_tutor_before_or_after_a_correct_answer(self):
        state = ArabicTutorState([], order=[0, 1])
        players = state.apply('set_players', {'names': ['Amna']})
        choice = state.apply('choose_difficulty', {'difficulty': 'easy'})
        for result in (players, choice):
            self.assertFalse({'picture', 'word', 'roman', 'meaning'} & result.keys())
            self.assertNotIn('كتاب', str(result))
        good = state.apply('submit_answer', {'answer': 'كتاب'})
        self.assertTrue(good['ok'])
        self.assertNotIn('كتاب', str(good))
        self.assertNotIn('accepted_word', good)

    def test_incorrect_answer_gives_a_correct_gender_hint(self):
        fan = next(i for i, item in enumerate(TUTOR_ITEMS) if item.picture == 'fan')
        state = ArabicTutorState(['Amna'], order=[fan])
        state.apply('choose_difficulty', {'difficulty': 'easy'})
        result = state.apply('submit_answer', {'answer': 'كتاب'})
        self.assertFalse(result['ok'])
        self.assertEqual(result['hint'], 'هذه مروحة')

    def test_spoken_hint_request_reveals_only_current_answer(self):
        state = ArabicTutorState(['Amna'], order=[0])
        state.apply('choose_difficulty', {'difficulty': 'easy'})
        self.assertEqual(state.apply('get_hint', {})['hint'], 'هذا كتاب')
        self.assertEqual(state.stage, 'playing')

    def test_easy_and_hard_choices_and_turns(self):
        state = ArabicTutorState(['Amna', 'Maryam', 'Abdullah'], order=list(range(6)))
        self.assertEqual(state.snapshot()['stage'], 'choose')
        self.assertFalse(state.apply('submit_answer', {'answer': 'كتاب'})['ok'])
        self.assertTrue(state.apply('choose_difficulty', {'difficulty': 'easy'})['ok'])
        self.assertFalse(state.apply('submit_answer', {'answer': 'قلم'})['ok'])
        self.assertTrue(state.apply('submit_answer', {'answer': 'كتاب'})['ok'])
        self.assertEqual(state.snapshot()['child'], 'Amna')
        self.assertEqual(state.snapshot()['repetitions'], 1)
        self.assertEqual(state.snapshot()['stage'], 'awaiting_advance')
        self.assertEqual(state.snapshot()['picture'], 'book')
        self.assertEqual(state.snapshot()['child'], 'Amna')
        state.advance_picture()
        self.assertEqual(state.snapshot()['child'], 'Maryam')
        self.assertEqual(state.snapshot()['picture'], 'pencil')

    def test_hard_accepts_each_full_phrase_once(self):
        state = ArabicTutorState(['A', 'M', 'B'], order=list(range(6)))
        state.apply('choose_difficulty', {'difficulty': 'hard'})
        self.assertFalse(state.apply('submit_answer', {'answer': 'كتاب'})['ok'])
        for answer in ('هذا كتاب', 'هذا قلم', 'هذا باب', 'هذا بيت', 'هذا كرسي', 'هذا مفتاح'):
            self.assertTrue(state.apply('submit_answer', {'answer': answer})['ok'])
            state.advance_picture()
        self.assertEqual(state.snapshot()['stage'], 'finished')
        state.apply('play_again', {})
        self.assertEqual(state.snapshot()['stage'], 'choose')

    def test_session_uses_live_audio_and_tools(self):
        session = session_update(['Amna', 'Maryam', 'Abdullah'])['session']
        self.assertEqual(session['audio']['input']['format']['rate'], 24000)
        self.assertEqual(session['output_modalities'], ['audio'])
        self.assertIn('submit_answer', [tool['name'] for tool in session['tools']])
        self.assertIn('set_players', [tool['name'] for tool in session['tools']])
        self.assertNotIn('secret', str(session))

    def test_unexpected_connection_close_reports_error_instead_of_stale_listening(self):
        worker = ArabicTutorWorker([])
        worker._status = Mock()
        socket = Mock()
        socket.recv.return_value = ''
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only-key'}), \
             patch('websocket.create_connection', return_value=socket):
            worker.run()
        worker._status.assert_any_call('service_error')

    def test_short_answer_immediately_after_tutor_is_not_dropped(self):
        worker = ArabicTutorWorker([])
        worker.speaking = False
        worker.play_until = 10.0
        worker._send = Mock()
        speech = b'\x10\x01' * 2400
        tutor_audio = b'\x20\x02' * 2400
        chunks = [tutor_audio, speech, speech, speech, b'\0' * 4800]

        class Stream:
            def read(self, _size):
                if chunks:
                    return chunks.pop(0)
                worker.stopping.set()
                return b''

        recorder = Mock()
        recorder.stdout = Stream()
        with patch('magic_mirror.arabic_tutor.subprocess.Popen', return_value=recorder), \
             patch('magic_mirror.arabic_tutor.time.monotonic', side_effect=[9.95, 10.05, 10.15, 10.25, 10.36]):
            worker._capture()
        sent = b''.join(base64.b64decode(call.args[0]['audio']) for call in worker._send.call_args_list)
        self.assertTrue(speech in sent)
        self.assertFalse(tutor_audio in sent)

    def test_network_failure_during_microphone_send_is_not_reported_as_mic_failure(self):
        worker = ArabicTutorWorker([])
        worker.speaking = False
        worker.play_until = 0
        worker._send = Mock(side_effect=OSError('connection lost'))
        worker._status = Mock()
        worker.stop = Mock()
        recorder = Mock()
        recorder.stdout.read.return_value = b'\0' * 4800
        with patch('magic_mirror.arabic_tutor.subprocess.Popen', return_value=recorder), \
             patch('magic_mirror.arabic_tutor.time.monotonic', return_value=10.0):
            worker._capture()
        worker._status.assert_any_call('service_error')
        self.assertNotIn(call('microphone_error'), worker._status.call_args_list)

    def test_tutor_is_told_to_ask_in_urdu_without_giving_the_answer(self):
        instructions = session_update(['Amna', 'Maryam', 'Abdullah'])['session']['instructions']
        self.assertIn('Do not reveal the answer', instructions)
        self.assertIn('Urdu is the primary language', instructions)
        self.assertIn('wrong', instructions)
        self.assertIn('Always ask', instructions)
        self.assertIn('ما هذا؟', instructions)

    def test_tool_events_update_picture_and_reply_to_model(self):
        worker = ArabicTutorWorker(['Amna', 'Maryam', 'Abdullah'])
        worker.state.order = list(range(6))
        worker._send = Mock()
        worker._event({'type': 'response.done', 'response': {'output': [
            {'type': 'function_call', 'name': 'choose_difficulty', 'call_id': 'c1',
             'arguments': '{"difficulty":"easy"}'}]}})
        self.assertEqual(worker.state.snapshot()['picture'], 'book')
        self.assertEqual(worker.state.snapshot()['stage'], 'playing')
        self.assertEqual(worker._send.call_args_list[0].args[0]['item']['call_id'], 'c1')
        self.assertEqual(worker._send.call_args_list[1].args[0]['type'], 'response.create')

    def test_correct_answer_requests_brief_praise_only(self):
        worker = ArabicTutorWorker(['Amna'])
        worker.state.order = list(range(6))
        worker.state.apply('choose_difficulty', {'difficulty': 'easy'})
        worker._send = Mock()
        worker._event({'type': 'response.done', 'response': {'output': [
            {'type': 'function_call', 'name': 'submit_answer', 'call_id': 'c2',
             'arguments': '{"answer":"كتاب"}'}]}})
        self.assertEqual(worker.state.stage, 'awaiting_advance')
        prompt = worker._send.call_args_list[-1].args[0]['response']['instructions'].lower()
        self.assertIn('nothing else', prompt)
        self.assertNotIn('كتاب', prompt)

    def test_easy_picture_does_not_display_the_answer(self):
        app = QApplication.instance() or QApplication([])
        window = MazeWindow(camera=-1)
        window._timer.stop()
        state = ArabicTutorState(['Amna', 'Maryam', 'Abdullah'], order=list(range(6)))
        state.apply('choose_difficulty', {'difficulty': 'easy'})
        window.arabic_state = state.snapshot()
        painter = Mock()
        with patch.object(window, '_sprite'), patch.object(window, '_panel'), patch.object(window, '_title'):
            window._arabic_live_play(painter)
        visible_text = ' '.join(str(arg) for call in painter.drawText.call_args_list for arg in call.args)
        self.assertNotIn('كتاب', visible_text)
        self.assertNotIn('kitaab', visible_text.lower())
        self.assertNotIn('Book', visible_text)
        window.close()

    def test_one_or_two_children_take_turns_after_names_are_spoken(self):
        for names in (['Amna'], ['Maryam', 'Abdullah']):
            state = ArabicTutorState([], order=list(range(6)))
            self.assertEqual(state.snapshot()['stage'], 'names')
            self.assertFalse(state.apply('set_players', {'names': []})['ok'])
            self.assertFalse(state.apply('set_players', {'names': ['A', 'B', 'C', 'D']})['ok'])
            self.assertTrue(state.apply('set_players', {'names': names})['ok'])
            self.assertTrue(state.apply('choose_difficulty', {'difficulty': 'easy'})['ok'])
            state.apply('submit_answer', {'answer': 'كتاب'})
            state.advance_picture()
            self.assertEqual(state.snapshot()['child'], names[1 % len(names)])

    def test_picture_waits_for_tutors_praise_to_finish(self):
        worker = ArabicTutorWorker(['Amna', 'Maryam'])
        worker.state.order = list(range(6))
        worker.state.apply('choose_difficulty', {'difficulty': 'easy'})
        worker.state.apply('submit_answer', {'answer': 'كتاب'})
        worker._send = Mock()
        worker.play_until = time.monotonic() + 0.15
        worker._event({'type': 'response.done', 'response': {'output': []}})
        self.assertEqual(worker.state.snapshot()['picture'], 'book')
        time.sleep(0.55)
        self.assertEqual(worker.state.snapshot()['picture'], 'pencil')
        self.assertEqual(worker.state.snapshot()['child'], 'Maryam')
        self.assertEqual(worker._send.call_args.args[0]['type'], 'response.create')
        prompt = worker._send.call_args.args[0]['response']['instructions'].lower()
        self.assertIn('do not announce', prompt)
        self.assertNotIn('picture just changed', prompt)
        worker.stop()

    def test_completed_practice_keeps_current_picture_visible(self):
        app = QApplication.instance() or QApplication([])
        window = MazeWindow(camera=-1)
        window._timer.stop()
        state = ArabicTutorState(['Amna'], order=list(range(6)))
        state.apply('choose_difficulty', {'difficulty': 'easy'})
        state.apply('submit_answer', {'answer': 'كتاب'})
        window.arabic_state = state.snapshot()
        with patch.object(window, '_sprite') as sprite, patch.object(window, '_panel'), patch.object(window, '_title'):
            window._arabic_live_play(Mock())
        self.assertEqual(sprite.call_args.args[1], 'vocab_book')
        window.close()

    def test_picture_order_is_shuffled_for_new_sessions(self):
        with patch('magic_mirror.arabic_tutor.random.shuffle', side_effect=lambda order: order.reverse()):
            state = ArabicTutorState(['A'])
        self.assertEqual(state.snapshot()['picture'], TUTOR_ITEMS[-1].picture)

    def test_live_tutor_starts_without_a_camera(self):
        app = QApplication.instance() or QApplication([])
        window = MazeWindow(camera=None, camera_enabled=False)
        self.assertIsNone(window.worker)
        window.close()

    def test_opening_tutor_releases_camera(self):
        app = QApplication.instance() or QApplication([])
        window = MazeWindow(camera=-1)
        camera = Mock()
        camera.wait.return_value = True
        window.worker = camera
        with patch('magic_mirror.window.ArabicTutorWorker'):
            window._begin_arabic_tutor()
            camera.stop.assert_called_once()
            self.assertIsNone(window.worker)
            self.assertEqual(window.mode, 'arabic_live')
            window.close()

if __name__ == '__main__':
    unittest.main()
