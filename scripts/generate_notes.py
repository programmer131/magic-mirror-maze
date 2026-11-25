"""Generate three soft, original bell notes for the cooperative music game."""

import math
from pathlib import Path
import struct
import wave

RATE = 44100
OUT = Path(__file__).resolve().parents[1] / 'assets' / 'sounds'
OUT.mkdir(parents=True, exist_ok=True)
for index, frequency in enumerate((392.0, 493.88, 587.33), 1):
    samples = []
    for i in range(int(RATE * 0.9)):
        t = i / RATE
        envelope = min(1.0, t / 0.012) * math.exp(-4.4 * t)
        sound = (math.sin(math.tau * frequency * t)
                 + 0.33 * math.sin(math.tau * frequency * 2.01 * t)
                 + 0.13 * math.sin(math.tau * frequency * 3.9 * t))
        samples.append(struct.pack('<h', int(15000 * envelope * sound / 1.46)))
    with wave.open(str(OUT / f'note_{index}.wav'), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(b''.join(samples))

melody = (392.0, 493.88, 587.33, 493.88, 587.33, 783.99)
duration = 3.0
samples = []
for i in range(int(RATE * duration)):
    t = i / RATE
    value = 0.0
    for note, frequency in enumerate(melody):
        local = t - note * 0.38
        if 0 <= local < 1.1:
            envelope = min(1.0, local / 0.012) * math.exp(-4.0 * local)
            value += envelope * (math.sin(math.tau * frequency * local) + 0.22 * math.sin(math.tau * frequency * 2 * local))
    samples.append(struct.pack('<h', max(-32767, min(32767, int(value * 10000)))))
with wave.open(str(OUT / 'song.wav'), 'wb') as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(RATE)
    wav.writeframes(b''.join(samples))
