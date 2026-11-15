"""Where audio comes from. Both sources cut speech into utterances (pauses
between speakers) and hand each one to a callback.

- Laptop mic: works now, use it to build and test.
- Vexo band:  Opus packets from the band's AUDIO stream, decoded to PCM.
  Fill in the two TODOs after looking at how the kit's speech.py reads audio.
"""
import queue
import threading

import numpy as np

import config


class Segmenter:
    """Energy-based voice activity detection. Utterance ends after a pause."""

    def __init__(self, on_utterance, pause_s=0.7, max_s=15.0):
        self.on_utterance = on_utterance
        self.pause = int(pause_s * config.SAMPLE_RATE)
        self.max = int(max_s * config.SAMPLE_RATE)
        self.noise = 0.01
        self.buf: list[np.ndarray] = []
        self.silent = 0
        self.speaking = False

    def feed(self, chunk: np.ndarray):
        rms = float(np.sqrt(np.mean(chunk ** 2)) + 1e-9)
        loud = rms > max(0.015, self.noise * 3)
        if not loud:
            self.noise = 0.95 * self.noise + 0.05 * rms  # track room noise
        if loud:
            self.speaking = True
            self.silent = 0
        if self.speaking:
            self.buf.append(chunk)
            if not loud:
                self.silent += len(chunk)
            total = sum(len(c) for c in self.buf)
            if self.silent >= self.pause or total >= self.max:
                audio = np.concatenate(self.buf)
                self.buf, self.silent, self.speaking = [], 0, False
                self.on_utterance(audio)


def _worker(q: "queue.Queue", handle):
    while True:
        audio = q.get()
        try:
            handle(audio)
        except Exception as e:  # keep listening even if one utterance fails
            print("utterance failed:", e)


def start_mic(handle):
    """Listen on the laptop microphone. handle(audio) runs per utterance."""
    import sounddevice as sd

    q: "queue.Queue" = queue.Queue()
    threading.Thread(target=_worker, args=(q, handle), daemon=True).start()
    seg = Segmenter(q.put)

    def cb(indata, frames, time, status):
        seg.feed(indata[:, 0].copy())

    stream = sd.InputStream(samplerate=config.SAMPLE_RATE, channels=1,
                            dtype="float32", blocksize=480, callback=cb)
    stream.start()
    print("Laptop mic is ON. Tell people nearby their voices are being recorded.")
    return stream


def record_mic(seconds: float) -> np.ndarray:
    import sounddevice as sd
    print(f"Recording {seconds:.0f}s from the laptop mic... talk naturally.")
    audio = sd.rec(int(seconds * config.SAMPLE_RATE), samplerate=config.SAMPLE_RATE,
                   channels=1, dtype="float32")
    sd.wait()
    return audio[:, 0]


def _kit_on_path():
    import os
    import sys
    kit_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vexo-open-kit", "python")
    if kit_python not in sys.path:
        sys.path.insert(0, kit_python)


class BandSession:
    """One band connection: live utterances or enrollment on the same link."""

    def __init__(self, handle):
        self.handle = handle
        self.band = None
        self._decoder = None
        self._seg = None
        self._q = None
        self._live = True
        self._enrolling = False
        self._enroll_buf: list[np.ndarray] = []
        self._lock = threading.Lock()

    def _on_audio(self, event):
        pcm = self._decoder.feed(event)
        if not pcm:
            return
        chunk = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        with self._lock:
            if self._enrolling:
                self._enroll_buf.append(chunk)
            elif self._live:
                self._seg.feed(chunk)

    def connect(self):
        if not config.BAND_NUMBER:
            raise SystemExit("Set BAND_NUMBER in .env (the number on your bag). Never guess, never 42.")
        _kit_on_path()
        from vexo_open.sync import Band
        from vexo_open.audio import PcmDecoder

        self._decoder = PcmDecoder()
        self._q = queue.Queue()
        threading.Thread(target=_worker, args=(self._q, self.handle), daemon=True).start()
        self._seg = Segmenter(self._q.put)

        transport = "serial" if config.BAND_TRANSPORT == "usb" else config.BAND_TRANSPORT
        band = Band.connect(int(config.BAND_NUMBER), transport=transport)
        if band.number != int(config.BAND_NUMBER):  # kit rule: always verify it's OUR band
            band.disconnect()
            raise SystemExit(f"Connected to band {band.number}, not ours ({config.BAND_NUMBER}). Stopped.")
        band.on("audio", self._on_audio)
        self.band = band
        return band

    def start_mic(self):
        if not self.band:
            raise RuntimeError("not connected")
        self.band.configure(audio=True)
        print("Band microphone is ON (blue light). Tell people nearby: voices go to Deepgram.")

    def set_live(self, on: bool):
        with self._lock:
            self._live = on

    def record_seconds(self, seconds: float) -> np.ndarray:
        if not self.band:
            raise RuntimeError("not connected")
        with self._lock:
            self._live = False
            self._enrolling = True
            self._enroll_buf = []
        try:
            self.band.wait(seconds)
        finally:
            with self._lock:
                self._enrolling = False
                chunks = self._enroll_buf
                self._enroll_buf = []
                self._live = True
        if not chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(chunks)

    def stop(self):
        band = self.band
        self.band = None
        if not band:
            return
        try:
            band.configure(audio=False)
        except Exception:
            pass
        try:
            band.disconnect()
        except Exception:
            pass


def stop_band(band) -> None:
    """Turn the mic off and release the band."""
    if band is None:
        return
    try:
        band.configure(audio=False)
    except Exception:
        pass
    try:
        band.disconnect()
    except Exception:
        pass


def start_band(handle):
    """Listen through the Vexo band's microphone (Opus 16 kHz, 20 ms packets).

    Same calls as the kit's examples/python/speech.py: band.on("audio", ...) and
    band.configure(audio=True). The kit's PcmDecoder turns Opus into plain sound.
    """
    session = BandSession(handle)
    band = session.connect()
    print(f"Connected to band {band.number}.")
    session.start_mic()
    start_band._session = session  # keep session alive for handlers
    return band


start_band._session = None


def record_band(seconds: float) -> np.ndarray:
    """Record from the band for enrollment (so voiceprints match the band's mic)."""
    if not config.BAND_NUMBER:
        raise SystemExit("Set BAND_NUMBER in .env (the number on your bag). Never guess, never 42.")
    _kit_on_path()
    from vexo_open.sync import Band
    from vexo_open.audio import PcmDecoder

    decoder, chunks = PcmDecoder(), []
    transport = "serial" if config.BAND_TRANSPORT == "usb" else config.BAND_TRANSPORT
    band = Band.connect(int(config.BAND_NUMBER), transport=transport)
    if band.number != int(config.BAND_NUMBER):  # kit rule: always verify it's OUR band
        band.disconnect()
        raise SystemExit(f"Connected to band {band.number}, not ours ({config.BAND_NUMBER}). Stopped.")
    band.on("audio", lambda e: chunks.append(decoder.feed(e)))
    print(f"Band mic ON for {seconds:.0f}s (blue light). Talk naturally.")
    try:
        band.configure(audio=True)
        band.wait(seconds)
        band.configure(audio=False)
    finally:
        band.disconnect()
    pcm = b"".join(c for c in chunks if c)
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
