"""The core loop: one utterance in -> who said it -> text -> notes -> profile.

process_audio(audio)        real mode (mic or band audio, 16 kHz float32)
process_text(speaker, text) demo/test mode, no audio or voice ID needed
"""
import traceback

import config
import profiles

_context: list[str] = []
_last_other: str | None = None
_new_count = 0


def _handle_line(speaker: str, text: str, score=None):
    global _last_other
    if not text:
        return []
    if speaker != config.WEARER_NAME:
        profiles.ensure_person(speaker)
    profiles.add_line(speaker, text, score)
    if speaker != config.WEARER_NAME:
        _last_other = speaker
    _context.append(f"{speaker}: {text}")
    try:
        import extract
        notes = extract.extract(speaker, text, _context, _last_other)
        for n in notes:  # default: a friend's line is about that friend
            if not n.get("person"):
                n["person"] = speaker if speaker != config.WEARER_NAME else _last_other
        added = profiles.add_notes(notes)
        for a in added:
            print(f"  + [{a['person']}] {a['category']}: {a['text']}")
        return added
    except Exception:
        traceback.print_exc()
        return []


def process_text(speaker: str, text: str):
    print(f"{speaker}: {text}")
    return _handle_line(speaker.strip(), text.strip())


def process_audio(audio):
    """Called by the mic/band listener for each finished utterance."""
    global _new_count
    import voice_id
    import transcribe

    seconds = len(audio) / config.SAMPLE_RATE
    if seconds < config.MIN_UTTERANCE_SECONDS:
        return []  # too short to identify a voice reliably
    try:
        name, score, emb = voice_id.identify(audio)
    except ValueError:
        return []
    if name is None:
        # Unknown voice: start a profile for them; rename it in the app later.
        _new_count += 1
        name = f"New person {_new_count}"
        voice_id.enroll_embedding(name, emb)
        print(f"  ? new voice (best match {score:.2f}) -> {name}")
    text = transcribe.transcribe(audio)
    print(f"{name} ({score:.2f}): {text}")
    return _handle_line(name, text, score)
