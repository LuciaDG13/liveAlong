import io
import base64
import numpy as np
import soundfile as sf
from kokoro import KPipeline

pipeline = None
SAMPLE_RATE = 24000

try:
    pipeline = KPipeline(lang_code='a')
except Exception as exc:
    print(f"Unable to initialize TTS pipeline: {exc}")


def synthesize_speech(text):
    if not text or not text.strip():
        return None

    if pipeline is None:
        return None

    try:
        generator = pipeline(text, voice='af_heart', speed=1.0)

        audio_segments = [audio for (_, _, audio) in generator]

        if not audio_segments:
            return None

        full_audio = np.concatenate(audio_segments)

        buffer = io.BytesIO()
        sf.write(buffer, full_audio, SAMPLE_RATE, format="WAV")
        buffer.seek(0)

        audio_bytes = buffer.read()
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        return audio_base64

    except Exception as e:
        print(f"Error during speech synthesis: {e}")
        return None