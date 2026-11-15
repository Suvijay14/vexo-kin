#!/usr/bin/env python3
"""Naming scenarios A/B/C without band or OpenAI (mocked extract + embeddings)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import config
import naming
import pipeline
import profiles
import voice_id


def _reset():
    pipeline._context.clear()
    pipeline._last_other = None
    naming.reset_state()


def _fake_extract(speaker, text, context, other):
    import naming as N

    text_l = text.lower()
    if "pottery" in text_l:
        N.observe(speaker, None, None)
        return [{
            "category": "wish",
            "person": speaker,
            "text": "Wants to try pottery",
            "quote": text,
        }]
    if "suvijay" in text_l and speaker == config.WEARER_NAME:
        N.observe(speaker, "Suvijay", None)
        return []
    if speaker == config.WEARER_NAME and "leo" in text_l and "hi" in text_l:
        N.observe(speaker, "Leo", None)
        return []
    if speaker.startswith("New person") and "weather" in text_l:
        N.observe(speaker, None, None)
        return []
    if speaker == config.WEARER_NAME and "send you that article" in text_l:
        N.observe(speaker, None, None)
        return [{
            "category": "follow_up",
            "person": other or "Leo",
            "text": "Send the article they mentioned",
            "quote": text,
        }]
    if speaker == "Leo":
        N.observe(speaker, None, None)
        return []
    N.observe(speaker, None, None)
    return []


class NamingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        config.PROFILES_FILE = root / "profiles.json"
        config.VOICEPRINTS_FILE = root / "voiceprints.json"
        config.PROFILES_FILE.write_text(json.dumps({"people": {}, "transcript": [], "aliases": {}}))
        config.VOICEPRINTS_FILE.write_text("{}")
        _reset()

    def tearDown(self):
        self.tmp.cleanup()

    @patch("extract.extract", side_effect=_fake_extract)
    def test_scenario_a_greet_then_name(self, _mock):
        emb = np.random.randn(256).astype(np.float32)
        emb /= np.linalg.norm(emb)
        voice_id.enroll_embedding("New person 1", emb)
        pipeline.process_text("New person 1", "I've always wanted to try pottery")
        pipeline.process_text(config.WEARER_NAME, "Hey Suvijay, how's it going?")
        db = profiles.snapshot()
        self.assertIn("Suvijay", db["people"])
        self.assertNotIn("New person 1", db["people"])
        wishes = [n for n in db["people"]["Suvijay"]["notes"] if n["category"] == "wish"]
        self.assertTrue(any("pottery" in n["text"].lower() for n in wishes))

    @patch("extract.extract", side_effect=_fake_extract)
    def test_scenario_b_address_before_voice(self, _mock):
        pipeline.process_text(config.WEARER_NAME, "Hi Leo")
        emb = np.random.randn(256).astype(np.float32)
        emb /= np.linalg.norm(emb)
        voice_id.enroll_embedding("New person 1", emb)
        pipeline.process_text("New person 1", "Yeah the weather is nice today")
        db = profiles.snapshot()
        self.assertIn("Leo", db["people"])
        self.assertIn("Leo", voice_id.enrolled())

    @patch("extract.extract", side_effect=_fake_extract)
    def test_scenario_c_leo_follow_up(self, _mock):
        emb = np.random.randn(256).astype(np.float32)
        emb /= np.linalg.norm(emb)
        voice_id.enroll_embedding("Leo", emb)
        pipeline.process_text("Leo", "That podcast was really good")
        pipeline.process_text(config.WEARER_NAME, "I'll send you that article")
        db = profiles.snapshot()
        follow = [n for n in db["people"]["Leo"]["notes"] if n["category"] == "follow_up"]
        self.assertTrue(follow, "wearer promise should land on Leo")


if __name__ == "__main__":
    unittest.main()