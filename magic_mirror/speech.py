"""Record only on request and transcribe locally in a separate process."""

import base64
import json
import os
from pathlib import Path
import queue
import select
import subprocess
import threading
import time

import numpy as np
from PySide6.QtCore import QThread, Signal


class SpeechWorker(QThread):
    status = Signal(str)
    result = Signal(int, str, str)

    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        self.jobs = queue.Queue()
        self.stopping = threading.Event()
        self.decoder = None
        self.recorder = None

    def listen(self, request_id: int, language: str) -> None:
        self.jobs.put((request_id, language))

    def stop(self) -> None:
        self.stopping.set()
        self.jobs.put(None)
        for process in (self.recorder, self.decoder):
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass

    def _record(self) -> bytes:
        self.recorder = subprocess.Popen(
            ['pw-record', '--rate', '16000', '--channels', '1', '--format', 's16', '-'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        )
        audio = bytearray()
        started = time.monotonic()
        last_voice = None
        try:
            while not self.stopping.is_set() and time.monotonic() - started < 8.0:
                available, _, _ = select.select([self.recorder.stdout], [], [], 0.2)
                if not available:
                    if self.recorder.poll() is not None:
                        break
                    continue
                chunk = os.read(self.recorder.stdout.fileno(), 3200)
                if not chunk:
                    break
                audio.extend(chunk)
                samples = np.frombuffer(chunk[:len(chunk) - len(chunk) % 2], dtype='<i2').astype(np.float32)
                rms = float(np.sqrt(np.mean(samples * samples))) if len(samples) else 0.0
                if rms > 300:
                    last_voice = time.monotonic()
                if last_voice is not None and time.monotonic() - last_voice > 0.9:
                    break
        finally:
            if self.recorder.poll() is None:
                self.recorder.terminate()
            self.recorder.wait(timeout=2)
            self.recorder = None
        return bytes(audio[:len(audio) - len(audio) % 2])

    def run(self) -> None:
        python = self.settings.get('speech_python', '')
        model = self.settings.get('speech_model', '')
        if not Path(python).is_file() or not Path(model).is_dir():
            self.status.emit('unavailable')
            return
        env = os.environ.copy()
        cudnn = self.settings.get('speech_cudnn', '')
        if cudnn:
            env['LD_LIBRARY_PATH'] = cudnn + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
        script = Path(__file__).with_name('speech_backend.py')
        self.status.emit('loading')
        try:
            if self.stopping.is_set():
                return
            self.decoder = subprocess.Popen([python, '-u', str(script), model], stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                            encoding='utf-8', env=env, bufsize=1)
            if self.stopping.is_set():
                self.decoder.terminate()
                return
            line = self.decoder.stdout.readline()
            ready = json.loads(line) if line else {}
            if ready.get('status') != 'ready':
                self.status.emit('unavailable')
                return
            self.status.emit('ready')
            while not self.stopping.is_set():
                try:
                    job = self.jobs.get(timeout=0.3)
                except queue.Empty:
                    continue
                if job is None:
                    break
                request_id, language = job
                self.status.emit('listening')
                try:
                    audio = self._record()
                    if self.stopping.is_set():
                        break
                    if len(audio) < 3200:
                        self.result.emit(request_id, '', 'microphone')
                        self.status.emit('ready')
                        continue
                    self.status.emit('thinking')
                    request = {'language': language, 'audio': base64.b64encode(audio).decode('ascii')}
                    self.decoder.stdin.write(json.dumps(request) + '\n')
                    self.decoder.stdin.flush()
                    line = self.decoder.stdout.readline()
                    response = json.loads(line) if line else {'error': 'decoder stopped'}
                    self.result.emit(request_id, response.get('text', ''), response.get('error', ''))
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    self.result.emit(request_id, '', str(exc))
                self.status.emit('ready')
        except (OSError, ValueError):
            self.status.emit('unavailable')
        finally:
            self.stop()
            if self.decoder is not None:
                try:
                    self.decoder.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.decoder.kill()
                    self.decoder.wait()
