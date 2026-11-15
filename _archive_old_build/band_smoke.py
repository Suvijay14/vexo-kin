#!/usr/bin/env python3
"""Minimal band test — connect, mic on, plain terminal status. No web, no AI.

  python3 band_smoke.py

Double-tap the band when you see "connecting". Ctrl+C stops and disconnects.
"""
from __future__ import annotations

import signal
import sys
import time

import config


def main() -> None:
    if not config.BAND_NUMBER:
        raise SystemExit("Set BAND_NUMBER in .env (number on your bag).")

    import audio_sources

    audio_sources._kit_on_path()
    from vexo_open.transport import VexoError

    band = None

    def _quit(*_):
        print("\nBand: stopping…", flush=True)
        if band:
            try:
                band.configure(audio=False)
            except Exception:
                pass
            try:
                band.disconnect()
            except Exception:
                pass
        print("Band: idle", flush=True)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _quit)
    signal.signal(signal.SIGTERM, _quit)

    print("Band: connecting — double-tap your band (60s)", flush=True)
    deadline = time.time() + 60
    transport = "serial" if config.BAND_TRANSPORT == "usb" else config.BAND_TRANSPORT

    while time.time() < deadline:
        try:
            from vexo_open.sync import Band

            band = Band.connect(int(config.BAND_NUMBER), transport=transport)
            if band.number != int(config.BAND_NUMBER):
                band.disconnect()
                raise SystemExit(f"Wrong band {band.number}, expected {config.BAND_NUMBER}.")
            break
        except VexoError as e:
            if e.code == "not-found-nearby":
                print("Band: still looking… double-tap the band", flush=True)
                time.sleep(3)
                continue
            raise SystemExit(e.message) from e

    if not band:
        raise SystemExit("Band: could not connect after 60s.")

    print(f"Band: connected (Vexo-HACK-{band.number:02d})", flush=True)
    band.on("audio", lambda _e: None)
    band.configure(audio=True)
    print("Band: listening — mic on (blue light). Ctrl+C to stop.", flush=True)
    print("Band microphone is ON. Tell people nearby: voices go to Deepgram.", flush=True)

    try:
        while True:
            band.wait(1.0)
    finally:
        _quit()


if __name__ == "__main__":
    main()