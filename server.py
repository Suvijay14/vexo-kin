"""Run the app.

  python server.py            text mode: type lines in the page (no audio)
  python server.py --mic      listen on the laptop mic
  python server.py --band     listen through the Vexo band

  npm run dev                 same server, band starts from the web page

Then open http://127.0.0.1:5050
"""
import argparse
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

import config
import pipeline
import profiles

app = Flask(__name__, static_folder="web")

_LEGACY_BAND = None


class BandController:
    """Band lifecycle for the web UI: idle, connecting, listening, error."""

    def __init__(self):
        self._lock = threading.Lock()
        self.status = "idle"
        self.message = ""
        self._session = None
        self._thread = None
        self._stop_connect = threading.Event()
        self.enroll_name = ""
        self.enroll_seconds_left = 0

    def snapshot(self):
        with self._lock:
            return {
                "status": self.status,
                "message": self.message,
            }

    def enroll_snapshot(self):
        with self._lock:
            if not self.enroll_name:
                return None
            return {"name": self.enroll_name, "seconds_left": self.enroll_seconds_left}

    def _set(self, status: str, message: str = ""):
        with self._lock:
            self.status = status
            self.message = message

    def start(self):
        with self._lock:
            if self.status not in ("idle", "error"):
                return False, "Already started"
            self._stop_connect.clear()
            self._set("connecting", "Double-tap your band (light blinks blue)")
            self._thread = threading.Thread(target=self._connect_worker, daemon=True)
            self._thread.start()
        print("Band: connecting — double-tap your band", flush=True)
        return True, ""

    def _connect_worker(self):
        import audio_sources

        _kit_on_path = audio_sources._kit_on_path
        _kit_on_path()
        from vexo_open.transport import VexoError

        deadline = time.time() + 60

        while time.time() < deadline and not self._stop_connect.is_set():
            session = audio_sources.BandSession(pipeline.process_audio)
            try:
                band = session.connect()
                session.start_mic()
                with self._lock:
                    self._session = session
                    self._set("listening", "")
                print(f"Band: connected (Vexo-HACK-{band.number:02d})", flush=True)
                print("Band: listening — mic on.", flush=True)
                return
            except VexoError as e:
                if e.code == "not-found-nearby":
                    self._set("connecting", "Double-tap your band (light blinks blue)")
                    print("Band: still looking… double-tap the band", flush=True)
                    if self._stop_connect.wait(3):
                        return
                    continue
                self._set("error", e.message if hasattr(e, "message") else str(e))
                print(f"Band: error — {e.message}", flush=True)
                return
            except SystemExit as e:
                self._set("error", str(e) if str(e) else "Set BAND_NUMBER in .env")
                return
            except Exception as e:
                self._set("error", str(e))
                return

        if self._stop_connect.is_set():
            self._set("idle", "")
            print("Band: stopped", flush=True)
        else:
            self._set(
                "error",
                "Could not find your band after 60 seconds. Double-tap it and press Start again.",
            )
            print("Band: could not connect after 60s", flush=True)

    def stop(self):
        self._stop_connect.set()
        with self._lock:
            session = self._session
            self._session = None
            self.enroll_name = ""
            self.enroll_seconds_left = 0
        if session:
            session.stop()
        else:
            import audio_sources
            if _LEGACY_BAND:
                audio_sources.stop_band(_LEGACY_BAND)
        self._set("idle", "")
        print("Band: stopped", flush=True)

    def shutdown(self):
        self.stop()

    def enroll(self, name: str, seconds: float = 15):
        with self._lock:
            if self.status != "listening" or not self._session:
                return False, "Press Start first."
            if self.enroll_name:
                return False, "Enrollment already in progress."
            session = self._session

        def _work():
            import voice_id

            stop_tick = threading.Event()

            def _tick():
                end = time.time() + seconds
                with self._lock:
                    self.enroll_name = name
                    self.enroll_seconds_left = max(1, int(seconds))
                while not stop_tick.is_set() and time.time() < end:
                    with self._lock:
                        self.enroll_seconds_left = max(0, int(end - time.time() + 0.99))
                    time.sleep(0.2)
                with self._lock:
                    self.enroll_seconds_left = 0

            tick = threading.Thread(target=_tick, daemon=True)
            tick.start()
            try:
                print(f"Recording {seconds:.0f}s for enrollment — talk naturally.")
                audio = session.record_seconds(seconds)
                voice_id.enroll(name, audio)
                if name != config.WEARER_NAME:
                    profiles.ensure_person(name)
                print(f"Enrolled {name}.")
            finally:
                stop_tick.set()
                tick.join(timeout=1)
                with self._lock:
                    self.enroll_name = ""
                    self.enroll_seconds_left = 0

        threading.Thread(target=_work, daemon=True).start()
        return True, ""


band_controller = BandController()


@app.get("/")
def index():
    resp = send_from_directory("web", "index.html")
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.get("/api/state")
def state():
    db = profiles.snapshot()
    enroll = band_controller.enroll_snapshot()
    out = {
        "people": db["people"],
        "transcript": db["transcript"][-30:],
        "nudges": profiles.nudges(),
        "wearer": config.WEARER_NAME,
        "band": band_controller.snapshot(),
    }
    if enroll:
        out["enroll"] = enroll
    return jsonify(out)


@app.post("/api/band/start")
def band_start():
    if config.BAND_NUMBER == "":
        return jsonify(ok=False, error="Set BAND_NUMBER in .env (the number on your bag)."), 400
    ok, err = band_controller.start()
    if not ok:
        return jsonify(ok=False, error=err), 409
    return jsonify(ok=True)


@app.post("/api/band/stop")
def band_stop():
    band_controller.stop()
    return jsonify(ok=True)


@app.post("/api/enroll")
def enroll():
    d = request.get_json(force=True) or {}
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify(ok=False, error="Name required"), 400
    seconds = float(d.get("seconds", 15))
    ok, err = band_controller.enroll(name, seconds)
    if not ok:
        return jsonify(ok=False, error=err), 400
    return jsonify(ok=True)


@app.post("/api/say")
def say():
    """Demo/test mode: pretend someone said a line."""
    d = request.get_json(force=True)
    threading.Thread(target=pipeline.process_text,
                     args=(d.get("speaker", ""), d.get("text", "")), daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/rename")
def rename():
    d = request.get_json(force=True)
    profiles.rename_person(d["old"], d["new"])
    try:
        import voice_id
        voice_id.rename(d["old"], d["new"])
    except Exception:
        pass
    return jsonify(ok=True)


@app.post("/api/star")
def star():
    profiles.toggle_star(request.get_json(force=True)["person"])
    return jsonify(ok=True)


@app.post("/api/delete_note")
def delete_note():
    d = request.get_json(force=True)
    profiles.delete_note(d["person"], d["id"])
    return jsonify(ok=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mic", action="store_true")
    ap.add_argument("--band", action="store_true")
    a = ap.parse_args()
    if a.mic or a.band:
        import audio_sources
        start = audio_sources.start_band if a.band else audio_sources.start_mic
        _LEGACY_BAND = start(pipeline.process_audio)
    print("Open http://127.0.0.1:5050")
    try:
        app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
    finally:
        if a.band and _LEGACY_BAND:
            import audio_sources
            audio_sources.stop_band(_LEGACY_BAND)