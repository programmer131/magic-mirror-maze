"""Local speech process. Audio is supplied in memory and is never saved."""

import base64
import json
import sys

import numpy as np
from faster_whisper import WhisperModel


def send(payload):
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def main():
    try:
        model = WhisperModel(sys.argv[1], device='cuda', compute_type='float16', local_files_only=True)
        send({'status': 'ready'})
    except Exception as exc:
        send({'status': 'error', 'message': str(exc)})
        return 1
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get('stop'):
                break
            samples = np.frombuffer(base64.b64decode(request['audio']), dtype='<i2').astype(np.float32) / 32768.0
            if not len(samples) or float(np.max(np.abs(samples))) < 0.005:
                send({'text': ''})
                continue
            segments, _ = model.transcribe(samples, language=request['language'], beam_size=1,
                                           vad_filter=False, condition_on_previous_text=False)
            send({'text': ' '.join(segment.text.strip() for segment in segments).strip()})
        except Exception as exc:
            send({'error': str(exc)})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
