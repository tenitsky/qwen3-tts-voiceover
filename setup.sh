#!/bin/bash
set -e
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Starting Qwen3-TTS Voiceover Template Setup ==="
echo "Template revision: $(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || printf unknown)"

# Refuse a disposable workspace before doing installation work.
# The image's /start.sh fixes ComfyUI at this path.
export COMFYUI_PATH="${COMFYUI_PATH:-/workspace/runpod-slim/ComfyUI}"
if [ "$COMFYUI_PATH" != /workspace/runpod-slim/ComfyUI ]; then
  echo "FATAL: this image's /start.sh uses /workspace/runpod-slim/ComfyUI. Leave COMFYUI_PATH unset."
  exit 1
fi
python3 "$SCRIPT_DIR/custom_nodes/comfyui-qwen3-tts/storage.py" preflight "$COMFYUI_PATH"

# Apply before the image starts Jupyter. The image's /start.sh runs JupyterLab
# without a token when JUPYTER_DISABLE_AUTH=true, uses JUPYTER_PASSWORD as the
# token when set, and otherwise does not start Jupyter at all. The exported value
# reaches /start.sh through the final exec. Jupyter is optional, so a start script
# without that switch is reported rather than stopping the pod.
if [ "${JUPYTER_NO_AUTH:-1}" = "1" ]; then
  export JUPYTER_DISABLE_AUTH=true
  echo "Jupyter authentication disabled: anyone with access to its URL can run commands."
  if ! grep -q 'JUPYTER_DISABLE_AUTH' /start.sh 2>/dev/null; then
    echo "WARNING: this image's /start.sh has no JUPYTER_DISABLE_AUTH switch, so JupyterLab"
    echo "         may not start. Use runpod/comfyui:1.4.0-comfyuiv0.35.0-cuda12.8, or set"
    echo "         JUPYTER_NO_AUTH=0 and JUPYTER_PASSWORD. ComfyUI is unaffected."
  fi
else
  unset JUPYTER_DISABLE_AUTH
  if [ -z "${JUPYTER_PASSWORD:-}" ]; then
    echo "NOTE: JUPYTER_NO_AUTH=0 without JUPYTER_PASSWORD: the image does not start JupyterLab."
  fi
fi

echo "=== Ensuring System Dependencies are Installed ==="
# The image already supplies these. Contact apt mirrors only if something is
# actually missing; an unrelated mirror outage must not break a complete image.
packages=()
command -v wget >/dev/null || packages+=(wget)
command -v git >/dev/null || packages+=(git)
command -v ffmpeg >/dev/null || packages+=(ffmpeg)
[ -s /etc/ssl/certs/ca-certificates.crt ] || packages+=(ca-certificates)
if [ "${#packages[@]}" -gt 0 ]; then
  apt-get update
  apt-get install -y --no-install-recommends "${packages[@]}"
fi

# Jupyter serves /workspace in the base image. Keep its settings and user data on
# that persistent volume too; /root belongs to the disposable container disk.
export JUPYTER_CONFIG_DIR=/workspace/.jupyter
export JUPYTER_DATA_DIR=/workspace/.local/share/jupyter
export IPYTHONDIR=/workspace/.ipython
mkdir -p "$JUPYTER_CONFIG_DIR" "$JUPYTER_DATA_DIR" "$IPYTHONDIR"

# Network Volumes can expose fixed permissions. Jupyter's cookie secrets and
# kernel connection files require private 0600 files; these are disposable
# runtime state, not notebooks or settings. Keep them on the container filesystem.
JUPYTER_RUNTIME_DIR="$(mktemp -d /tmp/qwen3tts-jupyter-runtime.XXXXXX)"
export JUPYTER_RUNTIME_DIR
chmod 700 "$JUPYTER_RUNTIME_DIR"
python3 - <<'PY'
import os
from pathlib import Path
from jupyter_core.paths import secure_write

probe = Path(os.environ["JUPYTER_RUNTIME_DIR"]) / "secure-write-check"
try:
    with secure_write(str(probe)) as stream:
        stream.write("Jupyter runtime permissions verified")
finally:
    probe.unlink(missing_ok=True)
print(f"Jupyter runtime ready at {probe.parent}; notebooks and settings remain on /workspace.")
PY

# Qwen3-TTS runs through Qwen's official qwen-tts package (Apache-2.0), driven by this
# repo's comfyui-qwen3-tts nodes. QWEN_TTS_VERSION pins the package.
#   Base image: runpod/comfyui:1.4.0-comfyuiv0.35.0-cuda12.8
# This script deliberately does NOT update ComfyUI core: on these images
# `pip install -r requirements.txt` can reinstall torch and break the baked CUDA build.
QWEN_TTS_VERSION="${QWEN_TTS_VERSION:-0.1.1}"

# All three model repos are ungated, so no token is needed. Set HF_TOKEN anyway if you have
# one: anonymous requests are rate-limited (~120/h vs ~1000/h) and slower.
HF_TOKEN="${HF_TOKEN:-}"
[ -n "$HF_TOKEN" ] && export HF_TOKEN || echo "NOTE: HF_TOKEN not set - downloads may be slower and rate-limited."
export HF_HOME="${HF_HOME:-/workspace/.cache/huggingface}"

# Self-healing check prevents directory collisions and fixes broken folders
if [ ! -f "$COMFYUI_PATH/main.py" ]; then
  echo "First time setup: Copying baked ComfyUI to workspace..."
  if [ -e "$COMFYUI_PATH" ]; then
    echo "FATAL: existing ComfyUI directory has no main.py; refusing to delete user files."
    exit 1
  fi
  mkdir -p "$(dirname "$COMFYUI_PATH")"
  cp -r /opt/comfyui-baked "$COMFYUI_PATH"
fi

if [ ! -f "$COMFYUI_PATH/main.py" ]; then
  echo "FATAL: no ComfyUI at $COMFYUI_PATH and /opt/comfyui-baked did not provide one."
  echo "       Check the container image."
  exit 1
fi
echo "ComfyUI: $COMFYUI_PATH"

# Validation only needs the standard library. Use the image interpreter that
# already passed preflight, not a possibly stale persisted ComfyUI virtualenv.
PY="$(command -v python3)"
echo "Setup validator Python: $PY"

# PyTorch comes from the image (the volume's venv only adds custom-node packages).
# The image also starts on hosts whose driver is too old for its CUDA build, where
# PyTorch cannot see the GPU - stop here, before the downloads, rather than render on
# the CPU.
TORCH_PY="$(command -v python3.12 || command -v python3)"
if ! "$TORCH_PY" - <<'PY'
import sys
try:
    import torch
except Exception as exc:
    sys.exit(f"FATAL: cannot import the image's PyTorch ({exc}).")
build = torch.version.cuda or "none"
print(f"PyTorch {torch.__version__}, CUDA build {build}")
if build == "none":
    sys.exit("FATAL: the image's PyTorch has no CUDA build. Change the template's "
             "container image to runpod/comfyui:1.4.0-comfyuiv0.35.0-cuda12.8.")
if not torch.cuda.is_available():
    sys.exit(f"FATAL: CUDA {build} PyTorch cannot use this GPU: the host driver is too "
             "old for it. Redeploy on another GPU or datacenter; the same Network "
             "Volume can be reattached.")
print(f"GPU: {torch.cuda.get_device_name(0)}")
PY
then
  exit 1
fi

# 1. Custom nodes
echo "Installing custom nodes..."
NODE_DIR="$COMFYUI_PATH/custom_nodes/comfyui-qwen3-tts"
mkdir -p "$NODE_DIR"
cp "$SCRIPT_DIR/custom_nodes/comfyui-qwen3-tts/"*.py "$NODE_DIR/"

# qwen-tts and its runtime libraries go into ComfyUI's persistent virtualenv, the
# interpreter that runs ComfyUI. A bare `pip` would install into the system Python,
# where ComfyUI never sees them. Create the venv exactly as the image's /start.sh does
# when it is missing, so start.sh then just activates it. PIP_CONSTRAINT pins
# torch/torchvision/torchaudio to the image's builds: nothing here may replace them.
# qwen-tts needs transformers 4.57.3 exactly: its model code uses transformers
# internals that changed in 5.x (check_model_inputs), and it fails to import there
# (tested). The image ships transformers 5.x, so this template pins 4.57.3 in ComfyUI's
# venv; ComfyUI v0.35.0 itself only needs >= 4.50.3 and runs on it (tested). qwen-tts
# then goes in with --no-deps, to skip gradio, which it lists only for its demo app.
QWEN_TTS_PACKAGES=("transformers==4.57.3" "accelerate==1.12.0" "librosa" "soundfile"
                   "sox" "onnxruntime" "einops")
VENV_DIR="$COMFYUI_PATH/${COMFYUI_VENV_NAME:-.venv-cu128}"
CONSTRAINTS=/opt/comfyui-runtime-constraints.txt
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Creating ComfyUI virtualenv $VENV_DIR (as the image's start.sh does)..."
  python3.12 -m venv --system-site-packages --without-pip "$VENV_DIR"
fi
VPY="$VENV_DIR/bin/python"
deps_ok() {
  "$VPY" - "$VENV_DIR" <<'PY'
import importlib, os, sys
venv = os.path.realpath(sys.argv[1])
for name in ("librosa", "soundfile", "einops", "accelerate", "transformers", "torchaudio"):
    importlib.import_module(name)
import transformers
if transformers.__version__ != "4.57.3":
    sys.exit(f"transformers {transformers.__version__} is active; qwen-tts needs 4.57.3.")
# The real test: the Qwen3-TTS model code imports against these transformers.
from qwen_tts import Qwen3TTSModel  # noqa: F401
import torch
if os.path.realpath(torch.__file__).startswith(venv + os.sep):
    sys.exit("PyTorch was installed inside the venv; it must come from the image.")
PY
}
PKG_HASH="$(printf '%s\n' "qwen-tts==$QWEN_TTS_VERSION" "${QWEN_TTS_PACKAGES[@]}" | sha256sum | cut -d' ' -f1)"
MARKER="$VENV_DIR/.qwen3-tts-voiceover-deps"
if [ "$(cat "$MARKER" 2>/dev/null)" = "$PKG_HASH" ] && deps_ok 2>/dev/null; then
  echo "Qwen3-TTS Python packages already installed."
else
  echo "Installing Qwen3-TTS Python packages into $VENV_DIR..."
  constraint_args=()
  if [ -f "$CONSTRAINTS" ]; then
    constraint_args=(-c "$CONSTRAINTS")
  else
    # Older images: pin to whatever PyTorch the image ships.
    CONSTRAINTS="$(mktemp /tmp/qwen3tts-torch-pins.XXXXXX)"
    "$VPY" -c 'import importlib.metadata as m
for p in ("torch", "torchvision", "torchaudio"):
    try: print(f"{p}=={m.version(p)}")
    except m.PackageNotFoundError: pass' > "$CONSTRAINTS"
    constraint_args=(-c "$CONSTRAINTS")
  fi
  if ! "$VPY" -m pip install --no-cache-dir "${constraint_args[@]}" "${QWEN_TTS_PACKAGES[@]}" \
      || ! "$VPY" -m pip install --no-cache-dir --no-deps "qwen-tts==$QWEN_TTS_VERSION"; then
    echo "FATAL: installing the Qwen3-TTS Python packages failed (see pip output above)."
    echo "         Restart the pod to retry."
    exit 1
  fi
  if ! deps_ok; then
    echo "FATAL: qwen-tts does not import in $VENV_DIR (see above)."
    exit 1
  fi
  printf '%s\n' "$PKG_HASH" > "$MARKER"
fi
echo "qwen-tts $QWEN_TTS_VERSION ready."

# 2. Model folders and the voice pool
echo "Preparing model directories..."
MODELS_DIR="$COMFYUI_PATH/models/qwen3-tts"
mkdir -p "$MODELS_DIR"
# The voice pool: every built-in voice rendered once (native language and English),
# with transcripts, for auditioning and as cloning references. Voices you save from
# the workflows go to the same folder. Never overwrites a file already there.
POOL_DIR="$COMFYUI_PATH/input/voices"
mkdir -p "$POOL_DIR"
for voice in "$SCRIPT_DIR/samples/voices/"*; do
  [ -e "$POOL_DIR/$(basename "$voice")" ] || cp "$voice" "$POOL_DIR/"
done
echo "Voice pool: $(ls "$POOL_DIR" | grep -c -E '\.(flac|wav|mp3)$') clips in $POOL_DIR"
# Load Audio only lists files directly in input/: the Add Your Voice workflow opens on
# this copy of a pool clip.
[ -e "$COMFYUI_PATH/input/example_recording.flac" ] \
  || cp "$SCRIPT_DIR/samples/voices/Serena_en.flac" "$COMFYUI_PATH/input/example_recording.flac"

# -------------------------------------------------------------------
# Download helpers
# -------------------------------------------------------------------
# `hf` is only a downloader - ComfyUI never imports it - so it lives in its own venv.
# Upgrading huggingface_hub inside ComfyUI's environment breaks transformers' version
# pin, and ComfyUI then fails to start with "from transformers import CLIPTokenizer".
# Its Xet backend is much faster than wget on multi-GB files but cannot resume a
# partial file, so wget stays as the fallback.
echo "Installing fast downloader (optional)..."
HF_VENV="/workspace/.hf-cli"
HF_BIN=""
if [ ! -x "$HF_VENV/bin/hf" ]; then
  if python3 -m venv "$HF_VENV" 2>/dev/null; then
    "$HF_VENV/bin/pip" install -q -U "huggingface_hub[hf-xet]" 2>/dev/null || true
  fi
fi
for cand in "$HF_VENV/bin/hf" "$HF_VENV/bin/huggingface-cli"; do
  [ -x "$cand" ] && { HF_BIN="$cand"; break; }
done
if [ -n "$HF_BIN" ]; then
  echo "Fast downloader: $HF_BIN (isolated venv)"
else
  echo "Fast downloader unavailable, using wget."
fi

# A complete file: a safetensors header that accounts for every byte, valid JSON, or
# non-empty text (the tokenizer's merges.txt).
file_ok() {
  [ -f "$1" ] || return 1
  "$PY" - "$1" <<'PY'
import json, os, struct, sys
path = sys.argv[1]
kind = path[:-len(".part")] if path.endswith(".part") else path  # wget's staging name
try:
    if kind.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            json.load(f)
        sys.exit(0)
    if kind.endswith(".txt"):
        if os.path.getsize(path) == 0:
            raise ValueError('empty')
        sys.exit(0)
    if os.path.getsize(path) < 1000000:
        raise ValueError('too small')
    with open(path, 'rb') as f:
        size = struct.unpack('<Q', f.read(8))[0]
        if not 2 <= size <= min(os.path.getsize(path) - 8, 100_000_000):
            raise ValueError('invalid header length')
        header = json.loads(f.read(size))
        end = max(v['data_offsets'][1] for k, v in header.items() if k != '__metadata__')
        if end + size + 8 != os.path.getsize(path):
            raise ValueError('incomplete tensor data')
except (OSError, ValueError, KeyError, TypeError, struct.error):
    sys.exit(1)
PY
}

hf_fast() {
  # $1 = repo, $2 = path inside the repo, $3 = destination file
  local repo="$1" rpath="$2" dest="$3" tmp
  [ -n "$HF_BIN" ] || return 1
  # Stage beside the destination so the final move is a rename, not a multi-GB copy.
  tmp="$(mktemp -d "$(dirname "$dest")/.hfdl.XXXXXX")" || return 1
  if HF_XET_HIGH_PERFORMANCE=1 "$HF_BIN" download "$repo" "$rpath" --local-dir "$tmp"; then
    file_ok "$tmp/$rpath" && mv -f "$tmp/$rpath" "$dest"
  fi
  rm -rf "$tmp"
  file_ok "$dest"
}

fetch_url() {
  # $1 = destination file, $2 = URL
  local dest="$1" url="$2" part="$1.part"
  if [ -n "$HF_TOKEN" ]; then
    wget -c -q --show-progress --tries=3 --read-timeout=120 \
      --header="Authorization: Bearer $HF_TOKEN" -O "$part" "$url" || return 1
  else
    wget -c -q --show-progress --tries=3 --read-timeout=120 -O "$part" "$url" || return 1
  fi
  file_ok "$part" && mv -f "$part" "$dest"
}

download_hf() {
  # $1 = Hugging Face repo, $2 = path inside it, $3 = folder under models/qwen3-tts.
  # Files keep their path inside the repo (speech_tokenizer/...), the layout
  # Qwen3TTSModel.from_pretrained loads.
  local repo="$1" rpath="$2" dest="$MODELS_DIR/$3/$2"
  mkdir -p "$(dirname "$dest")"
  if file_ok "$dest"; then
    echo "$3/$rpath already exists, skipping."
    return 0
  fi
  echo "Downloading $3/$rpath ..."
  hf_fast "$repo" "$rpath" "$dest" && { echo "$3/$rpath done."; return 0; }
  echo "  falling back to wget..."
  fetch_url "$dest" "https://huggingface.co/$repo/resolve/main/$rpath" || true
  if ! file_ok "$dest"; then
    echo "ERROR: could not download $3/$rpath. Existing files were retained for retry."
    return 1
  fi
  echo "$3/$rpath done."
}

# -------------------------------------------------------------------
# 3. Model downloads (~13.6 GB, all Apache-2.0)
# -------------------------------------------------------------------
FAILED=0
# Each repo is self-contained: the 1.7B model, its text tokenizer and the 12 Hz speech
# tokenizer (codec) it decodes with.
MODEL_FILES=(config.json generation_config.json merges.txt model.safetensors
             preprocessor_config.json tokenizer_config.json vocab.json
             speech_tokenizer/config.json speech_tokenizer/configuration.json
             speech_tokenizer/model.safetensors speech_tokenizer/preprocessor_config.json)
# CustomVoice: the 9 built-in voices. VoiceDesign: a voice from a description.
# Base: voice cloning from a reference clip.
for model in Qwen3-TTS-12Hz-1.7B-CustomVoice Qwen3-TTS-12Hz-1.7B-VoiceDesign \
             Qwen3-TTS-12Hz-1.7B-Base; do
  for file in "${MODEL_FILES[@]}"; do
    download_hf "Qwen/$model" "$file" "$model" || FAILED=1
  done
done

if [ "$FAILED" = "1" ]; then
  echo "FATAL: one or more model downloads failed (see ERROR lines above)."
  echo "         Restart the pod to retry - finished files are kept and skipped."
  exit 1
fi

# 4. Install bundled workflows into ComfyUI's Workflows sidebar
echo "Installing workflows..."
WF_DEST="$COMFYUI_PATH/user/default/workflows"
mkdir -p "$WF_DEST"
# Workflows shipped under earlier names, and earlier versions of current ones. Each is
# removed only while it is byte-identical to that shipped version, so a copy edited on
# the pod is kept; a current name is then reinstalled at its new version below.
RETIRED_WORKFLOWS="
"
while read -r sum name; do
  [ -n "$name" ] && [ -f "$WF_DEST/$name" ] || continue
  if [ "$(sha256sum "$WF_DEST/$name" | cut -d' ' -f1)" = "$sum" ]; then
    rm -f "$WF_DEST/$name"
    echo "  removed outdated workflow: $name"
  fi
done <<< "$RETIRED_WORKFLOWS"
if [ -d "$SCRIPT_DIR/workflows" ]; then
  # Never overwrite a workflow already edited on the Network Volume.
  for workflow in "$SCRIPT_DIR/workflows/"*.json; do
    [ -e "$WF_DEST/$(basename "$workflow")" ] || cp "$workflow" "$WF_DEST/"
  done
  ls "$WF_DEST" | sed 's/^/  workflow: /'
else
  echo "No workflows directory found in repo, skipping."
fi

# 5. Start ComfyUI using the official RunPod entrypoint
echo "Setup complete! Handing over to start script..."
exec /start.sh
