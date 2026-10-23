"""Milestone 2 checks: 36 valid traces, labels only on failures, deterministic output."""
import hashlib
import json

from datagen.generate import generate
from datagen.world import DATA
from graph.models import Trace


def _digest() -> str:
    h = hashlib.sha256()
    for f in sorted((DATA / "traces").glob("*.json")):
        h.update(f.read_bytes())
    return h.hexdigest()


def test_counts_and_labels():
    traces = generate()
    assert len(traces) == 36
    fails = [t for t in traces if t["label"]["injected_pattern"]]
    assert len(fails) == 24
    counts = {}
    for t in fails:
        counts[t["label"]["injected_pattern"]] = counts.get(t["label"]["injected_pattern"], 0) + 1
        assert t["label"]["root_cause_step"] is not None
    assert counts == {"FP04": 7, "FP03": 6, "FP05": 5, "FP07": 3, "FP01": 3}
    for t in traces:
        Trace.model_validate(t)


def test_heroes():
    generate()
    t17 = json.loads((DATA / "traces" / "run_017.json").read_text())
    assert t17["label"] == {"injected_pattern": "FP04", "root_cause_step": 2,
                            "contributing": ["FP07@3", "FP06@4", "FP12@4"]}
    assert t17["final_answer"]["claims"][0]["supported_by"] == ["run_017-e3"]
    t87 = json.loads((DATA / "traces" / "run_087.json").read_text())
    assert t87["steps"][1]["tool_call"]["args"][0]["value"] == "C-019"
    t66 = json.loads((DATA / "traces" / "run_066.json").read_text())
    assert t66["label"]["root_cause_step"] == 2
    t03 = json.loads((DATA / "traces" / "run_003.json").read_text())
    assert t03["label"]["injected_pattern"] is None


def test_deterministic():
    generate()
    a = _digest()
    generate()
    assert _digest() == a
