# Qwen3-TTS Voiceover - Any Length, 9 Voices, Design & Clone

Turn a script of any length into a voiceover with Qwen3-TTS (Apache-2.0), in 10 languages: 9 built-in voices, voices designed from a description, and voice cloning.

## Storage

Attach your own **Network Volume at /workspace** when deploying (**40 GB recommended**). The container disk is 5 GB and the Volume disk 0 GB.

Models, voices and voiceovers stay on the volume.

## Connect

- **Port 8188:** ComfyUI
- **Port 8888:** JupyterLab

First boot downloads **13.6 GB**. Wait for "Setup complete!" in logs.

Jupyter has no login by default; anyone with its URL can run commands. For a login, set JUPYTER_NO_AUTH=0 and JUPYTER_PASSWORD.

## Workflows

1. **Built-in Voice** - Ryan, Aiden, Vivian, Serena, Uncle_Fu, Dylan, Eric, Ono_Anna or Sohee reads your script.
2. **Voice Design** - describe a voice; its sample is saved to the voice pool.
3. **Voice Clone** - any pool voice reads your script, the same voice throughout.
4. **Add Your Voice** - a recording and its transcript into the pool.

Paste any length: it is rendered in parts at sentence breaks and joined with natural pauses. Saved to ComfyUI/output/voiceover as WAV and MP3.

## Voice pool

ComfyUI/input/voices holds every built-in voice already rendered, in its native language and in English, with transcripts. Listen there to choose a voice.

## Hardware

About 4 GB of VRAM, one model at a time: any 8 GB+ GPU works; an RTX 4090 or L4 is comfortable.

Full instructions:
https://github.com/tenitsky/qwen3-tts-voiceover
