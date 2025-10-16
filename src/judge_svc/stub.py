from .contracts import JudgeRequest, JudgeResponse, JudgeVerdict


def _risk_tokens(url: str) -> int:
    # ultra-cheap heuristic: count suspicious tokens (extensible)
    tokens = ["login", "verify", "update", "secure", "account", "paypa1", "signin"]
    url_l = url.lower()
    return sum(tok in url_l for tok in tokens)


def judge_url(req: JudgeRequest) -> JudgeResponse:
    f = req.features
    # Enhanced heuristics using 8-feature model:
    risk = 0.0
    reasons = []

    # HTTPS check (security baseline)
    if f.IsHTTPS == 0:
        risk += 0.15
        reasons.append("HTTP (not HTTPS)")

    # TLD legitimacy (Bayesian prior)
    if f.TLDLegitimateProb < 0.10:
        risk += 0.30
        reasons.append("very low TLD legitimacy")
    elif f.TLDLegitimateProb < 0.30:
        risk += 0.15
        reasons.append("low TLD legitimacy")

    # Character patterns (obfuscation indicators)
    if f.CharContinuationRate > 0.80:
        risk += 0.25
        reasons.append("high character repetition")
    elif f.CharContinuationRate > 0.60:
        risk += 0.10
        reasons.append("elevated character repetition")

    # Special character ratio (obfuscation)
    if f.SpacialCharRatioInURL > 0.25:
        risk += 0.25
        reasons.append("high special character ratio")
    elif f.SpacialCharRatioInURL > 0.15:
        risk += 0.15
        reasons.append("elevated special character ratio")

    # URL character probability (language model signal)
    if f.URLCharProb < 0.30:
        risk += 0.20
        reasons.append("low URL character probability")
    elif f.URLCharProb < 0.50:
        risk += 0.10
        reasons.append("moderate URL character probability")

    # Letter ratio (readability)
    if f.LetterRatioInURL < 0.40:
        risk += 0.15
        reasons.append("low letter ratio")

    # Special characters count (complexity)
    if f.NoOfOtherSpecialCharsInURL > 8:
        risk += 0.20
        reasons.append("many special characters")
    elif f.NoOfOtherSpecialCharsInURL > 5:
        risk += 0.10
        reasons.append("elevated special characters")

    # Domain length (suspiciously long domains)
    if f.DomainLength > 50:
        risk += 0.25
        reasons.append("very long domain")
    elif f.DomainLength > 30:
        risk += 0.10
        reasons.append("long domain")

    # Legacy features fallback (if available)
    if hasattr(f, "url_len") and f.url_len is not None:
        if f.url_len >= 120:
            risk += 0.10  # Lower weight since we have better features
            reasons.append("very long URL")

    if hasattr(f, "url_digit_ratio") and f.url_digit_ratio is not None:
        if f.url_digit_ratio >= 0.25:
            risk += 0.10  # Lower weight since we have better features
            reasons.append("high digit ratio")

    if hasattr(f, "url_subdomains") and f.url_subdomains is not None:
        if f.url_subdomains >= 4:
            risk += 0.10  # Lower weight since we have better features
            reasons.append("many subdomains")

    # suspicious tokens
    rt = _risk_tokens(req.url)
    if rt >= 2:
        risk += 0.20
        reasons.append("multiple phishing tokens in URL")
    elif rt == 1:
        risk += 0.10
        reasons.append("phishing token in URL")

    # clamp risk to [0,1]
    risk = max(0.0, min(1.0, risk))

    # map to verdict band (these are *judge* bands; independent of model thresholds)
    if risk >= 0.60:
        verdict: JudgeVerdict = "LEAN_PHISH"
    elif risk <= 0.20:
        verdict = "LEAN_LEGIT"
    else:
        verdict = "UNCERTAIN"

    rationale = (
        "; ".join(reasons) if reasons else "no obvious phishing heuristics triggered"
    )
    return JudgeResponse(
        verdict=verdict,
        rationale=rationale,
        judge_score=risk,
        context={
            # 8-feature model context
            "IsHTTPS": f.IsHTTPS,
            "TLDLegitimateProb": f.TLDLegitimateProb,
            "CharContinuationRate": f.CharContinuationRate,
            "SpacialCharRatioInURL": f.SpacialCharRatioInURL,
            "URLCharProb": f.URLCharProb,
            "LetterRatioInURL": f.LetterRatioInURL,
            "NoOfOtherSpecialCharsInURL": f.NoOfOtherSpecialCharsInURL,
            "DomainLength": f.DomainLength,
            # Legacy context (if available)
            "url_len": getattr(f, "url_len", None),
            "url_digit_ratio": getattr(f, "url_digit_ratio", None),
            "url_subdomains": getattr(f, "url_subdomains", None),
        },
    )
