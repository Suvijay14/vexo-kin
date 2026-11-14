"""Who is speaking? Voiceprints with Resemblyzer.

enroll(name, audio)  -> saves a voiceprint for that person
identify(audio)      -> (name, score) or (None, score) if nobody matches

audio = 1-D float32 numpy array, 16 kHz, values in [-1, 1].
Voiceprints are stored on the laptop only (band storage is public).
"""
import json
import numpy as np

import config

_encoder = None


def _enc():
    global _encoder
    if _encoder is None:
        from resemblyzer import VoiceEncoder  # loads a small model on first use
        _encoder = VoiceEncoder("cpu")
    return _encoder


def embed(audio: np.ndarray) -> np.ndarray:
    from resemblyzer import preprocess_wav
    wav = preprocess_wav(audio.astype(np.float32), source_sr=config.SAMPLE_RATE)
    if len(wav) < config.SAMPLE_RATE * 0.8:  # too little actual speech
        raise ValueError("not enough speech in this clip")
    return _enc().embed_utterance(wav)


def _load() -> dict:
    if config.VOICEPRINTS_FILE.exists():
        raw = json.loads(config.VOICEPRINTS_FILE.read_text())
        return {k: np.array(v, dtype=np.float32) for k, v in raw.items()}
    return {}


def _save(prints: dict):
    config.VOICEPRINTS_FILE.write_text(
        json.dumps({k: v.tolist() for k, v in prints.items()})
    )


def enroll(name: str, audio: np.ndarray):
    """Add (or strengthen) a person's voiceprint."""
    prints = _load()
    new = embed(audio)
    if name in prints:  # average with the old one, then re-normalise
        new = prints[name] + new
    prints[name] = new / np.linalg.norm(new)
    _save(prints)


def enroll_embedding(name: str, emb: np.ndarray):
    prints = _load()
    if name in prints:
        emb = prints[name] + emb
    prints[name] = emb / np.linalg.norm(emb)
    _save(prints)


def identify(audio: np.ndarray):
    """Return (name or None, best_score, embedding)."""
    prints = _load()
    emb = embed(audio)
    best_name, best = None, 0.0
    for name, ref in prints.items():
        score = float(np.dot(emb, ref))  # both are unit vectors -> cosine
        if score > best:
            best_name, best = name, score
    if best >= config.VOICE_THRESHOLD:
        return best_name, best, emb
    return None, best, emb


def rename(old: str, new: str):
    prints = _load()
    if old in prints:
        prints[new] = prints.pop(old)
        _save(prints)


def enrolled() -> list:
    return sorted(_load().keys())
