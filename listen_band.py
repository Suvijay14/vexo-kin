#!/usr/bin/env python3
"""Band → who said it + text in this terminal. No browser.

  npm run listen
  python3 listen_band.py

Double-tap the band when prompted. Ctrl+C disconnects."""
from __future__ import annotations

import signal
import sys
import time

import audio_sources
import config
import pipeline

_session: audio_sources.BandSession | None = None


def _stop(*_):
    global _session
    print("\nStopping…", flush=True)
    if _session:
        _session.stop()
        _session = None
    print("Band disconnected.", flush=True)
    sys.exit(0)


def main() -> None:
    if not config.BAND_NUMBER:
        raise SystemExit("Set BAND_NUMBER in .env (number on your bag).")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    audio_sources._kit_on_path()
    from vexo_open.transport import VexoError

    global _session
    print("Connecting — double-tap your band (60s)", flush=True)
    deadline = time.time() + 60

    while time.time() < deadline:
        _session = audio_sources.BandSession(pipeline.process_audio)
        try:
            band = _session.connect()
            _session.start_mic()
            print(f"Listening on band {band.number}. Talk now.", flush=True)
            print("(Each line prints here: Name (score): what they said)\n", flush=True)
            break
        except VexoError as e:
            if e.code == "not-found-nearby":
                print("Still looking… double-tap the band", flush=True)
                time.sleep(3)
                continue
            raise SystemExit(e.message) from e
        except SystemExit as e:
            raise SystemExit(e) from e
        except Exception as e:
            raise SystemExit(str(e)) from e
    else:
        raise SystemExit("Could not find band after 60s.")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()