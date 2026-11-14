# Vexo Kin
The emotional memory layer for Vexo.

Profiles of the people you love, recognized by voice.

Vexo hears a conversation → recognizes who's talking by their voice →
pulls out what a good friend would remember → updates that person's profile →
nudges you at the right moment.

```
band mic ─► cut into utterances ─► voiceprint match (Resemblyzer, local) ─► "Maya"
                                  └► Deepgram nova-3 ─► text
                                                  └► OpenAI extraction ─► profile notes ─► web app + nudges
```

## Accounts / keys you need
| Service | What for | Where it comes from |
|---|---|---|
| Deepgram | speech → text | Organizers give each team a key |
| OpenAI | text → profile notes | Organizers give each team a key |
| Resemblyzer | voice → who is speaking | Free, runs on your laptop, no key |

Keys go in `.env` only. Never in code, git, logs, chats or band storage.

## Folder layout (the kit requires this exact name)
```
vexo-people/
  vexo-open-kit/     <- the kit, unchanged
  config.py  voice_id.py  transcribe.py  extract.py  profiles.py
  pipeline.py  audio_sources.py  enroll.py  server.py  web/index.html
  .env               <- your keys (copy from .env.example)
```

## Step 1: install (10 min)
```bash
python3 -m pip install -r requirements.txt
cp .env.example .env     # then fill in the two keys
git submodule update --init  # fetches the kit into vexo-open-kit/
python3 vexo-open-kit/examples/python/check_keys.py   # the kit's key checker
```

## Step 2: text mode, no audio (works immediately)
```bash
python3 server.py
```
Open http://127.0.0.1:5050, type lines like `Maya` / `I've always wanted to try pottery`
and watch Maya's profile fill in. This tests extraction, profiles and nudges.

## Step 3: voices with the laptop mic
```bash
python3 enroll.py Me --seconds 15      # the wearer first
python3 enroll.py Maya --seconds 15    # each friend, in a quiet corner
python3 server.py --mic
```
Talk in turns (pause about 1 second between speakers). Unknown voices become
"New person 1"; click "Who is this?" to name them.
Tune `VOICE_THRESHOLD` in `.env`: wrong names → raise it; "New person" too often → lower it.

## Step 4: switch to the Vexo band
Uses the same calls as the kit's `examples/python/speech.py`: `band.on("audio", ...)`,
`band.configure(audio=True)` and the kit's `PcmDecoder`.
1. In `.env`: `BAND_NUMBER=7` for Vexo-HACK-07 (the number on your bag; never guess, never 42).
   `BAND_TRANSPORT=ble` (Bluetooth), `usb` (cable) or `sim` (pretend band, sends silence).
2. Double-tap the band so it can be found (60 seconds).
3. Re-enroll voices through the band (different mic = slightly different voice):
   `python3 enroll.py Me --band --seconds 15`, then each friend.
4. `python3 server.py --band`

## Kit rules to keep
- Only connect to your own band; don't disable the wrong-band check. Don't touch firmware.
- Tell people nearby before the mic is on (the code prints a notice; keep it).
- Mic is exclusive: don't run the kit's `speech.py` at the same time.
- Profiles and voiceprints stay in `data/` on the laptop. Band storage is public, so nothing goes there.

## Demo tips
- 2–3 enrolled people max, short turns, pause between speakers.
- Script the conversation so it hits: a wish, a date ("interview Tuesday"), a pet name, a promise.
- Record a backup video once it works.
- If voice matching is shaky on stage, use text mode for the rest of the demo.
