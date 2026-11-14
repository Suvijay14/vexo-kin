"""Speech -> text with Deepgram (nova-3). One call per utterance."""
import io
import wave

import numpy as np
import requests

import config


def to_wav_bytes(audio: np.ndarray) -> bytes:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(config.SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def transcribe(audio: np.ndarray) -> str:
    if not config.DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY missing from .env")
    r = requests.post(
        "https://api.deepgram.com/v1/listen",
        params={"model": "nova-3", "smart_format": "true"},
        headers={
            "Authorization": f"Token {config.DEEPGRAM_API_KEY}",
            "Content-Type": "audio/wav",
        },
        data=to_wav_bytes(audio),
        timeout=30,
    )
    r.raise_for_status()
    alts = r.json()["results"]["channels"][0]["alternatives"]
    return alts[0]["transcript"].strip() if alts else ""
