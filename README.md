# Qwen3-TTS Voiceover: RunPod ComfyUI template

A one-shot template that installs **Qwen3-TTS** (Alibaba Qwen, Apache-2.0) on RunPod with
ComfyUI and JupyterLab, for **voiceovers of any length** in 10 languages:

- the **9 built-in voices**, steerable with a style instruction
- **voices designed from a description** ("a calm, warm narrator in her thirties...")
- **voice cloning** from a **voice pool**: every built-in voice already rendered, plus
  any voice you design or add

The WAV it saves is ready to be the voiceover for the LongCat and FlashHead avatar
templates.

ComfyUI has no Qwen3-TTS nodes. This repo's small `comfyui-qwen3-tts` pack drives Qwen's
official [`qwen-tts`](https://github.com/QwenLM/Qwen3-TTS) package.

## The voices

| Voice | Native language | Character |
|---|---|---|
| **Ryan** | English | dynamic male, strong rhythm |
| **Aiden** | English | sunny American male, clear midrange |
| **Vivian** | Chinese | bright, slightly edgy young female |
| **Serena** | Chinese | warm, gentle young female |
| **Uncle_Fu** | Chinese | seasoned male, low and mellow |
| **Dylan** | Chinese (Beijing) | youthful Beijing male |
| **Eric** | Chinese (Sichuan) | lively Chengdu male, slightly husky |
| **Ono_Anna** | Japanese | playful female, light and nimble |
| **Sohee** | Korean | warm female, rich emotion |

Every voice speaks every supported language (English, Chinese, Japanese, Korean,
German, French, Russian, Portuguese, Spanish, Italian), best in its native one.

### The voice pool

`ComfyUI/input/voices/` holds a reference clip of every built-in voice, with its exact
transcript next to it:

- `Ryan.flac`, `Aiden.flac`: the English voices
- `Vivian.flac` + `Vivian_en.flac` (and the same for the other six): native language and
  English

16 clips in all. They ship in this repo (`samples/voices/`), rendered once with a fixed
seed, so every pod has them from the first boot without a GPU run. Listen to them in
JupyterLab to choose a voice. The **Base** model clones from them, so any built-in voice
can also read through the cloning path, and voices you design or add land in the same
folder.

## Workflows

| Workflow | Model | Does |
|---|---|---|
| `qwen3tts_1_builtin_voice` | CustomVoice | one of the 9 voices reads your script (voice, language, optional style) |
| `qwen3tts_2_voice_design` | VoiceDesign | describe a voice; it speaks a sample, saved to the voice pool |
| `qwen3tts_3_voice_clone` | Base | any pool voice reads your script, the same voice throughout |
| `qwen3tts_4_add_your_voice` | none | a recording + transcript into the voice pool |

Each opens with working defaults (an English sample script, Ryan, Serena_en), so the
first run needs no input. The voiceover is saved as
`output/voiceover/<prefix>_00001.wav` and `.mp3` and plays on the Save node.

**Long scripts.** One Qwen3-TTS call is capped at 2048 codec frames, about 2.5 minutes,
and long single calls drift in pace. So the script is cut into parts of at most
`max_chars_per_part` (400) at paragraph and sentence boundaries, rendered with the same
voice and seed, and joined with `sentence_gap` (0.25 s) inside a paragraph and
`paragraph_gap` (0.6 s) after one (a blank line). Voice Clone builds the voice once and
reuses it for every part.

**A designed voice for a long script.** VoiceDesign renders each part from the
description, so the voice can vary slightly between parts. Qwen's recommended route,
and this template's: design a short sample (workflow 2, which saves it to the pool),
then clone it for the whole script (workflow 3).

**Your own voice.** Workflow 4 adds a clean 3-20 s recording and its exact transcript to
the pool. Only clone voices you have the right to use.

## What boots

On first pod boot, `setup.sh`:

1. Requires a separate POSIX volume at `/workspace`; refuses container-disk or
   Global Volume working storage
2. Copies the baked ComfyUI from `/opt/comfyui-baked` to `/workspace/runpod-slim/ComfyUI`
   (self-healing, skip-if-present)
3. Checks that the image's PyTorch has a CUDA build that can use the GPU; stops if not,
   before any download
4. Installs the `comfyui-qwen3-tts` nodes and `qwen-tts` 0.1.1 into ComfyUI's persistent
   virtualenv, with the image's PyTorch pinned (`/opt/comfyui-runtime-constraints.txt`)
5. Copies the voice pool into `ComfyUI/input/voices/` (never over a file of the same
   name) and `Serena_en` to `input/example_recording.flac` for workflow 4
6. Downloads the three models (skip-if-exists, resumable, validated)
7. Installs the four workflows into ComfyUI's **Workflows** sidebar
8. Hands over to `/start.sh` (ComfyUI on port **8188**, JupyterLab on **8888**)

On later boots every step finds its work done and is skipped.

**transformers 4.57.3.** `qwen-tts` uses transformers internals that changed in 5.x and
fails to import there (tested with 5.18). The image ships transformers 5.x, so this
template pins **4.57.3** in ComfyUI's venv; ComfyUI v0.35.0 needs only >= 4.50.3 and runs
on it (tested). `qwen-tts` itself is installed with `--no-deps` to skip gradio, which it
lists only for its demo app. Every boot checks the version and that `qwen_tts` imports.

## Models pulled

| Folder (under `ComfyUI/models/qwen3-tts/`) | Size | From |
|---|---|---|
| `Qwen3-TTS-12Hz-1.7B-CustomVoice/` | 4.5 GB | [Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice) |
| `Qwen3-TTS-12Hz-1.7B-VoiceDesign/` | 4.5 GB | [Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign) |
| `Qwen3-TTS-12Hz-1.7B-Base/` | 4.5 GB | [Qwen/Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) |

About **13.6 GB**, all ungated, **all Apache-2.0**. Each folder holds the model, its
text tokenizer and the 12 Hz speech tokenizer it decodes with. Use **40 GB of Network
Volume storage** as a starting point.

## RunPod public template settings

| Setting | Value |
|---|---|
| Template name | `Qwen3-TTS Voiceover - ComfyUI + JupyterLab` |
| Compute type | **NVIDIA / GPU** |
| Base image | **`runpod/comfyui:1.4.0-comfyuiv0.35.0-cuda12.8`** |
| Registry authentication | None; image is public |
| Container disk | **5 GB** |
| Persistent storage in the public template editor | **Volume disk**, **0 GB** |
| Template volume mount path | **`/workspace`** |
| Network Volume at deployment | Each deployer attaches their own at `/workspace`; **40 GB recommended** |
| HTTP ports | **`8188,8888`** (ComfyUI, JupyterLab) |
| TCP ports | None required; expose `22` only if SSH is wanted |
| Environment variables | `JUPYTER_NO_AUTH=1`; `HF_TOKEN` optional |
| README tab | Paste [`TEMPLATE_README.md`](TEMPLATE_README.md) |

`JUPYTER_NO_AUTH=1` runs Jupyter without a login: setup passes the image's own
`JUPYTER_DISABLE_AUTH=true` switch to `/start.sh`. For authenticated Jupyter, use
`JUPYTER_NO_AUTH=0` and set `JUPYTER_PASSWORD` at deployment; it becomes the token.
Do not override `COMFYUI_PATH`: the image starts ComfyUI at its fixed path.

**Container start command.** Paste this JSON into RunPod's container start command
field (also provided as [`runpod-start.json`](runpod-start.json); readable source:
[`bootstrap.sh`](bootstrap.sh)). It checks DNS for GitHub and Hugging Face first and
leaves working DNS unchanged. If two checks fail, it saves the original
`/etc/resolv.conf` under `/tmp/qwen3-tts-voiceover-dns.*`, then tries the public
resolvers `1.1.1.1` and `8.8.8.8`; if resolution still fails, it restores the original
and stops with a networking error. Git clone failures are retried up to 10 times.

```json
{
  "entrypoint": [
    "bash",
    "-lc"
  ],
  "cmd": [
    "set -e\ndns_ok() {\n  timeout 10 getent ahostsv4 github.com >/dev/null 2>&1 &&\n  timeout 10 getent ahostsv4 huggingface.co >/dev/null 2>&1\n}\nif ! dns_ok; then\n  echo 'DNS lookup failed; retrying in 3 seconds...'\n  sleep 3\n  if ! dns_ok; then\n    dns_backup=$(mktemp /tmp/qwen3-tts-voiceover-dns.XXXXXX)\n    cp /etc/resolv.conf \"$dns_backup\"\n    echo \"Trying public DNS; original resolver saved at $dns_backup\"\n    if { printf 'nameserver 1.1.1.1\\nnameserver 8.8.8.8\\noptions timeout:2 attempts:2\\n'; } > /etc/resolv.conf && dns_ok; then\n      echo 'DNS recovered; continuing setup.'\n    else\n      cat \"$dns_backup\" > /etc/resolv.conf || true\n      echo 'FATAL: DNS still unavailable or resolver is read-only. Check RunPod networking or deploy on another host with the same Network Volume.' >&2\n      exit 1\n    fi\n  fi\nfi\nfor attempt in 1 2 3 4 5 6 7 8 9 10; do\n  repo=$(mktemp -d /tmp/qwen3-tts-voiceover.XXXXXX)\n  if git clone --depth 1 https://github.com/tenitsky/qwen3-tts-voiceover.git \"$repo\"; then\n    exec bash \"$repo/setup.sh\"\n  fi\n  sleep 5\ndone\necho 'FATAL: unable to clone qwen3-tts-voiceover after 10 attempts' >&2\nexit 1\n"
  ]
}
```

For the first launch, check the logs for **`Network Volume workspace ready at
/workspace`**, then `qwen-tts 0.1.1 ready.`, `Voice pool: 16 clips`, the model
downloads and **`Setup complete!`**.

## Hardware

Each 1.7B model takes about 4 GB of VRAM in bf16, and one is loaded at a time (moving
to a workflow with another model reloads it in seconds), so **any 8 GB+ GPU** works; an
RTX 4090, L4 or A5000 is comfortable. Speech is generated token by token, so a faster GPU helps less than
for video. On an 8 GB RTX 3080 Laptop without flash-attn, the voice pool rendered at
about 5 s per second of speech; a desktop or data-centre GPU is several times faster.

## Template env vars (all optional)

| Var | Default | Purpose |
|---|---|---|
| `HF_TOKEN` | *(empty)* | Not required (the repos are ungated). It raises Hugging Face rate limits |
| `JUPYTER_NO_AUTH` | `1` | Disables Jupyter login (anyone with the URL gets a shell). Set `0` and `JUPYTER_PASSWORD` for a login |
| `JUPYTER_PASSWORD` | *(empty)* | Jupyter token, used when `JUPYTER_NO_AUTH=0` |
| `QWEN_TTS_VERSION` | `0.1.1` | The qwen-tts package version |
| `COMFYUI_PATH` | `/workspace/runpod-slim/ComfyUI` | Leave unset; must match the base image's fixed startup path |
| `HF_HOME` | `/workspace/.cache/huggingface` | Keeps the HF cache on the volume, not the 5 GB container disk |

## What has and hasn't been verified

Verified on a local RTX 3080 Laptop GPU (PyTorch 2.10 cu128, transformers 4.57.3,
qwen-tts 0.1.1): the CustomVoice model rendering all 16 voice pool clips; and all four
shipped workflows run in ComfyUI v0.35.0: a recording added to the pool, a voice
designed and saved to the pool, that designed voice cloned for the 3-paragraph sample
script (3 parts, 32.7 s), and Ryan reading the same script (38.6 s), each workflow
loading its own model in turn. On CPU in CI: script splitting, pauses, seeds and the single
clone prompt against a fake model; the voice pool and audio files; that the CustomVoice
config still lists exactly these 9 voices and 10 languages and that qwen-tts imports
with this API on the pinned transformers; the workflows against the nodes' schemas; and
a full first boot and reboot of `setup.sh` against an offline image fixture.

**Not yet verified:** a boot on a real RunPod pod.

## Repository layout

```
├── setup.sh                               # RunPod boot script
├── bootstrap.sh / runpod-start.json       # container start command (readable / paste-ready)
├── README.md
├── TEMPLATE_README.md                     # paste into the public template's README tab
├── RUNPOD_TEMPLATE_SETUP.txt              # every template field, with comments and links
├── custom_nodes/
│   └── comfyui-qwen3-tts/                 # Load Model / Built-in Voice / Voice Design /
│       ├── engine.py                      #   Voice Clone / Save to Voice Pool / Save
│       └── storage.py                     # Network Volume preflight
├── samples/voices/                        # the voice pool: 16 clips + transcripts
├── tools/
│   ├── build_workflow.py                  # generates the workflow JSONs; re-run after edits
│   ├── render_voice_pool.py               # regenerates samples/voices on a GPU
│   ├── test_engine.py                     # splitting, pauses, cloning, pool, audio (CPU)
│   ├── test_upstream.py                   # Qwen's model and package still match
│   ├── test_workflows.py                  # graphs vs. node schemas, defaults, downloads
│   ├── test_storage.py                    # Network Volume mount and filesystem checks
│   ├── test_boot.py                       # full setup with image/network fixtures (Linux)
│   ├── test_jupyter.py                    # auth switch and real Jupyter Server smoke test
│   └── test_setup.py                      # Bash download and start-command checks
└── workflows/                             # the four workflows listed above
```

## Credits

[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) (Alibaba Qwen team, Apache-2.0).
