"""Local profile store + nudges. Saved on the laptop in data/profiles.json."""
from __future__ import annotations

import datetime as dt
import json
import threading
import uuid

import config

_lock = threading.Lock()


def _load() -> dict:
    if config.PROFILES_FILE.exists():
        db = json.loads(config.PROFILES_FILE.read_text())
        db.setdefault("aliases", {})
        return db
    return {"people": {}, "transcript": [], "aliases": {}}


def _resolve(db: dict, name: str) -> str:
    aliases = db.get("aliases", {})
    seen: set[str] = set()
    while name in aliases and name not in seen:
        seen.add(name)
        name = aliases[name]
    return name


def resolve_name(name: str | None) -> str | None:
    if not name:
        return None
    with _lock:
        return _resolve(_load(), name)


def _save(db: dict):
    config.PROFILES_FILE.write_text(json.dumps(db, indent=2))


def snapshot() -> dict:
    with _lock:
        return _load()


def ensure_person(name: str):
    with _lock:
        db = _load()
        if name not in db["people"]:
            db["people"][name] = {
                "name": name,
                "first_seen": dt.datetime.now().isoformat(timespec="minutes"),
                "last_seen": None,
                "notes": [],
            }
            _save(db)


def add_line(speaker: str, text: str, score: float | None = None):
    with _lock:
        db = _load()
        db["transcript"].append({
            "time": dt.datetime.now().isoformat(timespec="seconds"),
            "speaker": speaker, "text": text,
            "score": round(score, 2) if score is not None else None,
        })
        db["transcript"] = db["transcript"][-200:]
        if speaker in db["people"]:
            db["people"][speaker]["last_seen"] = dt.datetime.now().isoformat(timespec="minutes")
        _save(db)


def _similar(a: str, b: str) -> bool:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) > 0.6


def add_notes(notes: list[dict]) -> list[dict]:
    """Merge notes into profiles. Returns the notes that were actually new."""
    added = []
    with _lock:
        db = _load()
        today = dt.date.today()
        for n in notes:
            person = n.get("person")
            if person:
                person = _resolve(db, person)
                n["person"] = person
            if not person or (person == config.WEARER_NAME and n["category"] != "mood"):
                continue
            if n["category"] == "mood":
                n["expires_in_days"] = 1  # bad days never become permanent notes
            p = db["people"].setdefault(person, {
                "name": person, "first_seen": dt.datetime.now().isoformat(timespec="minutes"),
                "last_seen": None, "notes": [],
            })
            if any(_similar(x["text"], n["text"]) and x["category"] == n["category"]
                   for x in p["notes"]):
                continue  # duplicate
            exp = n.get("expires_in_days")
            note = {
                "id": uuid.uuid4().hex[:8],
                "category": n["category"],
                "text": n["text"],
                "quote": n.get("quote", ""),
                "heard": today.isoformat(),
                "event_date": n.get("event_date"),
                "expires": (today + dt.timedelta(days=int(exp))).isoformat() if exp else None,
            }
            p["notes"].append(note)
            added.append({**note, "person": person})
        _save(db)
    return added


def delete_note(person: str, note_id: str):
    with _lock:
        db = _load()
        if person in db["people"]:
            db["people"][person]["notes"] = [
                n for n in db["people"][person]["notes"] if n["id"] != note_id]
            _save(db)


def rename_person(old: str, new: str):
    with _lock:
        db = _load()
        if old in db["people"] and new not in db["people"]:
            p = db["people"].pop(old)
            p["name"] = new
            db["people"][new] = p
            for line in db["transcript"]:
                if line["speaker"] == old:
                    line["speaker"] = new
            _save(db)


def merge_person(old: str, new: str) -> None:
    with _lock:
        db = _load()
        db.setdefault("aliases", {})
        db["aliases"][old] = new
        old_p = db["people"].pop(old, None)
        if old_p:
            new_p = db["people"].get(new)
            if new_p:
                for n in old_p.get("notes", []):
                    if not any(
                        _similar(n["text"], x["text"]) and n["category"] == x["category"]
                        for x in new_p["notes"]
                    ):
                        new_p["notes"].append(n)
                if old_p.get("first_seen") and (
                    not new_p.get("first_seen") or old_p["first_seen"] < new_p["first_seen"]
                ):
                    new_p["first_seen"] = old_p["first_seen"]
                if old_p.get("last_seen") and (
                    not new_p.get("last_seen")
                    or (new_p.get("last_seen") or "") < (old_p.get("last_seen") or "")
                ):
                    new_p["last_seen"] = old_p["last_seen"]
                if old_p.get("starred"):
                    new_p["starred"] = True
            else:
                old_p["name"] = new
                db["people"][new] = old_p
        for line in db["transcript"]:
            if line["speaker"] == old:
                line["speaker"] = new
        _save(db)


TREAT_WORDS = ("coffee", "matcha", "tea", "latte", "boba", "chocolate", "cookie",
               "cake", "ice cream", "dessert", "pastry", "donut", "candy", "snack",
               "pizza", "sushi", "taco", "ramen", "smoothie", "croissant")


def is_close(p: dict) -> bool:
    """Close = you starred them, or you've learned a lot about them."""
    return p.get("starred") or len([n for n in p["notes"] if n["category"] != "mood"]) >= 3


def _treat_for(p: dict) -> str | None:
    favs = [n for n in p["notes"] if n["category"] in ("favorite", "wish")]
    for n in favs:  # prefer a food/drink they love
        if any(w in n["text"].lower() for w in TREAT_WORDS):
            return n["text"]
    return favs[0]["text"] if favs else None


def toggle_star(person: str):
    with _lock:
        db = _load()
        if person in db["people"]:
            p = db["people"][person]
            p["starred"] = not p.get("starred")
            _save(db)


def nudges(today: dt.date | None = None) -> list[dict]:
    """Things worth acting on now: moods, events in the next 7 days, follow-ups."""
    today = today or dt.date.today()
    out = []
    db = snapshot()
    for p in db["people"].values():
        for n in p["notes"]:
            if n.get("expires") and n["expires"] < today.isoformat():
                continue
            if n["category"] == "mood" and n["heard"] >= (today - dt.timedelta(days=1)).isoformat():
                treat = _treat_for(p)
                if p["name"] == config.WEARER_NAME:
                    msg = "Sounds like a long day. Take a break and get yourself a sweet treat."
                elif is_close(p):
                    msg = (f"Cheer them up with something they love ({treat.lower()})." if treat
                           else "Send a quick message or bring a sweet treat.")
                else:
                    msg = "Maybe check in on them later."
                out.append({"person": p["name"], "when": "right now", "days": -10,
                            "note": n, "suggestion": msg})
                continue
            if n.get("event_date"):
                d = dt.date.fromisoformat(n["event_date"])
                days = (d - today).days
                if 0 <= days <= 7:
                    when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
                    out.append({"person": p["name"], "when": when, "days": days, "note": n})
                elif -2 <= days < 0 and n["category"] in ("date", "follow_up", "life_now"):
                    out.append({"person": p["name"], "when": "just happened", "days": days, "note": n})
            elif n["category"] == "follow_up":
                out.append({"person": p["name"], "when": "next time you talk", "days": 99, "note": n})
    out.sort(key=lambda x: (x["days"], x["note"]["category"] != "follow_up"))
    seen, unique = set(), []
    for x in out:  # one nudge per event, one mood per person
        n = x["note"]
        key = (x["person"], "mood") if n["category"] == "mood" else \
              (x["person"], n.get("event_date") or n["text"])
        if key not in seen:
            seen.add(key)
            unique.append(x)
    return unique
