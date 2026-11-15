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
  pipeline.py  audio_sources.py  enroll.py  server.py  run.py  web/index.html
  package.json       <- npm run dev
  .env               <- your keys (copy from .env.example)
```

## Quick start
```bash
python3 -m pip install -r requirements.txt
cp .env.example .env     # then fill in keys + BAND_NUMBER (number on your bag)
git submodule update --init   # fetches the kit into vexo-open-kit/
npm run dev                   # opens the app — press ▶ Start, double-tap the band, talk
```

While the band microphone is on, voices go to Deepgram (deepgram.com). Tell people nearby before you start.

### On the page
1. Press **▶ Start listening**
2. **Double-tap** your band (light blinks blue) so the laptop can find it
3. Talk — profiles and nudges update as you go
4. **+ Add person** — enroll a voice in ~15 seconds (band must be listening first)

## Demo / dev without a band
```bash
python3 server.py
```
Open http://127.0.0.1:5050, type lines like `Maya` / `I've always wanted to try pottery`
and watch Maya's profile fill in.

## Legacy terminal mode (still works)
```bash
python3 enroll.py Me --seconds 15
python3 server.py --band
```

## Band settings
In `.env`: `BAND_NUMBER` (never guess, never 42), `BAND_TRANSPORT=ble` (or `usb` / `sim`).
Tune `VOICE_THRESHOLD` if matching is too loose or too strict (0.70–0.85 typical).

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