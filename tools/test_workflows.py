"""CPU checks for every bundled graph: wiring, node schemas, defaults, layout, and that
setup.sh downloads what the loader reads and ships the voice pool.
python tools/test_workflows.py"""
import importlib.util
import json
from pathlib import Path
import re
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
NODE = ROOT / "custom_nodes/comfyui-qwen3-tts"


def load(name, path, package=False):
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


folder_paths = types.ModuleType("folder_paths")
folder_paths.models_dir = "/models"
folder_paths.get_input_directory = lambda: str(ROOT / "samples")   # pool = samples/voices
sys.modules.setdefault("folder_paths", folder_paths)
builder = load("builder", ROOT / "tools/build_workflow.py")
pack = load("comfyui_qwen3_tts", NODE / "__init__.py", package=True)
engine = pack.engine
SETUP = (ROOT / "setup.sh").read_text(encoding="utf-8")
WIDGET = ("INT", "FLOAT", "BOOLEAN", "STRING")
CORE = {  # ComfyUI v0.35.0 core nodes used: (widgets, sockets)
    "LoadAudio": (["audio", "audioUI", "upload"], []),
    "PrimitiveStringMultiline": (["value"], []),
}


class WorkflowTests(unittest.TestCase):
    def each(self):
        for w in builder.WORKFLOWS:
            wf = builder.build(w["kind"])
            yield w, wf, {n["id"]: n for n in wf["nodes"]}

    def links(self, wf, nodes):
        out = {}
        for lid, src, slot, dst, port, kind in wf["links"]:
            o, i = nodes[src]["outputs"][slot], nodes[dst]["inputs"][port]
            self.assertEqual((o["type"], i["type"], i["link"]), (kind, kind, lid))
            self.assertIn(lid, o["links"])
            out[(dst, i["name"])] = (src, o["name"])
        return out

    def test_shipped_files_match_builder(self):
        shipped = {p.name for p in (ROOT / "workflows").glob("*.json")}
        self.assertEqual(shipped, {w["path"] for w in builder.WORKFLOWS})
        self.assertEqual(len({w["id"] for w in builder.WORKFLOWS}), len(builder.WORKFLOWS))
        for w, wf, _ in self.each():
            path = ROOT / "workflows" / w["path"]
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), wf, w["path"])

    def test_nodes_match_their_schema(self):
        for w, wf, nodes in self.each():
            for node in nodes.values():
                if node["type"] == "MarkdownNote":
                    continue
                with self.subTest(workflow=w["path"], node=node["type"]):
                    if node["type"] in CORE:
                        widgets, _ = CORE[node["type"]]
                        self.assertEqual(len(node["widgets_values"]), len(widgets))
                        continue
                    cls = pack.NODE_CLASS_MAPPINGS[node["type"]]
                    schema = cls.INPUT_TYPES()
                    inputs = {**schema.get("required", {}), **schema.get("optional", {})}
                    self.assertEqual(tuple(o["type"] for o in node["outputs"]), cls.RETURN_TYPES)
                    widgets = []
                    for name, spec in inputs.items():
                        if isinstance(spec[0], list) or spec[0] in WIDGET:
                            widgets.append(name)
                            if name == "seed":
                                widgets.append("control_after_generate")
                    sockets = [n for n in inputs if n not in widgets]
                    for inp in node["inputs"]:
                        self.assertIn(inp["name"], inputs)
                        if inp["name"] in sockets:
                            self.assertNotIn("widget", inp)
                        else:
                            self.assertIn("widget", inp)   # a widget converted to an input
                    self.assertEqual(len(widgets), len(node["widgets_values"]))
                    for name, value in zip(widgets, node["widgets_values"]):
                        spec = inputs.get(name)
                        if spec and isinstance(spec[0], list) and name != "pool_voice":
                            self.assertIn(value, spec[0], name)

    def test_wiring_and_defaults(self):
        expected = {
            "builtin": {(20, "tts"): (10, "tts"), (30, "audio"): (20, "audio")},
            "design": {(20, "tts"): (10, "tts"), (20, "text"): (15, "STRING"),
                       (30, "transcript"): (15, "STRING"), (30, "audio"): (20, "audio")},
            "clone": {(20, "tts"): (10, "tts"), (30, "audio"): (20, "audio")},
            "add_voice": {(30, "audio"): (20, "AUDIO")},
        }
        models = {"builtin": engine.MODEL_CUSTOM, "design": engine.MODEL_DESIGN,
                  "clone": engine.MODEL_BASE}
        for w, wf, nodes in self.each():
            with self.subTest(workflow=w["path"]):
                self.assertEqual(self.links(wf, nodes), expected[w["kind"]])
                if w["kind"] in models:
                    self.assertEqual(nodes[10]["widgets_values"], [models[w["kind"]], "sdpa"])
        # Defaults name real things: a built-in voice, a pool clip, the example recording.
        clone = {n["id"]: n for n in builder.build("clone")["nodes"]}
        self.assertIn(clone[20]["widgets_values"][1], engine.pool_voices(
            str(ROOT / "samples" / "voices")))
        builtin = {n["id"]: n for n in builder.build("builtin")["nodes"]}
        self.assertIn(builtin[20]["widgets_values"][1], engine.SPEAKERS)
        self.assertEqual(set(builder.MODELS), set(engine.MODELS.values()))
        self.assertEqual((builder.MODEL_CUSTOM, builder.MODEL_DESIGN, builder.MODEL_BASE),
                         (engine.MODEL_CUSTOM, engine.MODEL_DESIGN, engine.MODEL_BASE))
        example = (ROOT / "samples" / "voices" / "Serena_en.txt").read_text(encoding="utf-8")
        self.assertEqual(example.strip(), builder.EXAMPLE_TRANSCRIPT)

    def test_setup_downloads_what_the_loader_reads(self):
        loop = re.search(r"for model in (.*?); do", SETUP, re.S).group(1)
        self.assertEqual(loop.replace("\\", " ").split(), builder.MODELS)
        files = re.search(r"MODEL_FILES=\((.*?)\)", SETUP, re.S).group(1).split()
        for needed in ("config.json", "model.safetensors", "vocab.json", "merges.txt",
                       "speech_tokenizer/model.safetensors", "speech_tokenizer/config.json"):
            self.assertIn(needed, files)
        self.assertIn(f'QWEN_TTS_VERSION="${{QWEN_TTS_VERSION:-{builder.QWEN_TTS_VERSION}}}"',
                      SETUP)
        self.assertIn('"$SCRIPT_DIR/samples/voices/"*', SETUP)
        self.assertIn(builder.EXAMPLE_RECORDING, SETUP)

    def test_layout_is_spaced_grouped_and_expanded(self):
        title = 40
        for w, wf, nodes in self.each():
            boxes = {nid: (n["pos"][0], n["pos"][1] - title, n["pos"][0] + n["size"][0],
                           n["pos"][1] + n["size"][1]) for nid, n in nodes.items()}
            ids = sorted(boxes)
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    ax0, ay0, ax1, ay1 = boxes[a]
                    bx0, by0, bx1, by1 = boxes[b]
                    self.assertFalse(ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1,
                                     (w["path"], a, b))


class StandaloneNotesTests(unittest.TestCase):
    """Every workflow stands alone: its notes and titles never mention another model,
    template or workflow."""

    def test_no_cross_references(self):
        pattern = re.compile(r"\b(LongCat|FlashHead|H3|MiniMax|InfiniteTalk|Lite)\b|\bworkflows? [0-9]|"
                             r"other (workflow|template)|avatar templates", re.I)
        for path in sorted((ROOT / "workflows").glob("*.json")):
            wf = json.loads(path.read_text(encoding="utf-8"))
            for node in wf["nodes"]:
                texts = [node.get("title") or ""]
                if node["type"] == "MarkdownNote":
                    texts += [v for v in node.get("widgets_values", []) if isinstance(v, str)]
                for text in texts:
                    hit = pattern.search(text)
                    self.assertIsNone(hit, f"{path.name} node {node['id']}: "
                                      f"{hit and hit.group(0)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
