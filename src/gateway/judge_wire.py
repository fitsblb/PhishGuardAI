from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional
from urllib.parse import urlparse

from common.feature_extraction import extract_features
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

# --- Enhanced routing configuration ---
SHORT_DOMAIN_LENGTH = int(os.getenv("SHORT_DOMAIN_LENGTH", "10"))
SHORT_DOMAIN_CONFIDENCE = float(os.getenv("SHORT_DOMAIN_CONFIDENCE", "0.5"))

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


# --- tiny URL feature helpers (deterministic, matches 8-feature model) ---
def _url_len(s: str) -> int:
    """Legacy helper - use extract_features() for production"""
    return len(s) if isinstance(s, str) else 0


def _digit_ratio(s: str) -> float:
    """Legacy helper - use extract_features() for production"""
    if not isinstance(s, str) or not s:
        return 0.0
    d = sum(ch.isdigit() for ch in s)
    return d / len(s)


def _subdomain_count(s: str) -> int:
    """Legacy helper - use extract_features() for production"""
    if not isinstance(s, str) or not s:
        return 0
    host = s.split("://", 1)[-1].split("/", 1)[0]
    return max(0, host.count(".") - 1)


def _extract_8features(url: str) -> Dict[str, Any]:
    """Extract 8-feature model features for judge context."""
    try:
        return extract_features(url, include_https=True)
    except Exception:
        # Fallback to legacy features if extraction fails
        return {
            "url_len": _url_len(url),
            "url_digit_ratio": _digit_ratio(url),
            "url_subdomains": _subdomain_count(url),
        }


def _extract_domain(url: str) -> str:
    """Extract domain from URL, handling errors gracefully."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


@dataclass
class JudgeOutcome:
    final_decision: Decision
    policy_reason: str  # why ALLOW/BLOCK/REVIEW from policy/judge
    judge: Optional[JudgeResponse]  # None if not invoked


def _should_route_to_judge_for_short_domain(url: str, p_malicious: float) -> bool:
    """
    Check if URL should be routed to judge due to short domain edge case.

    Rationale: Short legitimate domains (npm.org, bit.ly, etc.) may appear
    suspicious to the model due to distribution shift. Route to judge for
    human-readable explanation when:
    - Domain length ≤ threshold (default 10 chars)
    - Confidence is moderate (p < 0.5) - not highly suspicious

    This catches edge cases not covered by the whitelist.
    """
    domain = _extract_domain(url)
    if not domain:
        return False

    is_short = len(domain) <= SHORT_DOMAIN_LENGTH
    is_moderate_confidence = p_malicious < SHORT_DOMAIN_CONFIDENCE

    return is_short and is_moderate_confidence


def decide_with_judge(
    url: str,
    p_malicious: float,
    th: Thresholds,
    extras: Optional[Dict[str, Any]] = None,
) -> JudgeOutcome:
    """
    Enhanced decision logic with short domain routing.

    Decision Flow:
    1. Apply policy bands (low/high thresholds)
    2. If base decision is REVIEW, check for short domain edge case
    3. Invoke judge and map verdict to final decision

    Enhanced Logic:
    - Short domains with moderate confidence routed to judge
    - Judge provides human-readable rationale for edge cases
    """
    base_decision: Decision = decide(p_malicious, th)  # uses low/high
    inc_policy(base_decision)

    # Fast path: High confidence ALLOW/BLOCK
    if base_decision != "REVIEW":
        inc_final(base_decision)  # final == policy when not REVIEW
        return JudgeOutcome(
            final_decision=base_decision, policy_reason="policy-band", judge=None
        )

    # === GRAY ZONE ROUTING LOGIC ===
    # Check if this is a short domain edge case that needs judge review
    is_short_domain_case = _should_route_to_judge_for_short_domain(url, p_malicious)

    # Build the feature digest using 8-feature model
    features_8 = _extract_8features(url)

    digest = FeatureDigest(
        # 8-feature model (required fields)
        IsHTTPS=features_8.get("IsHTTPS", 0),
        TLDLegitimateProb=features_8.get("TLDLegitimateProb", 0.5),  # neutral default
        CharContinuationRate=features_8.get("CharContinuationRate", 0.0),
        SpacialCharRatioInURL=features_8.get("SpacialCharRatioInURL", 0.0),
        URLCharProb=features_8.get("URLCharProb", 0.5),  # neutral default
        LetterRatioInURL=features_8.get("LetterRatioInURL", 0.5),  # neutral default
        NoOfOtherSpecialCharsInURL=features_8.get("NoOfOtherSpecialCharsInURL", 0),
        DomainLength=features_8.get("DomainLength", len(_extract_domain(url))),
        # Legacy features (optional for backward compatibility)
        url_len=features_8.get("url_len", _url_len(url)),
        url_digit_ratio=features_8.get("url_digit_ratio", _digit_ratio(url)),
        url_subdomains=features_8.get("url_subdomains", _subdomain_count(url)),
    )

    # Add routing context to judge request
    req = JudgeRequest(url=url, features=digest)
    jr = _JUDGE_FN(req)  # uses selected judge backend (stub or llm)

    # === VERDICT MAPPING WITH SHORT DOMAIN CONTEXT ===
    # Map judge verdict to final decision
    if jr.verdict == "LEAN_PHISH":
        final: Decision = "BLOCK"
        reason = "judge-lean-phish"
        if is_short_domain_case:
            reason = "judge-short-domain-lean-phish"
    elif jr.verdict == "LEAN_LEGIT":
        final = "ALLOW"
        reason = "judge-lean-legit"
        if is_short_domain_case:
            reason = "judge-short-domain-lean-legit"
    else:
        final = "REVIEW"
        reason = "judge-uncertain"
        if is_short_domain_case:
            reason = "judge-short-domain-uncertain"

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
                "is_short_domain_case": is_short_domain_case,
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
                    "is_short_domain_case": is_short_domain_case,
                    "created_at": datetime.utcnow(),
                }
            )
        except Exception:
            pass  # non-fatal in local dev  # nosec B110

    return JudgeOutcome(final_decision=final, policy_reason=reason, judge=jr)
