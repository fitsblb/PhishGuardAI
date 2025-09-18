from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from pymongo.collection import Collection
else:
    try:
        from pymongo.collection import Collection
    except ImportError:  # pragma: no cover
        Collection = Any  # fallback typing if pymongo isn't installed


# ---- Records (structured, easy to test / serialize) ----
@dataclass
class DecisionRecord:
    url: str
    p_malicious: float
    policy_thresholds: Dict[str, float]
    policy_decision: str
    final_decision: str
    created_at: datetime


@dataclass
class JudgeRecord:
    url: str
    verdict: str
    rationale: str
    judge_score: Optional[float]
    features: Dict[str, Any]
    created_at: datetime


# ---- Writer (Mongo or in-memory stub) ----
class AuditWriter:
    def __init__(
        self,
        decisions: Optional[Collection] = None,
        rationales: Optional[Collection] = None,
    ):
        self._decisions = decisions
        self._rationales = rationales

    def log_decision(self, rec: DecisionRecord) -> None:
        doc = asdict(rec)
        if self._decisions is not None:
            try:
                self._decisions.insert_one(
                    doc
                )  # nosec B110 - deliberate fail-open audit write
            except Exception:
                pass  # nosec B110

    def log_judge(self, rec: JudgeRecord) -> None:
        doc = asdict(rec)
        if self._rationales is not None:
            try:
                self._rationales.insert_one(
                    doc
                )  # nosec B110 - deliberate fail-open audit write
            except Exception:
                pass  # nosec B110
