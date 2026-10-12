"""
Qwen3-TTS - voiceovers of any length in ComfyUI with Qwen's official qwen_tts package
(Apache-2.0): the 9 built-in voices, voices designed from a description, and voices
cloned from a pool of reference clips. engine.py does the work; these are thin nodes.
"""

import os

import numpy as np
import torch

import folder_paths

from . import engine

CATEGORY = "Qwen3-TTS"
POOL = "voices"   # ComfyUI/input/voices: the voice pool
_loaded = {}      # the one loaded model: (folder, attention) -> Qwen3TTSModel


def models_dir():
    return os.environ.get("QWEN3_TTS_MODELS") or os.path.join(folder_paths.models_dir,
                                                              "qwen3-tts")


def pool_dir():
    return os.path.join(folder_paths.get_input_directory(), POOL)


def _progress(total):
    try:
        import comfy.utils
        bar = comfy.utils.ProgressBar(total)
    except Exception:  # pragma: no cover - outside ComfyUI
        bar = None

    def step(i, n):
        try:
            import comfy.model_management
            comfy.model_management.throw_exception_if_processing_interrupted()
        except ImportError:  # pragma: no cover
            pass
        if bar:
            bar.update_absolute(i + 1, n)
    return step


def _audio(wave, sr):
    """Mono numpy -> ComfyUI AUDIO."""
    return {"waveform": torch.from_numpy(np.asarray(wave, np.float32)).reshape(1, 1, -1),
            "sample_rate": int(sr)}


def _mono(audio):
    """ComfyUI AUDIO -> (mono numpy, sr)."""
    w = audio["waveform"]
    w = w[0] if w.dim() == 3 else w
    return w.float().mean(dim=0).cpu().numpy(), int(audio["sample_rate"])


def _pool_choices():
    return engine.pool_voices(pool_dir()) or ["(voice pool is empty)"]


GAP_INPUTS = {
    "max_chars_per_part": ("INT", {
        "default": 400, "min": 80, "max": 2000, "step": 10,
        "tooltip": "Long scripts are rendered in parts of at most this many characters, "
                   "cut at paragraph and sentence ends, then joined."}),
    "sentence_gap": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 3.0, "step": 0.05,
                               "tooltip": "Silence (s) between parts inside a paragraph."}),
    "paragraph_gap": ("FLOAT", {"default": 0.6, "min": 0.0, "max": 5.0, "step": 0.05,
                                "tooltip": "Silence (s) after a paragraph (blank line)."}),
}


def _script():
    return ("STRING", {"multiline": True, "default": "",
                       "tooltip": "The voiceover script, any length. Blank lines separate "
                                  "paragraphs."})


class Qwen3TTSLoader:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": (list(engine.MODELS), {
                "tooltip": "CustomVoice: the 9 built-in voices. VoiceDesign: a voice from a "
                           "description. Base: clone a voice from the voice pool."}),
            "attention": (["sdpa", "flash_attention_2", "eager"], {
                "tooltip": "sdpa works everywhere; flash_attention_2 needs flash-attn "
                           "installed."}),
        }}

    RETURN_TYPES = ("QWEN3TTS",)
    RETURN_NAMES = ("tts",)
    FUNCTION = "load"
    CATEGORY = CATEGORY

    def load(self, model, attention="sdpa"):
        folder = os.path.join(models_dir(), engine.MODELS[model])
        key = (folder, attention)
        if key not in _loaded:
            # One model in VRAM at a time (~4 GB each): switching workflows reloads,
            # which takes seconds, and any 8 GB GPU is enough.
            _loaded.clear()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            _loaded[key] = engine.load_model(folder, attention)
        return ({"model": _loaded[key], "kind": model},)


def _need(tts, kind, node):
    if tts["kind"] != kind:
        raise RuntimeError(f"{node} needs the '{kind}' model; the loader has "
                           f"'{tts['kind']}'.")
    return tts["model"]


class Qwen3TTSBuiltinVoice:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "tts": ("QWEN3TTS",),
            "text": _script(),
            "voice": (list(engine.SPEAKERS), {
                "tooltip": "; ".join(f"{k}: {v[1]} ({v[0]})"
                                     for k, v in engine.SPEAKERS.items())}),
            "language": (engine.LANGUAGES, {
                "tooltip": "Auto detects it; set it when you know. Every voice speaks every "
                           "language, best in its native one."}),
            "style": ("STRING", {
                "multiline": True, "default": "",
                "tooltip": "Optional delivery instruction, e.g. 'Calm, warm narration, "
                           "unhurried.' or 'Excited and fast.'"}),
            "seed": ("INT", {"default": 42, "min": 0, "max": 2**31 - 1}),
            **GAP_INPUTS,
        }}

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "speak"
    CATEGORY = CATEGORY

    def speak(self, tts, text, voice, language, style="", seed=42, max_chars_per_part=400,
              sentence_gap=0.25, paragraph_gap=0.6):
        model = _need(tts, engine.MODEL_CUSTOM, "Built-in Voice")
        parts = engine.split_script(text, max_chars_per_part)
        wave, sr = engine.builtin_voice(model, text, voice, language, style, seed,
                                        max_chars_per_part, on_part=_progress(len(parts)),
                                        sentence_gap=sentence_gap, paragraph_gap=paragraph_gap)
        return (_audio(wave, sr),)


class Qwen3TTSVoiceDesign:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "tts": ("QWEN3TTS",),
            "text": _script(),
            "voice_description": ("STRING", {
                "multiline": True,
                "default": "A calm, warm female narrator in her thirties, clear and "
                           "friendly, speaking at a relaxed pace.",
                "tooltip": "Who is speaking and how: age, gender, accent, timbre, mood, "
                           "pace."}),
            "language": (engine.LANGUAGES,),
            "seed": ("INT", {"default": 42, "min": 0, "max": 2**31 - 1}),
            **GAP_INPUTS,
        }}

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "speak"
    CATEGORY = CATEGORY

    def speak(self, tts, text, voice_description, language, seed=42, max_chars_per_part=400,
              sentence_gap=0.25, paragraph_gap=0.6):
        model = _need(tts, engine.MODEL_DESIGN, "Voice Design")
        parts = engine.split_script(text, max_chars_per_part)
        wave, sr = engine.designed_voice(model, text, voice_description, language, seed,
                                         max_chars_per_part, on_part=_progress(len(parts)),
                                         sentence_gap=sentence_gap,
                                         paragraph_gap=paragraph_gap)
        return (_audio(wave, sr),)


class Qwen3TTSVoiceClone:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tts": ("QWEN3TTS",),
                "text": _script(),
                "pool_voice": (_pool_choices(), {
                    "tooltip": "A voice from ComfyUI/input/voices (the 9 built-in voices "
                               "and any you saved). Ignored when reference_audio is "
                               "connected."}),
                "language": (engine.LANGUAGES,),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2**31 - 1}),
                **GAP_INPUTS,
            },
            "optional": {
                "reference_audio": ("AUDIO", {
                    "tooltip": "Clone this instead of the pool voice: 3-20 s of one person "
                               "speaking, no music."}),
                "reference_text": ("STRING", {
                    "multiline": True, "default": "",
                    "tooltip": "Exact transcript of reference_audio. Leave empty to clone "
                               "from the timbre only (less faithful)."}),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "speak"
    CATEGORY = CATEGORY

    def speak(self, tts, text, pool_voice, language, seed=42, max_chars_per_part=400,
              sentence_gap=0.25, paragraph_gap=0.6, reference_audio=None, reference_text=""):
        model = _need(tts, engine.MODEL_BASE, "Voice Clone")
        if reference_audio is not None:
            ref, ref_text = _mono(reference_audio), reference_text
            engine.log(f"{engine.LOG} cloning the connected reference audio")
        else:
            path, ref_text = engine.pool_entry(pool_dir(), pool_voice)
            ref = engine.read_audio(path)
            engine.log(f"{engine.LOG} cloning pool voice '{pool_voice}'")
        parts = engine.split_script(text, max_chars_per_part)
        wave, sr = engine.cloned_voice(model, text, ref, ref_text, language, seed,
                                       max_chars_per_part, on_part=_progress(len(parts)),
                                       sentence_gap=sentence_gap, paragraph_gap=paragraph_gap)
        return (_audio(wave, sr),)


class Qwen3TTSSaveToPool:
    """Add a voice to the pool: the clip and its transcript, for cloning later."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "audio": ("AUDIO",),
            "voice_name": ("STRING", {"default": "my_voice",
                                      "tooltip": "Saved as input/voices/<name>.flac + .txt."}),
            "transcript": ("STRING", {
                "multiline": True, "default": "",
                "tooltip": "Exactly what the clip says. Wire the same text the clip was "
                           "rendered from."}),
            "overwrite": ("BOOLEAN", {"default": False}),
        }}

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("audio", "voice_name")
    OUTPUT_NODE = True
    FUNCTION = "save"
    CATEGORY = CATEGORY

    def save(self, audio, voice_name, transcript, overwrite=False):
        name = engine.safe_name(voice_name)
        path = os.path.join(pool_dir(), name + ".flac")
        if os.path.exists(path) and not overwrite:
            raise RuntimeError(f"The pool already has '{name}'. Pick another name or turn "
                               f"on overwrite.")
        wave, sr = _mono(audio)
        engine.write_audio(wave, sr, path)
        with open(os.path.join(pool_dir(), name + ".txt"), "w", encoding="utf-8") as f:
            f.write(" ".join(transcript.split()) + "\n")
        engine.log(f"{engine.LOG} voice '{name}' saved to the pool ({wave.size / sr:.1f} s); "
                   f"refresh the browser to pick it in Voice Clone.")
        return {"ui": {"audio": [{"filename": name + ".flac", "subfolder": POOL,
                                  "type": "input"}]},
                "result": (audio, name)}


class Qwen3TTSSave:
    """Save the voiceover as WAV and MP3 under output/voiceover/."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "audio": ("AUDIO",),
            "filename_prefix": ("STRING", {"default": "voiceover",
                                           "tooltip": "Saved as output/voiceover/"
                                                      "<prefix>_00001.wav and .mp3."}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("wav_path",)
    OUTPUT_NODE = True
    FUNCTION = "save"
    CATEGORY = CATEGORY

    def save(self, audio, filename_prefix="voiceover"):
        prefix = engine.safe_name(filename_prefix)
        folder = os.path.join(folder_paths.get_output_directory(), "voiceover")
        os.makedirs(folder, exist_ok=True)
        n = 1
        while any(os.path.exists(os.path.join(folder, f"{prefix}_{n:05d}{e}"))
                  for e in (".wav", ".mp3")):
            n += 1
        name = f"{prefix}_{n:05d}"
        wave, sr = _mono(audio)
        wav = os.path.join(folder, name + ".wav")
        engine.write_audio(wave, sr, wav)
        engine.write_audio(wave, sr, os.path.join(folder, name + ".mp3"))
        engine.log(f"{engine.LOG} saved {wave.size / sr:.1f} s -> output/voiceover/{name}"
                   f".wav and .mp3")
        return {"ui": {"audio": [{"filename": name + ".mp3", "subfolder": "voiceover",
                                  "type": "output"}]},
                "result": (wav,)}


NODE_CLASS_MAPPINGS = {
    "Qwen3TTSLoader": Qwen3TTSLoader,
    "Qwen3TTSBuiltinVoice": Qwen3TTSBuiltinVoice,
    "Qwen3TTSVoiceDesign": Qwen3TTSVoiceDesign,
    "Qwen3TTSVoiceClone": Qwen3TTSVoiceClone,
    "Qwen3TTSSaveToPool": Qwen3TTSSaveToPool,
    "Qwen3TTSSave": Qwen3TTSSave,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Qwen3TTSLoader": "Qwen3-TTS: Load Model",
    "Qwen3TTSBuiltinVoice": "Qwen3-TTS: Built-in Voice",
    "Qwen3TTSVoiceDesign": "Qwen3-TTS: Voice Design",
    "Qwen3TTSVoiceClone": "Qwen3-TTS: Voice Clone (voice pool)",
    "Qwen3TTSSaveToPool": "Qwen3-TTS: Save to Voice Pool",
    "Qwen3TTSSave": "Qwen3-TTS: Save Voiceover (WAV + MP3)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
