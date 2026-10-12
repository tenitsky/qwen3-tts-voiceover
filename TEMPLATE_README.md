# Qwen3-TTS Voiceover - Any Length, 9 Voices, Design & Clone

Turn a script of any length into a natural voiceover with **Qwen3-TTS 1.7B** (Apache-2.0) in **10 languages**: English, Chinese, Japanese, Korean, German, French, Russian, Portuguese, Spanish and Italian. Use 9 built-in voices, design a voice from a description, or clone one. The WAV is ready to drive the LongCat and FlashHead avatar templates.

## Storage

Attach your own **Network Volume at /workspace** when deploying (**40 GB recommended**). The container disk is 5 GB and the Volume disk 0 GB.

Models, voices and voiceovers stay on the volume. Reattach it in its datacenter when replacing a pod; later boots skip the downloads.

## Connect

- **Port 8188:** ComfyUI
- **Port 8888:** JupyterLab (listen to voices, upload recordings, download audio)

First boot downloads **13.6 GB** (three models). Wait for **"Setup complete!"** in the logs.

Jupyter has no login by default; anyone with its URL can run commands. For a login, set JUPYTER_NO_AUTH=0 and JUPYTER_PASSWORD.

## Workflows

Open ComfyUI's **Workflows** sidebar. Each opens with working defaults, so the first run needs no input.

1. **Built-in Voice** - one of the 9 voices reads your script. Pick the voice and language, and optionally a style ("calm and slow", "excited").
2. **Voice Design** - describe a voice ("a warm female narrator in her thirties"); it speaks a short sample, saved to the voice pool.
3. **Voice Clone** - any pool voice reads your script, the same voice throughout.
4. **Add Your Voice** - a clean 3-20 s recording plus its exact transcript goes into the pool. Only clone voices you have the right to use.

Voiceovers are saved to ComfyUI/output/voiceover/ as WAV and MP3 and play on the Save node.

## The 9 voices

- **Ryan** - dynamic English male
- **Aiden** - sunny American male
- **Vivian** - bright young female (Chinese)
- **Serena** - warm, gentle female (Chinese)
- **Uncle_Fu** - low, mellow male (Chinese)
- **Dylan** - youthful Beijing male
- **Eric** - lively Chengdu male
- **Ono_Anna** - playful female (Japanese)
- **Sohee** - warm female (Korean)

Every voice speaks every language, best in its native one.

## Voice pool

ComfyUI/input/voices/ already holds every voice rendered in its native language and in English (16 clips, with transcripts). Listen in JupyterLab to choose. Voices you design or add land there too.

## Long scripts

Paste any length. The script is split at sentence and paragraph breaks into parts of up to 400 characters, rendered with the same voice and seed, and joined with natural pauses (0.25 s between sentences, 0.6 s after a blank line).

For a long script in a designed voice, design a short sample (workflow 2), then clone it for the whole script (workflow 3): the voice stays identical throughout.

## Hardware

About **4 GB of VRAM**, one model loaded at a time: any 8 GB+ GPU works; an RTX 4090 or L4 is comfortable.

All three models are **Apache-2.0** and ungated; no Hugging Face token needed.

Full instructions:
https://github.com/tenitsky/qwen3-tts-voiceover
