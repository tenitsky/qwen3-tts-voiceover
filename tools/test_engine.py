"""The Qwen3-TTS engine on CPU with a fake model: script splitting, joining with pauses,
seeds, one clone prompt per script, the voice pool and audio files.
python tools/test_engine.py"""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "engine", ROOT / "custom_nodes/comfyui-qwen3-tts/engine.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
HAVE_FFMPEG = bool(shutil.which("ffmpeg"))
SR = 24000


class FakeTTS:
    """Each part becomes 0.1 s of audio per word, filled with a value per call."""

    def __init__(self):
        self.calls, self.prompts = [], 0

    def _wave(self, text):
        self.calls.append(text)
        return [np.full(int(0.1 * SR * len(text.split())), len(self.calls) / 100,
                        np.float32)], SR

    def generate_custom_voice(self, text, language, speaker, instruct, max_new_tokens):
        assert max_new_tokens == engine.MAX_NEW_TOKENS
        self.last = dict(language=language, speaker=speaker, instruct=instruct)
        return self._wave(text)

    def generate_voice_design(self, text, language, instruct, max_new_tokens):
        self.last = dict(language=language, instruct=instruct)
        return self._wave(text)

    def create_voice_clone_prompt(self, ref_audio, ref_text, x_vector_only_mode):
        self.prompts += 1
        self.clone = dict(ref_text=ref_text, x_vector_only_mode=x_vector_only_mode)
        return ["prompt"]

    def generate_voice_clone(self, text, language, voice_clone_prompt, max_new_tokens):
        assert voice_clone_prompt == ["prompt"]
        return self._wave(text)


SCRIPT = ("Welcome to the show. Today we talk about voices! Are they real? Mostly.\n\n"
          "Second paragraph here, with a single sentence.\n\n\n"
          "Third. " + "A very long sentence that keeps going, " * 30 + "and finally ends.")


class SplitTests(unittest.TestCase):
    def test_parts_respect_the_limit_paragraphs_and_keep_every_word(self):
        for limit in (80, 120, 400, 2000):
            parts = engine.split_script(SCRIPT, limit)
            self.assertTrue(all(len(p) <= limit for p, _ in parts), limit)
            self.assertEqual(" ".join(p for p, _ in parts).split(), SCRIPT.split())
            # Exactly one part ends each of the three paragraphs, the last one included.
            self.assertEqual(sum(end for _, end in parts), 3)
            self.assertTrue(parts[-1][1])

    def test_short_script_is_one_part(self):
        self.assertEqual(engine.split_script("  Hello there.  ", 400), [("Hello there.", True)])
        self.assertEqual(engine.split_script("\n \n", 400), [])

    def test_chinese_sentences_split_without_spaces(self):
        text = "大家好，欢迎收听。" * 20
        parts = engine.split_script(text, 40)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= 40 for p, _ in parts))
        self.assertEqual("".join(p for p, _ in parts).replace(" ", ""), text)


class RenderTests(unittest.TestCase):
    def test_parts_are_joined_with_sentence_and_paragraph_pauses(self):
        tts = FakeTTS()
        parts = engine.split_script(SCRIPT, 120)
        wave, sr = engine.builtin_voice(tts, SCRIPT, "Ryan", "English", "Calm.", seed=3,
                                        max_chars=120, sentence_gap=0.2, paragraph_gap=0.5)
        self.assertEqual(sr, SR)
        self.assertEqual(tts.calls, [p for p, _ in parts])
        speech = sum(int(0.1 * SR * len(p.split())) for p, _ in parts)
        gaps = sum(0.5 if end else 0.2 for _, end in parts[:-1])
        self.assertAlmostEqual(wave.size, speech + gaps * SR, delta=len(parts))
        self.assertEqual(tts.last, dict(language="English", speaker="Ryan", instruct="Calm."))

    def test_auto_language_passes_none_and_unknown_voice_is_refused(self):
        tts = FakeTTS()
        engine.builtin_voice(tts, "Hi.", "Sohee", "Auto")
        self.assertIsNone(tts.last["language"])
        with self.assertRaises(RuntimeError):
            engine.builtin_voice(tts, "Hi.", "Nobody", "Auto")

    def test_seed_makes_sampling_reproducible(self):
        engine._seed(11)
        a = torch.rand(3)
        engine._seed(11)
        self.assertTrue(torch.equal(a, torch.rand(3)))

    def test_design_needs_a_description(self):
        with self.assertRaises(RuntimeError):
            engine.designed_voice(FakeTTS(), "Hi.", "  ")
        tts = FakeTTS()
        engine.designed_voice(tts, "Hi.", "A deep voice.", "German")
        self.assertEqual(tts.last, dict(language="German", instruct="A deep voice."))

    def test_clone_builds_one_prompt_for_the_whole_script(self):
        tts = FakeTTS()
        engine.cloned_voice(tts, SCRIPT, (np.zeros(SR, np.float32), SR), "Hello there.",
                            max_chars=80)
        self.assertEqual(tts.prompts, 1)
        self.assertGreater(len(tts.calls), 3)
        self.assertEqual(tts.clone, dict(ref_text="Hello there.", x_vector_only_mode=False))
        tts = FakeTTS()
        engine.cloned_voice(tts, "Hi.", (np.zeros(SR, np.float32), SR), "  ")
        self.assertEqual(tts.clone, dict(ref_text=None, x_vector_only_mode=True))

    def test_empty_script_is_refused(self):
        with self.assertRaises(RuntimeError):
            engine.builtin_voice(FakeTTS(), "   ", "Ryan")


class PoolTests(unittest.TestCase):
    def test_pool_lists_builtin_voices_first_and_reads_transcripts(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("zeta", "Sohee", "Ryan", "Ryan_en", "Vivian_en", "Vivian", "alpha"):
                Path(d, name + ".flac").write_bytes(b"x")
            Path(d, "notes.md").write_text("ignored")
            Path(d, "Vivian.txt").write_text("大家好。\n", encoding="utf-8")
            self.assertEqual(engine.pool_voices(d),
                             ["Ryan", "Vivian", "Sohee", "Ryan_en", "Vivian_en", "alpha", "zeta"])
            self.assertEqual(engine.pool_entry(d, "Vivian")[1], "大家好。")
            self.assertEqual(engine.pool_entry(d, "zeta")[1], "")
            with self.assertRaises(RuntimeError):
                engine.pool_entry(d, "missing")
        self.assertEqual(engine.pool_voices("/no/such/folder"), [])

    def test_shipped_pool_has_every_builtin_voice_with_transcripts(self):
        pool = ROOT / "samples" / "voices"
        names = engine.pool_voices(str(pool))
        for speaker, (native, _) in engine.SPEAKERS.items():
            self.assertIn(speaker, names)
            self.assertTrue((pool / f"{speaker}.txt").read_text(encoding="utf-8").strip())
            if native != "English":
                self.assertIn(speaker + "_en", names)

    def test_safe_names(self):
        self.assertEqual(engine.safe_name(" My Voice #2 "), "My_Voice_2")
        with self.assertRaises(RuntimeError):
            engine.safe_name("  ##  ")

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg required")
    def test_audio_round_trip_in_every_format(self):
        tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
        with tempfile.TemporaryDirectory() as d:
            for ext in (".wav", ".flac", ".mp3"):
                path = str(Path(d, "t" + ext))
                engine.write_audio(tone, SR, path)
                back, sr = engine.read_audio(path)
                self.assertEqual(sr, SR)
                self.assertAlmostEqual(back.size / SR, 1.0, delta=0.06)
                self.assertGreater(float(np.abs(back).max()), 0.25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
