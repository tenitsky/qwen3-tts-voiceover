#!/usr/bin/env python3
"""
Generate the Qwen3-TTS workflow JSON files. Re-run after editing:

    python tools/build_workflow.py

  1 Built-in Voice   one of the 9 built-in voices reads a script of any length
  2 Voice Design     a new voice from a description, saved to the voice pool
  3 Voice Clone      any pool voice reads a script of any length, the same throughout
  4 Add Your Voice   a recording of your own (or anyone you may clone) into the pool

Layout: numbered stages from left to right, each a coloured group with a note
underneath, and a "Start here" note on the far left. Nothing is collapsed.
"""

import json
import os

WORKFLOW_DIR = os.path.join(os.path.dirname(__file__), "..", "workflows")
QWEN_TTS_VERSION = "0.1.1"
LF = "comfyui-qwen3-tts"

MODELS = ["Qwen3-TTS-12Hz-1.7B-CustomVoice", "Qwen3-TTS-12Hz-1.7B-VoiceDesign",
          "Qwen3-TTS-12Hz-1.7B-Base"]
MODEL_CUSTOM = "CustomVoice (9 built-in voices)"
MODEL_DESIGN = "VoiceDesign (voice from a description)"
MODEL_BASE = "Base (voice clone)"

EXAMPLE_RECORDING = "example_recording.flac"   # a copy of the Serena_en pool clip
EXAMPLE_TRANSCRIPT = ("Hello, and welcome. This is a short sample of my voice, so you can "
                      "hear how I sound before you choose me for your next voiceover.")

SCRIPT = """Welcome back. Today we are looking at something that changed how people tell stories: the human voice, recorded, shaped and shared.

A voiceover is more than words read aloud. Pace, warmth and the small pauses between sentences decide whether a listener leans in or drifts away. So take your time, and let every sentence land.

When you are ready, paste your own script here. It can be as long as you need: it is rendered in parts at sentence and paragraph breaks, and joined back together with natural pauses."""

DESIGN_SAMPLE = ("Hi, I'm the voice you just described. Listen to how I sound, and if you "
                 "like me, I'll be waiting in the voice pool for your next script.")

WORKFLOWS = [
    dict(kind="builtin", path="qwen3tts_1_builtin_voice.json",
         id="3f2c9a71-6b4e-4d1a-9c8f-2e7b5a1d0c31"),
    dict(kind="design", path="qwen3tts_2_voice_design.json",
         id="8a1d4e62-0f3b-4c7a-b2e9-5d6c3f1a7b42"),
    dict(kind="clone", path="qwen3tts_3_voice_clone.json",
         id="c5e7b913-2d4f-4a8e-8b1c-9f0a6e3d2c53"),
    dict(kind="add_voice", path="qwen3tts_4_add_your_voice.json",
         id="e9b3c825-7a1f-4e6d-a5c2-1b8d4f0e9a64"),
]

TITLES = {
    "builtin": "Built-in Voice",
    "design": "Voice Design",
    "clone": "Voice Clone",
    "add_voice": "Add Your Voice to the Pool",
}

# ------------------------------------------------------------------------ notes
NOTE_ABOUT = """## About Qwen3-TTS

Qwen's open text-to-speech models (Apache-2.0), 1.7B parameters, 10 languages: English, Chinese, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian.

- **CustomVoice** - 9 built-in voices, steerable with a style instruction.
- **VoiceDesign** - a new voice from a written description.
- **Base** - clones a voice from a short clip and its transcript.

**The voice pool** is `ComfyUI/input/voices/`: every built-in voice rendered in its native language and in English (`Vivian`, `Vivian_en`, ...), plus the voices you design or add. Each clip has its transcript next to it, so it can be cloned.

Long scripts are rendered in parts at sentence and paragraph breaks and joined with pauses; one part is at most about 2.5 minutes of speech.

Code: https://github.com/QwenLM/Qwen3-TTS"""

VOICES_TABLE = """| Voice | Native | Character |
|---|---|---|
| Ryan | English | dynamic male, strong rhythm |
| Aiden | English | sunny American male |
| Vivian | Chinese | bright young female |
| Serena | Chinese | warm, gentle young female |
| Uncle_Fu | Chinese | seasoned male, low and mellow |
| Dylan | Chinese | youthful Beijing male |
| Eric | Chinese | lively Chengdu male |
| Ono_Anna | Japanese | playful Japanese female |
| Sohee | Korean | warm Korean female |

Every voice speaks every language, best in its native one. Hear them all: the pool clips in `input/voices/`."""

NOTE_MODEL = """## Model - loaded once

The three 1.7B models are downloaded by setup to `ComfyUI/models/qwen3-tts/`. One is kept loaded between runs (about 4 GB of VRAM); switching to a workflow with another model reloads in seconds. Each node checks that the loader holds the right model.

**attention:** `sdpa` works everywhere; `flash_attention_2` only if flash-attn is installed."""

NOTE_OUTPUT = """## Save

The voiceover is saved as `output/voiceover/<prefix>_00001.wav` and `.mp3`, and plays on the node. Use the WAV as the voiceover for the LongCat or FlashHead avatar templates."""

NOTES = {
    "builtin": f"""## Speak

Pick a **voice**, set the **language** (or Auto), paste the **script**.

**style** (optional) steers the delivery: *Calm, warm narration, unhurried.* *Excited and fast.* *Whispering.*

{VOICES_TABLE}

**seed** is fixed: the same script, voice and seed give the same read. Change it for another take.""",
    "design": """## Design a voice

Describe the voice: **age, gender, accent, timbre, mood, pace**. For example: *A deep, gravelly male voice in his fifties with a slow, deliberate Texan drawl.*

The node reads the short **sample text** in that voice. Like it? It is saved to the **voice pool** under **voice_name**, with its transcript, so **Voice Clone** (workflow 3) can read whole scripts in exactly this voice. Not quite right? Change the description or the seed and run again (turn on overwrite).

VoiceDesign can render a long script directly too, but its voice may vary a little between parts; cloning the saved sample keeps it identical.""",
    "clone": """## Clone a voice

Pick a **pool_voice**: any built-in voice (`Ryan`, or `Vivian_en` for Vivian's English recording) or one you designed or added. The pool clip and its transcript are the reference; the voice is analysed once and used for every part, so a long script stays the same voice throughout.

**Your own clip instead:** connect a Load Audio to **reference_audio** and type its exact transcript in **reference_text**, or add it to the pool with workflow 4.

New pool voices appear after refreshing the browser (R).""",
    "add_voice": f"""## Add a voice to the pool

Upload a clean recording, **3-20 seconds**, one person speaking, no music, then type **exactly** what it says in **transcript**. Saved as `input/voices/<voice_name>.flac` + `.txt`, ready for **Voice Clone** (workflow 3).

The workflow opens on `{EXAMPLE_RECORDING}` (a copy of the pool's Serena_en) with its transcript, so you can see it work. Only clone voices you have the right to use.""",
}


def note_start(w):
    steps = {
        "builtin": ["**Voice** - one of the 9 built-in voices (table in stage 2).",
                    "**Script** - paste it; blank lines separate paragraphs.",
                    "**Run.** The voiceover plays on the Save node."],
        "design": ["**voice_description** - who is speaking and how.",
                   "**Run.** Listen to the sample on the Save to Voice Pool node.",
                   "Happy with it? Use **Voice Clone** (workflow 3) with the new pool voice "
                   "for whole scripts."],
        "clone": ["**pool_voice** - a built-in voice or one you designed or added.",
                  "**Script** - paste it; blank lines separate paragraphs.",
                  "**Run.** The voiceover plays on the Save node."],
        "add_voice": ["**Load Audio** - upload your recording (3-20 s, clean).",
                      "**transcript** - exactly what it says; **voice_name** - its name.",
                      "**Run**, then use it in **Voice Clone** (workflow 3)."],
    }[w["kind"]]
    lines = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    return f"""# Qwen3-TTS - {TITLES[w['kind']]}

**Red nodes are the ones you set.** Stages run left to right with a note under each.

{lines}

Full instructions: https://github.com/tenitsky/qwen3-tts-voiceover"""


# ------------------------------------------------------------------------ graph
class Graph:
    def __init__(self):
        self.nodes, self.links = [], []
        self._link_id = 0

    def node(self, nid, ntype, inputs=(), outputs=(), widgets=None, title=None,
             color=None, cnr="comfy-core", mode=0, size=(440, 100)):
        props = {"Node name for S&R": ntype}
        if cnr:
            props["cnr_id"] = cnr
        n = {
            "id": nid, "type": ntype, "pos": [0, 0], "size": list(size),
            "flags": {}, "order": len(self.nodes), "mode": mode,
            "inputs": [dict({"localized_name": nm, "name": nm, "type": tp, "link": None},
                            **({"widget": {"name": nm}} if wid else {}),
                            **({"shape": 7} if opt else {}))
                       for nm, tp, wid, opt in inputs],
            "outputs": [{"localized_name": nm, "name": nm, "type": tp, "links": []}
                        for nm, tp in outputs],
            "properties": props,
        }
        if title:
            n["title"] = title
        if widgets is not None:
            n["widgets_values"] = widgets
        if color:
            n["color"], n["bgcolor"] = color
        self.nodes.append(n)
        return nid

    def link(self, src, src_slot, dst, dst_name):
        s = next(n for n in self.nodes if n["id"] == src)
        d = next(n for n in self.nodes if n["id"] == dst)
        if isinstance(src_slot, str):
            src_slot = next(i for i, o in enumerate(s["outputs"]) if o["name"] == src_slot)
        out = s["outputs"][src_slot]
        slot = next(i for i, inp in enumerate(d["inputs"]) if inp["name"] == dst_name)
        inp = d["inputs"][slot]
        if inp["link"] is not None:
            raise ValueError(f"{d['type']}.{dst_name} already linked")
        if inp["type"] != out["type"]:
            raise ValueError(f"type mismatch {s['type']}.{out['name']} ({out['type']})"
                             f" -> {d['type']}.{dst_name} ({inp['type']})")
        self._link_id += 1
        lid = self._link_id
        inp["link"] = lid
        out["links"].append(lid)
        self.links.append([lid, src, src_slot, dst, slot, out["type"]])


def md(g, nid, title, text, size):
    g.node(nid, "MarkdownNote", widgets=[text], title=title, cnr=None,
           color=("#222", "#000"), size=size)


COLUMN_W, NODE_W, GAP_X, GAP_Y, TITLE_H, PAD = 560, 500, 140, 50, 120, 30
STAGE_COLORS = {"model": "#3f789e", "speak": "#a1309b", "output": "#8a4a4a",
                "input": "#b06634"}


def lay_out(g, stages, start_notes):
    nodes = {n["id"]: n for n in g.nodes}
    groups = []
    x = y = 0
    for nid in start_notes:
        nodes[nid]["pos"] = [x, y]
        y += nodes[nid]["size"][1] + GAP_Y
    x += COLUMN_W + GAP_X
    for gid, (title, color, ids, notes) in enumerate(stages, 1):
        y = TITLE_H
        for nid in ids:
            nodes[nid]["pos"] = [x + PAD, y]
            y += nodes[nid]["size"][1] + GAP_Y
        bottom = y - GAP_Y + PAD
        groups.append({"id": gid, "title": title, "bounding": [x, 0, COLUMN_W, bottom],
                       "color": STAGE_COLORS[color], "font_size": 26, "flags": {}})
        y = bottom + 60
        for nid in notes:
            nodes[nid]["pos"] = [x, y]
            nodes[nid]["size"][0] = COLUMN_W
            y += nodes[nid]["size"][1] + GAP_Y
        x += COLUMN_W + GAP_X
    return groups


GAPS = [400, 0.25, 0.6]   # max_chars_per_part, sentence_gap, paragraph_gap
SEED = [42, "fixed"]


def build(kind):
    w = next(w for w in WORKFLOWS if w["kind"] == kind)
    g = Graph()
    INPUT = ("#322", "#533")    # red: things you set
    I, W = False, True

    def size(h):
        return (NODE_W, h)

    md(g, 1, "Start here", note_start(w), (COLUMN_W, 520))
    md(g, 2, "About Qwen3-TTS", NOTE_ABOUT, (COLUMN_W, 560))
    loader_model = {"builtin": MODEL_CUSTOM, "design": MODEL_DESIGN, "clone": MODEL_BASE}

    if kind != "add_voice":
        g.node(10, "Qwen3TTSLoader", outputs=[("tts", "QWEN3TTS")],
               widgets=[loader_model[kind], "sdpa"],
               title=f"Qwen3-TTS {loader_model[kind].split(' ')[0]} (loaded once)", cnr=LF,
               size=size(110))
        md(g, 3, "About the model", NOTE_MODEL, (COLUMN_W, 300))

    if kind == "builtin":
        g.node(20, "Qwen3TTSBuiltinVoice", inputs=[("tts", "QWEN3TTS", I, False)],
               outputs=[("audio", "AUDIO")],
               widgets=[SCRIPT, "Ryan", "English", ""] + SEED + GAPS,
               title="Built-in Voice (voice, language, script)", color=INPUT, cnr=LF,
               size=size(620))
        g.node(30, "Qwen3TTSSave", inputs=[("audio", "AUDIO", I, False)],
               outputs=[("wav_path", "STRING")], widgets=["builtin_voice"],
               title="Save voiceover (WAV + MP3)", cnr=LF, size=size(220))
        g.link(10, 0, 20, "tts")
        g.link(20, 0, 30, "audio")
        md(g, 4, "About stage 2", NOTES[kind], (COLUMN_W, 860))
        md(g, 5, "About stage 3", NOTE_OUTPUT, (COLUMN_W, 220))
        stages = [("1. Model", "model", [10], [3]), ("2. Speak", "speak", [20], [4]),
                  ("3. Save", "output", [30], [5])]
    elif kind == "design":
        g.node(15, "PrimitiveStringMultiline", outputs=[("STRING", "STRING")],
               widgets=[DESIGN_SAMPLE], title="Sample text (also the pool transcript)",
               color=INPUT, size=size(180))
        g.node(20, "Qwen3TTSVoiceDesign",
               inputs=[("tts", "QWEN3TTS", I, False), ("text", "STRING", W, False)],
               outputs=[("audio", "AUDIO")],
               widgets=[DESIGN_SAMPLE,
                        "A calm, warm female narrator in her thirties, clear and friendly, "
                        "speaking at a relaxed pace.", "English"] + SEED + GAPS,
               title="Voice Design (describe the voice)", color=INPUT, cnr=LF,
               size=size(520))
        g.node(30, "Qwen3TTSSaveToPool",
               inputs=[("audio", "AUDIO", I, False), ("transcript", "STRING", W, False)],
               outputs=[("audio", "AUDIO"), ("voice_name", "STRING")],
               widgets=["my_designed_voice", DESIGN_SAMPLE, False],
               title="Save to Voice Pool (name it)", color=INPUT, cnr=LF, size=size(260))
        g.link(10, 0, 20, "tts")
        g.link(15, 0, 20, "text")
        g.link(15, 0, 30, "transcript")
        g.link(20, 0, 30, "audio")
        md(g, 4, "About stage 2", NOTES[kind], (COLUMN_W, 560))
        stages = [("1. Model", "model", [10], [3]), ("2. Design", "speak", [15, 20], [4]),
                  ("3. Save to the pool", "output", [30], [])]
    elif kind == "clone":
        g.node(20, "Qwen3TTSVoiceClone",
               inputs=[("tts", "QWEN3TTS", I, False), ("reference_audio", "AUDIO", I, True)],
               outputs=[("audio", "AUDIO")],
               widgets=[SCRIPT, "Serena_en", "English"] + SEED + GAPS + [""],
               title="Voice Clone (pool voice, script)", color=INPUT, cnr=LF, size=size(660))
        g.node(30, "Qwen3TTSSave", inputs=[("audio", "AUDIO", I, False)],
               outputs=[("wav_path", "STRING")], widgets=["cloned_voice"],
               title="Save voiceover (WAV + MP3)", cnr=LF, size=size(220))
        g.link(10, 0, 20, "tts")
        g.link(20, 0, 30, "audio")
        md(g, 4, "About stage 2", NOTES[kind], (COLUMN_W, 520))
        md(g, 5, "About stage 3", NOTE_OUTPUT, (COLUMN_W, 220))
        stages = [("1. Model", "model", [10], [3]), ("2. Clone", "speak", [20], [4]),
                  ("3. Save", "output", [30], [5])]
    else:  # add_voice
        g.node(20, "LoadAudio", outputs=[("AUDIO", "AUDIO")],
               widgets=[EXAMPLE_RECORDING, None, None], title="Load your recording",
               color=INPUT, size=size(160))
        g.node(30, "Qwen3TTSSaveToPool", inputs=[("audio", "AUDIO", I, False)],
               outputs=[("audio", "AUDIO"), ("voice_name", "STRING")],
               widgets=["my_voice", EXAMPLE_TRANSCRIPT, False],
               title="Save to Voice Pool (name + transcript)", color=INPUT, cnr=LF,
               size=size(300))
        g.link(20, 0, 30, "audio")
        md(g, 4, "About this workflow", NOTES[kind], (COLUMN_W, 420))
        stages = [("1. Your recording", "input", [20], []),
                  ("2. Save to the pool", "output", [30], [4])]

    groups = lay_out(g, stages, [1, 2])
    return {
        "id": w["id"], "revision": 0,
        "last_node_id": max(n["id"] for n in g.nodes), "last_link_id": g._link_id,
        "nodes": g.nodes, "links": g.links, "groups": groups, "config": {},
        "extra": {"ds": {"scale": 0.6, "offset": [80, 80]}}, "version": 0.4,
    }


if __name__ == "__main__":
    os.makedirs(WORKFLOW_DIR, exist_ok=True)
    for w in WORKFLOWS:
        wf = build(w["kind"])
        path = os.path.join(WORKFLOW_DIR, w["path"])
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(wf, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {os.path.normpath(path)}: {len(wf['nodes'])} nodes, "
              f"{len(wf['links'])} links")
