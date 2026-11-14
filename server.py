"""Run the app.

  python server.py            text mode: type lines in the page (no audio)
  python server.py --mic      listen on the laptop mic
  python server.py --band     listen through the Vexo band

Then open http://127.0.0.1:5050
"""
import argparse
import threading

from flask import Flask, jsonify, request, send_from_directory

import config
import pipeline
import profiles

app = Flask(__name__, static_folder="web")


@app.get("/")
def index():
    return send_from_directory("web", "index.html")


@app.get("/api/state")
def state():
    db = profiles.snapshot()
    return jsonify({
        "people": db["people"],
        "transcript": db["transcript"][-30:],
        "nudges": profiles.nudges(),
        "wearer": config.WEARER_NAME,
    })


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
        _keep = start(pipeline.process_audio)
    print("Open http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
