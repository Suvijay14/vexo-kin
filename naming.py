"""Learn real names from conversation (direct address + self-introduction)."""
from __future__ import annotations

import threading
import time

import config

_lock = threading.RLock()
_last_other: tuple[str, float] | None = None
_pending: tuple[str, float] | None = None
_IGNORE = frozenset({"me", "you", "guys", "everyone", "vexo"})


def _clean(name: str | None) -> str | None:
    if not name or not str(name).strip():
        return None
    first = str(name).strip().split()[0].capitalize()
    return None if first.lower() in _IGNORE else first


def learn(old: str, new: str, how: str = "from the conversation") -> None:
    import profiles
    import voice_id

    profiles.merge_person(old, new)
    voice_id.merge(old, new)
    profiles.add_line("Vexo", f"✨ Learned that {old} is {new} ({how})")
    print(f"✨ Learned that {old} is {new} ({how})")
    global _last_other
    with _lock:
        if _last_other and _last_other[0] == old:
            _last_other = (new, _last_other[1])


def observe(speaker: str, addressed: str | None, self_name: str | None) -> None:
    global _last_other, _pending
    addressed, self_name = _clean(addressed), _clean(self_name)
    now, wearer = time.time(), config.WEARER_NAME
    with _lock:
        pending, last = _pending, _last_other
        if speaker != wearer and self_name and speaker.startswith("New person"):
            learn(speaker, self_name, "they introduced themselves")
            _pending, _last_other = None, (self_name, now)
            return
        if speaker != wearer and speaker.startswith("New person") and pending and now - pending[1] < 60:
            learn(speaker, pending[0], "you addressed them first")
            _pending, _last_other = None, (pending[0], now)
            return
        if speaker != wearer and pending and speaker == pending[0]:
            _pending = None
        if speaker != wearer:
            _last_other = (speaker, now)
        if speaker == wearer and addressed:
            if last and now - last[1] <= 30 and last[0].startswith("New person"):
                learn(last[0], addressed, "you greeted them")
                _pending, _last_other = None, (addressed, now)
            elif not (last and last[0] == addressed):
                _pending = (addressed, now)


def reset_state() -> None:
    """For tests only."""
    global _last_other, _pending
    with _lock:
        _last_other = _pending = None