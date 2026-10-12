#!/usr/bin/env python3
"""
Render the voice pool: every built-in Qwen3-TTS voice saying a short sample in its
native language, and in English, as <Name>.flac / <Name>_en.flac with the transcript
next to it (<Name>.txt). The clips let you audition the voices and are ready-made
cloning references for the Base model.

    python tools/render_voice_pool.py --models /path/to/models/qwen3-tts --out samples/voices

The repo ships the result in samples/voices/; setup.sh copies it into
ComfyUI/input/voices on every pod. Re-run only to regenerate it.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "custom_nodes", "comfyui-qwen3-tts"))
import engine  # noqa: E402

SAMPLES = {
    "English": "Hello, and welcome. This is a short sample of my voice, so you can hear "
               "how I sound before you choose me for your next voiceover.",
    "Chinese": "大家好，欢迎收听。这是一段简短的声音样本，让你先听听我的音色，再决定是否用我来录制下一段配音。",
    "Japanese": "こんにちは、ようこそ。これは私の声の短いサンプルです。次のナレーションに使う前に、"
                "どんな声か聞いてみてください。",
    "Korean": "안녕하세요, 반갑습니다. 이것은 제 목소리의 짧은 샘플입니다. 다음 내레이션에 "
              "쓰기 전에 어떤 목소리인지 들어 보세요.",
}
SEED = 7


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", required=True, help="folder holding the three model folders")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "samples", "voices"))
    ap.add_argument("--attention", default="sdpa")
    args = ap.parse_args()

    model = engine.load_model(os.path.join(args.models, engine.MODELS[engine.MODEL_CUSTOM]),
                              args.attention)
    os.makedirs(args.out, exist_ok=True)
    for speaker, (native, _) in engine.SPEAKERS.items():
        takes = [(speaker, native)] + ([] if native == "English" else [(speaker + "_en", "English")])
        for name, language in takes:
            text = SAMPLES[language]
            wave, sr = engine.builtin_voice(model, text, speaker, language, seed=SEED,
                                            max_chars=1000)
            engine.write_audio(wave, sr, os.path.join(args.out, name + ".flac"))
            with open(os.path.join(args.out, name + ".txt"), "w", encoding="utf-8") as f:
                f.write(text + "\n")
            engine.log(f"{engine.LOG} pool: {name} ({language}, {wave.size / sr:.1f} s)")


if __name__ == "__main__":
    main()
