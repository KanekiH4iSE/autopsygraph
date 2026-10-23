"""Milestone 4 checks against the loaded graph (skipped when no Neo4j is configured)."""
import os

import pytest
from dotenv import load_dotenv

load_dotenv()
pytestmark = pytest.mark.skipif(not os.environ.get("NEO4J_URI"), reason="no Neo4j configured")


@pytest.mark.parametrize("run_id,step,pattern", [
    ("run_017", 2, "FP04"),
    ("run_087", 2, "FP03"),
    ("run_066", 2, "FP05"),
])
def test_hero_roots(run_id, step, pattern):
    from forensics.detectors import run_all
    from forensics.divergence import find_root
    root = find_root(run_all(run_id))
    assert (root.step_idx, root.pattern) == (step, pattern)


def test_run_017_contributing():
    from forensics.detectors import run_all
    from forensics.divergence import find_root
    root = find_root(run_all("run_017"))
    assert {(h.pattern, h.step_idx) for h in root.contributing} >= {("FP07", 3), ("FP06", 4), ("FP12", 4)}


def test_success_run_has_no_decisive_hits():
    from forensics.detectors import run_all
    assert [h for h in run_all("run_003") if h.severity == 3] == []


def test_claims_run_017():
    from forensics.claims import claim_verdicts
    rows = claim_verdicts("run_017")
    assert rows[0]["verdict"] == "MISMATCH" and rows[0]["stale"] is True
