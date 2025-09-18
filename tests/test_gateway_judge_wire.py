from types import SimpleNamespace

from common.thresholds import Thresholds
from gateway.judge_wire import decide_with_judge

TH: Thresholds = {
    "t_star": 0.45,
    "low": 0.30,
    "high": 0.60,
    "gray_zone_rate": 0.10,
}


def test_policy_allows_without_judge():
    out = decide_with_judge("https://example.com", p_malicious=0.05, th=TH)
    assert out.final_decision == "ALLOW" and out.judge is None


def test_policy_blocks_without_judge():
    out = decide_with_judge("https://example.com", p_malicious=0.95, th=TH)
    assert out.final_decision == "BLOCK" and out.judge is None


def test_review_calls_judge_and_maps(monkeypatch):
    # Monkeypatch the stub to force different verdicts
    import gateway.judge_wire

    class JR(SimpleNamespace):
        def __init__(self, verdict):
            self.verdict = verdict
            self.rationale = "mock"
            self.judge_score = 0.5
            self.context = {}

        def model_dump(self):
            return {
                "verdict": self.verdict,
                "rationale": self.rationale,
                "judge_score": self.judge_score,
                "context": self.context,
            }

    monkeypatch.setattr(
        gateway.judge_wire,
        "_JUDGE_FN",
        lambda req: JR("LEAN_PHISH"),
    )
    out = decide_with_judge("http://foo/login", p_malicious=0.45, th=TH)
    assert out.final_decision == "BLOCK"

    monkeypatch.setattr(
        gateway.judge_wire,
        "_JUDGE_FN",
        lambda req: JR("LEAN_LEGIT"),
    )
    out = decide_with_judge("http://foo/login", p_malicious=0.45, th=TH)
    assert out.final_decision == "ALLOW"

    monkeypatch.setattr(
        gateway.judge_wire,
        "_JUDGE_FN",
        lambda req: JR("UNCERTAIN"),
    )
    out = decide_with_judge("http://foo/login", p_malicious=0.45, th=TH)
    assert out.final_decision == "REVIEW"
