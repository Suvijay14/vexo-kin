"""Shared settings. Keys come from .env only (never put keys in code)."""
import os
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)


def _load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

# Band number from the bag (Vexo-HACK-NN). Required before any band code runs.
BAND_NUMBER = os.environ.get("BAND_NUMBER", "")
BAND_TRANSPORT = os.environ.get("BAND_TRANSPORT", "ble")  # ble, usb or sim

# Voice matching: higher = stricter. Tune on the day (0.70-0.85 typical).
VOICE_THRESHOLD = float(os.environ.get("VOICE_THRESHOLD", "0.75"))
MIN_UTTERANCE_SECONDS = float(os.environ.get("MIN_UTTERANCE_SECONDS", "1.5"))

SAMPLE_RATE = 16000
WEARER_NAME = os.environ.get("WEARER_NAME", "Me")

PROFILES_FILE = DATA / "profiles.json"
VOICEPRINTS_FILE = DATA / "voiceprints.json"
