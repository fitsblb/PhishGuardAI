from __future__ import annotations

from collections import Counter
from typing import Dict

# Simple process-wide counters (sufficient for local/demo use)
_decisions: Counter[str] = Counter()
_judge_verdicts: Counter[str] = Counter()


def inc_decision(kind: str) -> None:
    # kind in {"ALLOW","REVIEW","BLOCK"}
    _decisions[kind] += 1


def inc_judge(verdict: str) -> None:
    # verdict in {"LEAN_PHISH","LEAN_LEGIT","UNCERTAIN"}
    _judge_verdicts[verdict] += 1


def snapshot() -> Dict[str, Dict[str, int]]:
    return {"decisions": dict(_decisions), "judge_verdicts": dict(_judge_verdicts)}
