import json
import os

from common.thresholds import load_thresholds
from gateway.judge_wire import decide_with_judge

# Set backend AFTER imports but before use
os.environ["JUDGE_BACKEND"] = (
    "llm"  # set BEFORE judge_wire usage so it binds LLM adapter
)

TH = load_thresholds(os.getenv("THRESHOLDS_JSON", "configs/dev/thresholds.json"))
out = decide_with_judge("http://ex.com/login?acct=12345", p_malicious=0.45, th=TH)

print(
    json.dumps(
        {
            "final_decision": out.final_decision,
            "reason": out.policy_reason,
            "judge_backend": (
                None if out.judge is None else out.judge.context.get("backend")
            ),
            "judge_verdict": (None if out.judge is None else out.judge.verdict),
        },
        indent=2,
    )
)
