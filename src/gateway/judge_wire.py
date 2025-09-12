from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from common.stats import inc_final, inc_judge, inc_policy
from common.thresholds import Thresholds, decide  # your existing loader & policy
from judge_svc.adapter import judge_url_llm
from judge_svc.contracts import FeatureDigest, JudgeRequest, JudgeResponse
from judge_svc.stub import judge_url as judge_url_stub

Decision = Literal["ALLOW", "REVIEW", "BLOCK"]

# --- Judge backend selection ---
_JUDGE_BACKEND = os.getenv("JUDGE_BACKEND", "stub").lower()


def _select_judge():
    return judge_url_llm if _JUDGE_BACKEND == "llm" else judge_url_stub


_JUDGE_FN = _select_judge()

# --- optional Mongo logging (no-op if env not set) ---
_MONGO_URI = os.getenv("MONGO_URI")
_MONGO_DB = os.getenv("MONGO_DB", "phishguard")
_mongo = None
_decisions = None
_rationales = None

if _MONGO_URI:
    try:
        from pymongo import ASCENDING, MongoClient

        _mongo = MongoClient(_MONGO_URI, serverSelectionTimeoutMS=1500)
        if _mongo is not None:
            _db = _mongo[_MONGO_DB]
            _decisions = _db["decisions"]
            _rationales = _db["judge_rationales"]
            _decisions.create_index([("created_at", ASCENDING)])
            _rationales.create_index([("created_at", ASCENDING)])
    except Exception:
        _mongo = None  # fail open if Mongo unavailable in local demos  # nosec B110
        _decisions = None
        _rationales = None


# --- tiny URL feature helpers (deterministic, matches training features) ---
def _url_len(s: str) -> int:
    return len(s) if isinstance(s, str) else 0


def _digit_ratio(s: str) -> float:
    if not isinstance(s, str) or not s:
        return 0.0
    d = sum(ch.isdigit() for ch in s)
    return d / len(s)


def _subdomain_count(s: str) -> int:
    if not isinstance(s, str) or not s:
        return 0
    host = s.split("://", 1)[-1].split("/", 1)[0]
    return max(0, host.count(".") - 1)


@dataclass
class JudgeOutcome:
    final_decision: Decision
    policy_reason: str  # why ALLOW/BLOCK/REVIEW from policy/judge
    judge: Optional[JudgeResponse]  # None if not invoked


def decide_with_judge(
    url: str,
    p_malicious: float,
    th: Thresholds,
    extras: Optional[Dict[str, Any]] = None,
) -> JudgeOutcome:
    """
    Apply policy band first; if REVIEW, invoke judge and map verdict:
      LEAN_PHISH -> BLOCK, LEAN_LEGIT -> ALLOW, UNCERTAIN -> REVIEW
    """
    base_decision: Decision = decide(p_malicious, th)  # uses low/high
    inc_policy(base_decision)
    if base_decision != "REVIEW":
        inc_final(base_decision)  # final == policy when not REVIEW
        return JudgeOutcome(
            final_decision=base_decision, policy_reason="policy-band", judge=None
        )

    # Build the compact digest (URL-only; optional extras may include
    # TLDLegitimateProb, etc.)
    digest = FeatureDigest(
        url_len=_url_len(url),
        url_digit_ratio=_digit_ratio(url),
        url_subdomains=_subdomain_count(url),
        TLDLegitimateProb=(extras or {}).get("TLDLegitimateProb"),
        NoOfOtherSpecialCharsInURL=(extras or {}).get("NoOfOtherSpecialCharsInURL"),
        SpacialCharRatioInURL=(extras or {}).get("SpacialCharRatioInURL"),
        CharContinuationRate=(extras or {}).get("CharContinuationRate"),
        URLCharProb=(extras or {}).get("URLCharProb"),
    )
    req = JudgeRequest(url=url, features=digest)
    jr = _JUDGE_FN(req)  # uses selected judge backend (stub or llm)

    # Map judge verdict to final decision
    if jr.verdict == "LEAN_PHISH":
        final: Decision = "BLOCK"
        reason = "judge-lean-phish"
    elif jr.verdict == "LEAN_LEGIT":
        final = "ALLOW"
        reason = "judge-lean-legit"
    else:
        final = "REVIEW"
        reason = "judge-uncertain"

    # Track judge verdict and final decision
    inc_judge(jr.verdict)
    inc_final(final)

    # Optional: write audit logs if Mongo is configured
    if _mongo and _decisions and _rationales:
        try:
            from datetime import datetime

            doc_dec = {
                "url": url,
                "p_malicious": p_malicious,
                "policy_thresholds": dict(th),
                "policy_decision": base_decision,
                "final_decision": final,
                "created_at": datetime.utcnow(),
            }
            _decisions.insert_one(doc_dec)
            _rationales.insert_one(
                {
                    "url": url,
                    "verdict": jr.verdict,
                    "rationale": jr.rationale,
                    "judge_score": jr.judge_score,
                    "features": jr.context,
                    "created_at": datetime.utcnow(),
                }
            )
        except Exception:
            pass  # non-fatal in local dev  # nosec B110

    return JudgeOutcome(final_decision=final, policy_reason=reason, judge=jr)
