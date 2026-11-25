"""A hands-free, live Arabic picture tutor. No microphone audio is saved."""
from __future__ import annotations

import base64
import json
import os
import queue
import random
import subprocess
import threading
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QThread, Signal

from .arabic_catalog import TUTOR_ITEMS
from .learning import arabic_matches, _arabic_normalize


@dataclass
class ArabicTutorState:
    names: list[str]
    difficulty: str = ''
    index: int = 0
    repetitions: int = 0
    stage: str = ''
    order: list[int] = field(default_factory=lambda: shuffled_picture_order())

    def __post_init__(self):
        if not self.stage:
            self.stage = 'choose' if self.names else 'names'

    def snapshot(self) -> dict:
        item = TUTOR_ITEMS[self.order[min(self.index, len(self.order) - 1)]]
        return {'stage': self.stage, 'difficulty': self.difficulty, 'index': self.index,
                'repetitions': self.repetitions, 'target_repetitions': 1,
                'names': list(self.names), 'child': self.names[self.index % len(self.names)] if self.names else '', 'picture': item.picture,
                'word': item.word, 'roman': item.roman, 'meaning': item.meaning, 'gender': item.gender,
                'question': 'ما هذه؟' if item.gender == 'f' else 'ما هذا؟',
                'demonstrative': 'هذه' if item.gender == 'f' else 'هذا'}

    def tutor_state(self) -> dict:
        """Keep the answer private until the child needs a correction or hint."""
        return {key: value for key, value in self.snapshot().items()
                if key not in ('picture', 'word', 'roman', 'meaning')}

    def apply(self, name: str, args: dict) -> dict:
        if name == 'set_players' and self.stage in ('names', 'choose', 'playing', 'awaiting_advance'):
            names = args.get('names')
            if isinstance(names, list) and 1 <= len(names) <= 3 and all(isinstance(n, str) and n.strip() for n in names):
                self.names = [' '.join(n.split())[:32] for n in names]
                if self.stage == 'names':
                    self.stage = 'choose'
                return {'ok': True, **self.tutor_state()}
        elif name == 'choose_difficulty' and self.stage == 'choose':
            value = args.get('difficulty')
            if value in ('easy', 'hard'):
                self.difficulty = value
                self.stage = 'playing'
                return {'ok': True, **self.tutor_state()}
        elif name == 'submit_answer' and self.stage == 'playing':
            answer = str(args.get('answer', ''))[:200]
            item = TUTOR_ITEMS[self.order[self.index]]
            phrase = _arabic_normalize(answer)
            forms = ('هذه', 'هاذه', 'hadhihi', 'hadheh', 'hazihi', 'hazi') if item.gender == 'f' else ('هذا', 'هاذا', 'hadha', 'hatha', 'haza')
            has_phrase = any(part in phrase for part in forms)
            if arabic_matches(answer, item) and (self.difficulty != 'hard' or has_phrase):
                self.repetitions += 1
                self.stage = 'awaiting_advance'
                return {'ok': True, 'round_done': True, **self.tutor_state()}
            return {'ok': False, 'hint': f"{'هذه' if item.gender == 'f' else 'هذا'} {item.word}", **self.tutor_state()}
        elif name == 'get_hint' and self.stage == 'playing':
            item = TUTOR_ITEMS[self.order[self.index]]
            return {'ok': True, 'hint': f"{'هذه' if item.gender == 'f' else 'هذا'} {item.word}", **self.tutor_state()}
        elif name == 'play_again' and self.stage == 'finished':
            self.index, self.stage, self.difficulty, self.repetitions = 0, 'choose', '', 0
            self.order = shuffled_picture_order()
            return {'ok': True, **self.tutor_state()}
        elif name == 'go_home':
            self.stage = 'home'
            return {'ok': True, **self.tutor_state()}
        return {'ok': False, **self.tutor_state()}

    def advance_picture(self) -> bool:
        """Change pictures only after the completed practice and tutor's response."""
        if self.stage != 'awaiting_advance':
            return False
        self.index += 1
        self.repetitions = 0
        self.stage = 'finished' if self.index >= len(self.order) else 'playing'
        return True


def shuffled_picture_order() -> list[int]:
    order = list(range(len(TUTOR_ITEMS)))
    random.shuffle(order)
    return order


def praise_response() -> dict:
    praise = random.choice(('أحسنت! شاباش!', 'ما شاء الله! بہت خوب!', 'بارك الله فيك! شاباش!', 'رائع! بہت اچھا!'))
    return {'type': 'response.create', 'response': {'instructions':
            f"In a warm natural voice, say exactly: {praise} Say nothing else."}}


def session_update(names: list[str]) -> dict:
    instructions = '''You are a warm, cheerful, patient voice tutor for one to three children learning beginner Arabic.
Urdu is the primary language: speak naturally and briefly in Pakistani Urdu (اردو), not Pashto or any other regional language. Use everyday Urdu vocabulary and pronunciation; Arabic is for the vocabulary questions, answers, and praise. A short English phrase like “very good” is fine occasionally, but do not translate every instruction into English. Never compete, rank, scold, time, or penalize the children. Be kind about uncertain answers. Use neutral Arabic praise such as بارك الله فيك or Urdu شاباش if a child's gender is unknown.
Begin by asking in Urdu “السلام علیکم! ہمارے ساتھ آج کون کون ہے؟ اپنے نام بتائیے۔” Listen naturally and collect the names of one, two, or three children. Ask whether anyone else is playing if this is unclear, and wait for their response; never assume any particular names or number of children. When the names are known call set_players with exactly the names spoken, in their spoken order. Use those names during the lesson and honor corrections through set_players. After setting names, ask in Urdu whether they want آسان or مشکل; when they answer call choose_difficulty.
The app knows the picture and checks answers. You do not know the hidden word until the child answers incorrectly or asks for a hint; do not guess it. Do not reveal the answer when introducing a picture or asking the first question. Always ask the named child the Arabic question supplied in the tool's question field: “ما هذا؟” for masculine nouns or “ما هذه؟” for feminine nouns. You may add a short Urdu prompt such as “اب بتاؤ”. Do not name, translate, spell, or hint at the object before the child has tried or explicitly asked for help. Then wait for their answer. Do not assume they answered before hearing them.
For each spoken answer call submit_answer with what was said in Arabic script or Latin transliteration. The tool is authoritative about correctness. One correct answer is enough in both modes. When correct, give brief, varied praise such as أحسنت, شاباش, or very good. Do not repeat the answer and do not ask the child to repeat it. Do not announce that the picture is changing or has changed. After the praise stop speaking and wait: the app will advance automatically and prompt you to ask the next question. If the answer is wrong, use the tool's hint to gently pronounce the correct Arabic word, then invite the same child to try again. If the child asks for help before answering, call get_hint and use its hint. If you did not hear clearly, ask in Urdu for a repeat rather than assuming the child is wrong. Easy accepts the word alone; hard asks for the full phrase with the tool's demonstrative, هذا for masculine or هذه for feminine. Speak Arabic clearly.
When the lesson pictures are finished, celebrate together and ask whether they want to play again or go home. If they say again call play_again and ask difficulty again. If they ask to go home or stop, call go_home. Do not request clicks, keys, or gestures. Avoid invented game state; tools tell you which picture is currently visible.'''
    tools = [
        {'type': 'function', 'name': 'set_players', 'description': 'Set or correct the one to three children’s spoken names in order.', 'parameters': {'type': 'object', 'properties': {'names': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': {'type': 'string'}}}, 'required': ['names']}},
        {'type': 'function', 'name': 'choose_difficulty', 'description': 'Choose the level the children spoke.', 'parameters': {'type': 'object', 'properties': {'difficulty': {'type': 'string', 'enum': ['easy', 'hard']}}, 'required': ['difficulty']}},
        {'type': 'function', 'name': 'submit_answer', 'description': 'Check the actual Arabic word or phrase spoken by the current child.', 'parameters': {'type': 'object', 'properties': {'answer': {'type': 'string'}}, 'required': ['answer']}},
        {'type': 'function', 'name': 'get_hint', 'description': 'Reveal the current word only when the child asks for a hint or help.', 'parameters': {'type': 'object', 'properties': {}}},
        {'type': 'function', 'name': 'play_again', 'description': 'Start again after all pictures have been completed.', 'parameters': {'type': 'object', 'properties': {}}},
        {'type': 'function', 'name': 'go_home', 'description': 'Return to the games menu when the children ask to stop or go home.', 'parameters': {'type': 'object', 'properties': {}}},
    ]
    return {'type': 'session.update', 'session': {'type': 'realtime', 'output_modalities': ['audio'],
        'instructions': instructions, 'tools': tools, 'tool_choice': 'auto',
        'audio': {'input': {'format': {'type': 'audio/pcm', 'rate': 24000},
                            'turn_detection': {'type': 'semantic_vad'}},
                  'output': {'format': {'type': 'audio/pcm', 'rate': 24000}, 'voice': 'marin'}}}}


class ArabicTutorWorker(QThread):
    status = Signal(str)
    changed = Signal(object)
    transcript = Signal(str)
    go_home = Signal()

    def __init__(self, names: list[str]):
        super().__init__()
        self.state = ArabicTutorState(names)
        self.stopping = threading.Event()
        self.sock = None
        self.recorder = None
        self.player = None
        self.audio = queue.Queue(maxsize=256)
        self.send_lock = threading.Lock()
        self.play_lock = threading.Lock()
        self.speaking = True
        self.play_until = 0.0
        self.last_status = ''

    def _status(self, value):
        if value != self.last_status:
            self.last_status = value
            self.status.emit(value)

    def _send(self, event):
        with self.send_lock:
            if self.sock and not self.stopping.is_set():
                self.sock.send(json.dumps(event, ensure_ascii=False))

    def stop(self):
        self.stopping.set()
        for proc in (self.recorder, self.player):
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
        if self.sock:
            try:
                self.sock.shutdown()
            except Exception:
                pass

    def _capture(self):
        try:
            self.recorder = subprocess.Popen(['pw-record', '--rate', '24000', '--channels', '1', '--format', 's16', '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            while not self.stopping.is_set():
                chunk = self.recorder.stdout.read(4800)
                if not chunk:
                    if not self.stopping.is_set():
                        self._status('microphone_error')
                        self.stop()
                    break
                with self.play_lock:
                    muted = self.speaking or time.monotonic() < self.play_until + .35
                if not muted:
                    self._status('listening')
                    self._send({'type': 'input_audio_buffer.append', 'audio': base64.b64encode(chunk).decode('ascii')})
        except Exception:
            if not self.stopping.is_set():
                self._status('microphone_error')
                self.stop()

    def _play(self):
        try:
            self.player = subprocess.Popen(['pw-play', '--rate', '24000', '--channels', '1', '--format', 's16', '-'], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            while not self.stopping.is_set():
                try:
                    chunk = self.audio.get(timeout=.2)
                except queue.Empty:
                    continue
                self.player.stdin.write(chunk)
        except Exception:
            if not self.stopping.is_set():
                self._status('audio_error')
                self.stop()

    def _event(self, event):
        kind = event.get('type')
        if kind == 'session.created':
            self._send(session_update(self.state.names))
        elif kind == 'session.updated':
            self._send({'type': 'response.create', 'response': {'instructions': 'In Pakistani Urdu, warmly welcome the children and ask: ہمارے ساتھ آج کون کون ہے؟ اپنے نام بتائیے۔ Then wait for their answer.'}})
            threading.Thread(target=self._play, daemon=True).start()
            threading.Thread(target=self._capture, daemon=True).start()
        elif kind == 'response.created':
            with self.play_lock:
                self.speaking = True
            self._status('speaking')
        elif kind == 'response.output_audio.delta':
            chunk = base64.b64decode(event.get('delta', ''))
            with self.play_lock:
                self.play_until = max(time.monotonic(), self.play_until) + len(chunk) / 48000
            try:
                self.audio.put(chunk, timeout=1)
            except queue.Full:
                self._status('audio_error')
                self.stop()
        elif kind == 'response.output_audio_transcript.done':
            self.transcript.emit(event.get('transcript', ''))
        elif kind == 'response.done':
            calls = [item for item in event.get('response', {}).get('output', []) if item.get('type') == 'function_call']
            for item in calls:
                try:
                    arguments = json.loads(item.get('arguments', '{}'))
                    if not isinstance(arguments, dict):
                        arguments = {}
                except ValueError:
                    arguments = {}
                result = self.state.apply(item.get('name', ''), arguments)
                self.changed.emit(self.state.snapshot())
                self._send({'type': 'conversation.item.create', 'item': {'type': 'function_call_output',
                            'call_id': item.get('call_id', ''), 'output': json.dumps(result, ensure_ascii=False)}})
            if self.state.stage == 'home':
                self.go_home.emit()
            elif calls:
                self._send(praise_response() if self.state.stage == 'awaiting_advance' else {'type': 'response.create'})
            elif self.state.stage == 'awaiting_advance':
                threading.Thread(target=self._advance_after_speech, daemon=True).start()
            else:
                with self.play_lock:
                    self.speaking = False
        elif kind == 'error':
            self._status('service_error')
            self.stop()

    def _advance_after_speech(self):
        """Keep the current picture visible until the tutor finishes speaking."""
        with self.play_lock:
            delay = max(0.0, self.play_until - time.monotonic()) + 0.35
        if self.stopping.wait(delay):
            return
        if not self.state.advance_picture():
            return
        state = self.state.snapshot()
        self.changed.emit(state)
        if state['stage'] == 'finished':
            instruction = 'In Pakistani Urdu, celebrate the children together and ask if they want to play again or go home.'
        else:
            instruction = (f"Ask {state['child']} in Pakistani Urdu and clear Arabic: {state['question']} "
                           "Do not announce a picture change, and do not name, translate, or reveal the object. Wait for their answer.")
        self._send({'type': 'response.create', 'response': {'instructions': instruction}})

    def run(self):
        key = os.environ.get('OPENAI_API_KEY', '').strip()
        if not key:
            self._status('missing_key')
            return
        self._status('connecting')
        try:
            import websocket
            model = os.environ.get('OPENAI_REALTIME_MODEL', 'gpt-realtime-2.1-mini')
            self.sock = websocket.create_connection(f'wss://api.openai.com/v1/realtime?model={model}',
                                                    header=[f'Authorization: Bearer {key}'], timeout=6)
            self.sock.settimeout(.5)
            self.changed.emit(self.state.snapshot())
            while not self.stopping.is_set():
                try:
                    message = self.sock.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not message:
                    break
                self._event(json.loads(message))
        except Exception:
            if not self.stopping.is_set():
                self._status('service_error')
        finally:
            self.stop()
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
