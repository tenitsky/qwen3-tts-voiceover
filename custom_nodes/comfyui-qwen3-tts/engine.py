"""
Qwen3-TTS voiceover engine: script of any length -> one voiceover, with Qwen's official
qwen_tts package. No ComfyUI imports, so the same code runs inside the nodes and from
tools/render_voice_pool.py.

One generate call is capped at max_new_tokens = 2048 codec frames (12 Hz, about 2.5
minutes), and long single calls drift in pace and timbre, so a script is split into
parts at paragraph and sentence boundaries, rendered part by part with the same voice,
and joined with short pauses: a little longer between paragraphs than between sentences.

Three models, as Qwen ships them:
  CustomVoice  the 9 built-in voices, steerable with a style instruction
  VoiceDesign  a new voice from a natural-language description
  Base         clones a voice from a reference clip and its transcript

The voice pool is a folder of reference clips (<name>.flac + <name>.txt transcript):
the 9 built-in voices rendered once, plus any voice you design or upload. The Base
model clones from it, which is also how a designed voice stays the same across a long
script (Qwen's "voice design then clone").
"""

import os
import re
import shutil
import subprocess

import numpy as np
import torch

LOG = "[Qwen3-TTS]"

MODELS = {
    "CustomVoice (9 built-in voices)": "Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "VoiceDesign (voice from a description)": "Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "Base (voice clone)": "Qwen3-TTS-12Hz-1.7B-Base",
}
MODEL_CUSTOM, MODEL_DESIGN, MODEL_BASE = MODELS

# Built-in voices of the CustomVoice model (official model card), with native language.
SPEAKERS = {
    "Ryan": ("English", "Dynamic male voice with strong rhythm"),
    "Aiden": ("English", "Sunny American male voice with a clear midrange"),
    "Vivian": ("Chinese", "Bright, slightly edgy young female voice"),
    "Serena": ("Chinese", "Warm, gentle young female voice"),
    "Uncle_Fu": ("Chinese", "Seasoned male voice with a low, mellow timbre"),
    "Dylan": ("Chinese", "Youthful Beijing male voice with a clear, natural timbre"),
    "Eric": ("Chinese", "Lively Chengdu male voice with a slightly husky brightness"),
    "Ono_Anna": ("Japanese", "Playful Japanese female voice with a light, nimble timbre"),
    "Sohee": ("Korean", "Warm Korean female voice with rich emotion"),
}
LANGUAGES = ["Auto", "English", "Chinese", "Japanese", "Korean", "German", "French",
             "Russian", "Portuguese", "Spanish", "Italian"]

POOL_EXT = (".flac", ".wav", ".mp3", ".ogg", ".m4a")
MAX_NEW_TOKENS = 2048
SENTENCE_END = re.compile(r"(?<=[.!?。！？…])[\"'”’)\]]*\s+|(?<=[。！？])")


def log(*args, **kwargs):
    """print, flushed: ComfyUI's stdout is a file on the pod."""
    print(*args, **kwargs, flush=True)


# ---------------------------------------------------------------------------- text
def split_script(text, max_chars=400):
    """Parts of at most max_chars, cut at paragraph, then sentence, then clause or word
    boundaries. Returns [(part, ends_paragraph)]."""
    parts = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.replace("\r", "")) if p.strip()]
    for paragraph in paragraphs:
        paragraph = " ".join(paragraph.split())
        sentences = [s.strip() for s in SENTENCE_END.split(paragraph) if s.strip()]
        current = ""
        pieces = []
        for sentence in sentences:
            for piece in _fit(sentence, max_chars):
                if current and len(current) + 1 + len(piece) > max_chars:
                    pieces.append(current)
                    current = piece
                else:
                    current = f"{current} {piece}".strip()
        if current:
            pieces.append(current)
        parts += [(p, i == len(pieces) - 1) for i, p in enumerate(pieces)]
    return parts


def _fit(sentence, max_chars):
    """A sentence longer than max_chars, cut at commas or spaces."""
    if len(sentence) <= max_chars:
        return [sentence]
    out, current = [], ""
    for token in re.split(r"(?<=[,;:，；：])\s*|\s+", sentence):
        if not token:
            continue
        if current and len(current) + 1 + len(token) > max_chars:
            out.append(current)
            current = token
        else:
            current = f"{current} {token}".strip()
    if current:
        out.append(current)
    return out


# ---------------------------------------------------------------------------- model
def load_model(model_dir, attention="sdpa", device="cuda"):
    """Qwen3TTSModel from a local folder, bf16."""
    if not os.path.isfile(os.path.join(model_dir, "model.safetensors")):
        raise RuntimeError(f"Qwen3-TTS model not found at {model_dir}. Restart the pod so "
                           f"setup.sh can download it.")
    from qwen_tts import Qwen3TTSModel
    model = Qwen3TTSModel.from_pretrained(model_dir, device_map=device, dtype=torch.bfloat16,
                                          attn_implementation=attention)
    log(f"{LOG} loaded {os.path.basename(model_dir)} ({attention})")
    return model


def _seed(seed):
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed))


def _language(language):
    return None if language in ("", "Auto", None) else language


def render_parts(generate, parts, sample_rate_hint=24000, sentence_gap=0.25,
                 paragraph_gap=0.6, on_part=None):
    """Run generate(text) -> (wave, sr) for every part and join them with pauses."""
    if not parts:
        raise RuntimeError("The script is empty.")
    out, sr = [], sample_rate_hint
    for i, (part, ends_paragraph) in enumerate(parts):
        wave, sr = generate(part)
        wave = np.asarray(wave, dtype=np.float32).reshape(-1)
        out.append(wave)
        if i < len(parts) - 1:
            gap = paragraph_gap if ends_paragraph else sentence_gap
            out.append(np.zeros(int(round(gap * sr)), dtype=np.float32))
        if on_part:
            on_part(i, len(parts))
    audio = np.concatenate(out)
    log(f"{LOG} {len(parts)} part(s) -> {audio.size / sr:.1f} s of speech")
    return audio, sr


def builtin_voice(model, text, speaker, language="Auto", instruct="", seed=42,
                  max_chars=400, on_part=None, **gaps):
    if speaker not in SPEAKERS:
        raise RuntimeError(f"Unknown voice {speaker}. Built-in voices: {', '.join(SPEAKERS)}")
    _seed(seed)

    def generate(part):
        wavs, sr = model.generate_custom_voice(text=part, language=_language(language),
                                               speaker=speaker, instruct=instruct or "",
                                               max_new_tokens=MAX_NEW_TOKENS)
        return wavs[0], sr
    return render_parts(generate, split_script(text, max_chars), on_part=on_part, **gaps)


def designed_voice(model, text, description, language="Auto", seed=42, max_chars=400,
                   on_part=None, **gaps):
    """VoiceDesign renders every part from the description, so the voice can vary a
    little between parts. For a long script, save a short design to the voice pool and
    clone it with the Base model instead."""
    if not description.strip():
        raise RuntimeError("Describe the voice, e.g. 'A calm, warm female narrator in her "
                           "thirties with a soft British accent.'")
    _seed(seed)

    def generate(part):
        wavs, sr = model.generate_voice_design(text=part, language=_language(language),
                                               instruct=description,
                                               max_new_tokens=MAX_NEW_TOKENS)
        return wavs[0], sr
    return render_parts(generate, split_script(text, max_chars), on_part=on_part, **gaps)


def cloned_voice(model, text, ref_audio, ref_text, language="Auto", seed=42, max_chars=400,
                 on_part=None, **gaps):
    """Base model. ref_audio: (wave, sr). The clone prompt is built once and reused for
    every part, so the voice stays the same across the script."""
    ref_text = (ref_text or "").strip()
    prompt = model.create_voice_clone_prompt(ref_audio=ref_audio, ref_text=ref_text or None,
                                             x_vector_only_mode=not ref_text)
    if not ref_text:
        log(f"{LOG} no transcript for the reference: cloning from the speaker embedding "
            f"only, which is less faithful. Add the transcript for the best match.")
    _seed(seed)

    def generate(part):
        wavs, sr = model.generate_voice_clone(text=part, language=_language(language),
                                              voice_clone_prompt=prompt,
                                              max_new_tokens=MAX_NEW_TOKENS)
        return wavs[0], sr
    return render_parts(generate, split_script(text, max_chars), on_part=on_part, **gaps)


# ---------------------------------------------------------------------------- pool
def pool_voices(pool_dir):
    """Voice names in the pool, sorted: built-in voices first, then the rest."""
    if not os.path.isdir(pool_dir):
        return []
    names = {os.path.splitext(f)[0] for f in os.listdir(pool_dir)
             if f.lower().endswith(POOL_EXT) and not f.startswith(".")}
    builtin = [n for n in SPEAKERS if n in names] + \
        [n for n in sorted(names) if n.split("_en")[0] in SPEAKERS and n not in SPEAKERS]
    return builtin + sorted(names - set(builtin), key=str.lower)


def pool_entry(pool_dir, name):
    """(audio path, transcript) of a pool voice."""
    for ext in POOL_EXT:
        path = os.path.join(pool_dir, name + ext)
        if os.path.isfile(path):
            txt = os.path.join(pool_dir, name + ".txt")
            text = open(txt, encoding="utf-8").read().strip() if os.path.isfile(txt) else ""
            return path, text
    raise RuntimeError(f"Voice '{name}' is not in the pool at {pool_dir}.")


def safe_name(name):
    name = re.sub(r"[^\w\-]+", "_", (name or "").strip()).strip("_")
    if not name:
        raise RuntimeError("Give the voice a name (letters, digits, _ or -).")
    return name[:64]


# ---------------------------------------------------------------------------- audio io
def ffmpeg():
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found (apt-get install -y ffmpeg).")
    return exe


def read_audio(path, sr=24000):
    """Any ffmpeg-readable file -> mono float32 at sr."""
    p = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-vn", "-f", "f32le", "-ac", "1",
                        "-ar", str(sr), "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    data = np.frombuffer(p.stdout, dtype=np.float32)
    if p.returncode != 0 or not data.size:
        raise RuntimeError(f"Could not read {path}:\n{p.stderr.decode(errors='replace')[-800:]}")
    return data.copy(), sr


def write_audio(wave, sr, path):
    """Write mono float audio; the format follows the extension (wav, flac, mp3)."""
    wave = np.asarray(wave, dtype=np.float32).reshape(-1)
    pcm = (np.clip(wave, -1, 1) * 32767).astype(np.int16)
    args = [ffmpeg(), "-y", "-v", "error", "-f", "s16le", "-ar", str(int(sr)), "-ac", "1",
            "-i", "-"]
    if path.lower().endswith(".mp3"):
        args += ["-c:a", "libmp3lame", "-q:a", "0"]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    p = subprocess.run(args + [path], input=pcm.tobytes(), stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed writing {path}:\n{p.stderr.decode()[-800:]}")
