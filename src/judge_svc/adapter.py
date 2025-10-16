from __future__ import annotations

import json
import os
import re
from typing import Tuple

import requests

from judge_svc.contracts import JudgeRequest, JudgeResponse, JudgeVerdict
from judge_svc.stub import judge_url as fallback_stub  # fail-open if LLM not available

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "llama3.2:1b")
JUDGE_TIMEOUT = float(os.getenv("JUDGE_TIMEOUT_SECS", "12"))

_VERDICT_RE = re.compile(r"\bVERDICT\s*:\s*(LEAN_PHISH|LEAN_LEGIT|UNCERTAIN)\b", re.I)
_SCORE_RE = re.compile(r"\bSCORE\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)\b", re.I)
_RAT_RE = re.compile(r"\bRATIONALE\s*:\s*(.+)", re.I | re.S)


def _prompt(req: JudgeRequest) -> str:
    # Enhanced prompt for 8-feature model with detailed feature descriptions
    feat = req.features.model_dump()
    return (
        "You are a cybersecurity analyst specializing in phishing detection. "
        "Assess phishing risk using the URL and 8 sophisticated features:\n\n"
        "KEY FEATURES TO ANALYZE:\n"
        "- IsHTTPS: HTTPS usage (0=HTTP, 1=HTTPS)\n"
        "- TLDLegitimateProb: Bayesian TLD legitimacy probability [0,1]\n"
        "- CharContinuationRate: Character repetition patterns [0,1]\n"
        "- SpacialCharRatioInURL: Special character density [0,1]\n"
        "- URLCharProb: URL character sequence probability [0,1]\n"
        "- LetterRatioInURL: Alphabetic character ratio [0,1]\n"
        "- NoOfOtherSpecialCharsInURL: Count of special characters\n"
        "- DomainLength: RFC-compliant domain length\n\n"
        "RESPOND WITH EXACTLY THREE FIELDS:\n"
        "VERDICT: LEAN_PHISH | LEAN_LEGIT | UNCERTAIN\n"
        "SCORE: risk score in [0,1] where 0=safe, 1=malicious\n"
        "RATIONALE: brief explanation focusing on key risk indicators\n\n"
        f"URL: {req.url}\n"
        f"FEATURES: {json.dumps(feat, separators=(',', ':'))}\n\n"
        "Focus on: HTTPS usage, TLD legitimacy, character patterns, "
        "and any URL obfuscation techniques."
    )


def _parse(text: str) -> Tuple[JudgeVerdict, float | None, str]:
    verdict: JudgeVerdict = "UNCERTAIN"
    score = None
    rationale = "no rationale"
    m = _VERDICT_RE.search(text)
    if m:
        v = m.group(1).upper()
        verdict = (
            "LEAN_PHISH"
            if v == "LEAN_PHISH"
            else ("LEAN_LEGIT" if v == "LEAN_LEGIT" else "UNCERTAIN")
        )
    m = _SCORE_RE.search(text)
    if m:
        try:
            score = float(m.group(1))
            score = max(0.0, min(1.0, score))
        except Exception:
            score = None
    m = _RAT_RE.search(text)
    if m:
        rationale = m.group(1).strip().splitlines()[0][:500]
    return verdict, score, rationale


def judge_url_llm(req: JudgeRequest) -> JudgeResponse:
    """
    LLM-backed judge using Ollama /api/generate.
    Fails open to deterministic stub if any network/model error occurs.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": JUDGE_MODEL, "prompt": _prompt(req), "stream": False},
            timeout=JUDGE_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response", "")
        verdict, score, rationale = _parse(text)
        return JudgeResponse(
            verdict=verdict,
            judge_score=score,
            rationale=rationale,
            context={
                "backend": "llm",
                "model": JUDGE_MODEL,
                **req.features.model_dump(),
            },
        )
    except Exception:
        # Fail-open: never block the request path just because LLM isn't available
        fb = fallback_stub(req)
        fb.context.update({"backend": "stub_fallback", "model": JUDGE_MODEL})
        return fb
