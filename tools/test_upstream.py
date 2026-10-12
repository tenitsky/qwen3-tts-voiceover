"""Qwen's model and package still match what engine.py assumes: the built-in voices and
languages in the CustomVoice config, and the qwen_tts API the engine calls, imported on
the pinned transformers. Needs network (Hugging Face) and qwen-tts installed.

    python tools/test_upstream.py
"""
import importlib.util
import inspect
import json
from pathlib import Path
import re
import sys
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "engine", ROOT / "custom_nodes/comfyui-qwen3-tts/engine.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
SETUP = (ROOT / "setup.sh").read_text(encoding="utf-8")
CONFIG = ("https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/resolve/main/"
          "config.json")


class UpstreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with urllib.request.urlopen(CONFIG, timeout=60) as r:
            cls.talker = json.load(r)["talker_config"]

    def test_builtin_voices_match_the_model(self):
        self.assertEqual({k.lower() for k in engine.SPEAKERS}, set(self.talker["spk_id"]))
        # Dialect voices are listed with Chinese as their native language.
        dialects = {k for k, v in self.talker["spk_is_dialect"].items() if v}
        self.assertEqual(dialects, {"eric", "dylan"})
        for name, (native, _) in engine.SPEAKERS.items():
            if name.lower() in dialects:
                self.assertEqual(native, "Chinese")

    def test_languages_match_the_model(self):
        model_langs = {k for k in self.talker["codec_language_id"] if "dialect" not in k}
        self.assertEqual({l.lower() for l in engine.LANGUAGES if l != "Auto"}, model_langs)

    def test_qwen_tts_api_on_the_pinned_transformers(self):
        import transformers
        pinned = re.search(r'"transformers==([\d.]+)"', SETUP).group(1)
        self.assertEqual(transformers.__version__, pinned)
        from qwen_tts import Qwen3TTSModel
        import qwen_tts
        version = re.search(r'QWEN_TTS_VERSION:-([\d.]+)', SETUP).group(1)
        from importlib.metadata import version as installed
        self.assertEqual(installed("qwen-tts"), version)
        params = {name: list(inspect.signature(getattr(Qwen3TTSModel, name)).parameters)
                  for name in ("generate_custom_voice", "generate_voice_design",
                               "generate_voice_clone", "create_voice_clone_prompt")}
        for name, expected in {
            "generate_custom_voice": ["text", "language", "speaker", "instruct"],
            "generate_voice_design": ["text", "instruct", "language"],
            "generate_voice_clone": ["text", "language", "voice_clone_prompt"],
            "create_voice_clone_prompt": ["ref_audio", "ref_text", "x_vector_only_mode"],
        }.items():
            for arg in expected:
                self.assertIn(arg, params[name], (name, arg))
        self.assertTrue(callable(Qwen3TTSModel.from_pretrained))
        self.assertTrue(hasattr(qwen_tts, "Qwen3TTSModel"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
