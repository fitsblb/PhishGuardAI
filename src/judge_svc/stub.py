from .contracts import JudgeRequest, JudgeResponse, JudgeVerdict


def _risk_tokens(url: str) -> int:
    # ultra-cheap heuristic: count suspicious tokens (extensible)
    tokens = ["login", "verify", "update", "secure", "account", "paypa1", "signin"]
    url_l = url.lower()
    return sum(tok in url_l for tok in tokens)


def judge_url(req: JudgeRequest) -> JudgeResponse:
    f = req.features
    # Simple, explainable rules:
    risk = 0.0
    reasons = []

    # long URL
    if f.url_len >= 120:
        risk += 0.35
        reasons.append("very long URL")
    elif f.url_len >= 80:
        risk += 0.20
        reasons.append("long URL")

    # many digits
    if f.url_digit_ratio >= 0.25:
        risk += 0.35
        reasons.append("high digit ratio")
    elif f.url_digit_ratio >= 0.15:
        risk += 0.20
        reasons.append("elevated digit ratio")

    # many subdomains
    if f.url_subdomains >= 4:
        risk += 0.20
        reasons.append("many subdomains")
    elif f.url_subdomains >= 3:
        risk += 0.10
        reasons.append("multiple subdomains")

    # low TLD legitimacy prior (if provided)
    if f.TLDLegitimateProb is not None:
        if f.TLDLegitimateProb < 0.10:
            risk += 0.25
            reasons.append("low TLD legitimacy")
        elif f.TLDLegitimateProb < 0.25:
            risk += 0.10
            reasons.append("moderate TLD legitimacy")

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
            "url_len": f.url_len,
            "url_digit_ratio": f.url_digit_ratio,
            "url_subdomains": f.url_subdomains,
            "TLDLegitimateProb": f.TLDLegitimateProb,
        },
    )
