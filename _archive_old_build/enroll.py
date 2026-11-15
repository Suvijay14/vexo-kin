"""Enroll a person's voice.

  python enroll.py Me --seconds 15          # do this first: the wearer
  python enroll.py Maya --seconds 15        # each friend, in a quiet spot
  python enroll.py Maya --wav maya.wav      # or from a recording (16 kHz mono)
  python enroll.py --list
"""
import argparse
import wave

import numpy as np

import config
import profiles
import voice_id


def load_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        if w.getframerate() != config.SAMPLE_RATE or w.getnchannels() != 1:
            raise SystemExit("Use a 16 kHz mono WAV (ffmpeg -i in.m4a -ar 16000 -ac 1 out.wav)")
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--wav")
    ap.add_argument("--band", action="store_true", help="record through the Vexo band")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list or not a.name:
        print("Enrolled:", voice_id.enrolled() or "nobody yet")
        raise SystemExit
    if a.wav:
        audio = load_wav(a.wav)
    elif a.band:
        from audio_sources import record_band
        audio = record_band(a.seconds)
    else:
        from audio_sources import record_mic
        audio = record_mic(a.seconds)
    voice_id.enroll(a.name, audio)
    if a.name != config.WEARER_NAME:
        profiles.ensure_person(a.name)
    print(f"Enrolled {a.name}. Everyone enrolled: {voice_id.enrolled()}")
