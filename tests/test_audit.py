from datetime import datetime

from common.audit import AuditWriter, DecisionRecord, JudgeRecord


class ListCollection:
    """Minimal insert-only stub mimicking a Mongo collection."""

    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)


def test_audit_writer_inserts_decision_and_judge():
    dec_col, rat_col = ListCollection(), ListCollection()
    aw = AuditWriter(decisions=dec_col, rationales=rat_col)

    dec = DecisionRecord(
        url="https://e.x",
        p_malicious=0.42,
        policy_thresholds={
            "low": 0.3,
            "high": 0.6,
            "t_star": 0.45,
            "gray_zone_rate": 0.10,
        },
        policy_decision="REVIEW",
        final_decision="BLOCK",
        created_at=datetime.utcnow(),
    )
    aw.log_decision(dec)
    assert len(dec_col.docs) == 1
    assert dec_col.docs[0]["final_decision"] == "BLOCK"

    jr = JudgeRecord(
        url="https://e.x",
        verdict="LEAN_PHISH",
        rationale="mock",
        judge_score=0.7,
        features={"url_len": 120},
        created_at=datetime.utcnow(),
    )
    aw.log_judge(jr)
    assert len(rat_col.docs) == 1
    assert rat_col.docs[0]["verdict"] == "LEAN_PHISH"
