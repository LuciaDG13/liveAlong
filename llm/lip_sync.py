import base64
import json
import subprocess
import tempfile
import uuid
from pathlib import Path

from llm import tts_service


RHUBARB_PATH = "rhubarb"
""" A changer avec le vrai chemin """

def synthesize_speech_with_lip_sync (text: str) -> dict:
    audio_b64 = tts_service.synthesize_speech(text)
    if not audio_b64: 
        return {"audio":None, "mouthCues": []}

    tmp_dir = Path(tempfile.gettempdir())
    job_id = uuid.uuid4().hex
    wav_path = tmp_dir / f"speech-{job_id}.wav"
    cues_path = tmp_dir / f"cues-{job_id}.json"
    mouth_cues = []
 
    try:
        wav_path.write_bytes(base64.b64decode(audio_b64))
 
        subprocess.run(
            [RHUBARB_PATH, "-f", "json", "-o", str(cues_path), str(wav_path)],
            check=True,
            capture_output=True,
        )
        cues_json = json.loads(cues_path.read_text(encoding="utf-8"))
        mouth_cues = cues_json.get("mouthCues", [])
 
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[lip_sync] Rhubarb a échoué, animation ignorée : {e}")
 
    finally:
        wav_path.unlink(missing_ok=True)
        cues_path.unlink(missing_ok=True)
 
    return {"audio": audio_b64, "mouthCues": mouth_cues}