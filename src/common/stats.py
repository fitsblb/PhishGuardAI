from __future__ import annotations

from collections import Counter
from typing import Dict

_policy: Counter[str] = Counter()  # ALLOW | REVIEW | BLOCK (policy band)
_final: Counter[str] = (
    Counter()
)  # ALLOW | BLOCK (after judge mapping; REVIEW possible if judge uncertain)
_judge: Counter[str] = Counter()  # LEAN_PHISH | LEAN_LEGIT | UNCERTAIN


def inc_policy(kind: str) -> None:
    _policy[kind] += 1


def inc_final(kind: str) -> None:
    _final[kind] += 1


def inc_judge(verdict: str) -> None:
    _judge[verdict] += 1


def snapshot() -> Dict[str, Dict[str, int]]:
    return {
        "policy_decisions": dict(_policy),
        "final_decisions": dict(_final),
        "judge_verdicts": dict(_judge),
    }


def reset() -> None:
    _policy.clear()
    _final.clear()
    _judge.clear()
