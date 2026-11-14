"""Turn one line of conversation into friendship notes (OpenAI).

Input:  who said it, what they said, recent context
Output: list of notes: {category, text, quote, event_date, expires_in_days}
"""
import datetime as dt
import json

import config

CATEGORIES = [
    "favorite",      # food, drinks, music, shows, hobbies, teams
    "dislike",
    "wish",          # things they want to try / buy / learn / visit
    "date",          # birthdays, anniversaries, upcoming events
    "life_now",      # goals, projects, what's keeping them busy
    "people_pets",   # partner, family, kids, pets (names!)
    "follow_up",     # things to ask about later, promises the wearer made
    "memory",        # inside jokes, shared moments
    "about",         # how you know them, where they work/study, where you met
    "mood",          # how they're feeling right now (rough day, stressed, excited)
]

SYSTEM = f"""You help a person be a better friend. You read one line from a
conversation captured by their wearable and pull out small things a thoughtful
friend would remember about the OTHER person.

Today is {{today}}. The wearer is called "{config.WEARER_NAME}".

Return JSON: {{{{"notes": [ ... ]}}}} where each note is
{{{{"person": name the note is about,
   "category": one of {CATEGORIES},
   "text": short note in third person, under 12 words,
   "quote": the exact words that support it,
   "event_date": "YYYY-MM-DD" if a specific date/day is mentioned (resolve
                 "Tuesday", "next week" against today), else null,
   "expires_in_days": number if the note goes stale (e.g. busy with finals: 21), else null}}}}

Rules:
- Only real signals. Small talk, logistics and filler -> {{{{"notes": []}}}}.
- If the WEARER says it, only keep promises they make to the other person
  ("I'll send you that article") as category follow_up about that person.
- Something stressful coming up -> also add a follow_up to check in after it.
- Sentiment: if someone clearly sounds like they're having a bad day, stressed,
  sad or drained (or great news to celebrate), add a "mood" note like
  "Having a rough day: presentation moved up", with expires_in_days 1.
  This applies to the wearer too (person = the wearer's name).
  Describe the situation, never a mental-health condition.
  Only when they SAY how they feel ("awful", "so stressed", "so excited").
  Never guess a feeling, never write "likely" or "probably".
- An upcoming event gets exactly two notes: one "date" note (the event) and one
  "follow_up" note ("Ask how the Stripe interview went"). Never repeat the same text.
- NEVER store: health conditions or diagnoses (write "check in about her mom"
  instead of medical details), money/salary/debt, religion, politics,
  sexuality, addresses, passwords, ID numbers, secrets ("don't tell anyone"),
  or anything after someone says to forget it.
"""


def extract(speaker: str, text: str, context: list[str], other_person: str | None):
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing from .env")
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    today = dt.date.today()
    user = (
        "Recent conversation:\n" + "\n".join(context[-6:]) +
        f"\n\nNEW LINE -> {speaker}: {text}\n"
        f"(If the speaker is the wearer, notes are about: {other_person or 'unknown'})"
    )
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM.format(today=f"{today:%A %Y-%m-%d}")},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    notes = [n for n in data.get("notes", []) if n.get("category") in CATEGORIES]
    return notes
