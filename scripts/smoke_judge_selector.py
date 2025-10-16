import json
import os

from common.thresholds import load_thresholds
from gateway.judge_wire import decide_with_judge

# Set backend AFTER imports but before use
os.environ["JUDGE_BACKEND"] = (
    "llm"  # set BEFORE judge_wire usage so it binds LLM adapter
)

TH = load_thresholds(os.getenv("THRESHOLDS_JSON", "configs/dev/thresholds.json"))

# Test with a realistic gray-zone URL that would trigger judge evaluation
test_url = "https://secure-banking-update.net/login?session=abc123"
test_p_malicious = 0.45  # Gray zone score that should trigger judge

out = decide_with_judge(test_url, p_malicious=test_p_malicious, th=TH)

print("🧪 PhishGuard Judge System Smoke Test")
print(
    f"📊 Thresholds: low={TH['low']:.3f}, high={TH['high']:.3f}, "
    f"t_star={TH['t_star']:.3f}"
)
print(f"🌐 Test URL: {test_url}")
print(f"⚠️  Test p_malicious: {test_p_malicious} (gray zone)")
print()

print(
    json.dumps(
        {
            "test_input": {
                "url": test_url,
                "p_malicious": test_p_malicious,
                "thresholds": {
                    "low": TH["low"],
                    "high": TH["high"],
                    "t_star": TH["t_star"],
                },
            },
            "result": {
                "final_decision": out.final_decision,
                "reason": out.policy_reason,
                "judge_backend": (
                    None if out.judge is None else out.judge.context.get("backend")
                ),
                "judge_verdict": (None if out.judge is None else out.judge.verdict),
                "judge_score": (None if out.judge is None else out.judge.judge_score),
            },
        },
        indent=2,
    )
)
