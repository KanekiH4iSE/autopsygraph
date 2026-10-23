"""First divergence: pick the earliest decisive step among detector hits (CLAUDE.md section 10.2)."""
from __future__ import annotations

from dataclasses import dataclass, field

from forensics.detectors import Hit

# When several decisive hits share the root step, the pattern listed first wins.
PRIORITY = ["FP04", "FP02", "FP03", "FP01", "FP07", "FP05", "FP10", "FP06", "FP12", "FP11"]


@dataclass
class Root:
    step_idx: int | None
    pattern: str | None
    root_hits: list[Hit] = field(default_factory=list)
    contributing: list[Hit] = field(default_factory=list)

    @property
    def agreeing_detectors(self) -> int:
        return len({h.detector for h in self.root_hits})


def _rank(h: Hit) -> tuple:
    return (-h.severity, PRIORITY.index(h.pattern) if h.pattern in PRIORITY else len(PRIORITY))


def find_root(hits: list[Hit]) -> Root:
    """Root = earliest severity-3 hit (wrong entity counts as decisive). An ignored error always wins:
    later unsafe actions are its symptoms. With no decisive hit, fall back to the earliest hit at all."""
    if not hits:
        return Root(None, None)
    ignored = [h for h in hits if h.pattern == "FP04"]
    decisive = ignored or [h for h in hits if h.severity == 3 or h.pattern == "FP03"] or hits
    step = min(h.step_idx for h in decisive)
    at_root = sorted([h for h in hits if h.step_idx == step], key=_rank)
    head = sorted([h for h in decisive if h.step_idx == step], key=_rank)[0]
    contributing = [h for h in hits if h.step_idx > step or (h.step_idx == step and h.pattern != head.pattern)]
    return Root(step, head.pattern, at_root, contributing)
