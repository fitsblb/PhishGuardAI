"""
Tests for enhanced short domain routing logic in judge_wire.py

Test Scenarios:
1. High confidence cases (no judge)
2. Gray zone cases (standard judge routing)
3. Short domain edge cases (enhanced judge routing)
4. Whitelist fast path (handled in main.py)
"""

from common.thresholds import Thresholds
from gateway.judge_wire import (
    _extract_domain,
    _should_route_to_judge_for_short_domain,
    decide_with_judge,
)

# Constants for short domain routing (matching judge_wire.py)
SHORT_DOMAIN_LENGTH = 10
SHORT_DOMAIN_CONFIDENCE = 0.5


# Mock thresholds for testing
MOCK_THRESHOLDS = Thresholds(
    low=0.004,
    high=0.999,
    t_star=0.35,
    gray_zone_rate=0.109,
)


class TestDomainExtraction:
    """Test domain extraction helper."""

    def test_extract_valid_domain(self):
        assert _extract_domain("https://example.com/path") == "example.com"
        assert _extract_domain("http://sub.example.com") == "sub.example.com"

    def test_extract_short_domain(self):
        assert _extract_domain("https://npm.org") == "npm.org"
        assert _extract_domain("https://bit.ly/abc") == "bit.ly"

    def test_extract_malformed_url(self):
        assert _extract_domain("not-a-url") == ""
        assert _extract_domain("") == ""


class TestShortDomainRouting:
    """Test short domain routing logic."""

    def test_short_legitimate_domain_moderate_confidence(self):
        """Short domain with p < 0.5 should route to judge."""
        url = "https://npm.org/package"
        p_malicious = 0.35
        assert _should_route_to_judge_for_short_domain(url, p_malicious) is True

    def test_short_domain_high_confidence(self):
        """Short domain with p >= 0.5 should NOT route (high suspicion)."""
        url = "https://evil.io/phish"
        p_malicious = 0.75
        assert _should_route_to_judge_for_short_domain(url, p_malicious) is False

    def test_long_domain_moderate_confidence(self):
        """Long domain should NOT route via short domain path."""
        url = "https://verylongdomainname.com/path"
        p_malicious = 0.35
        assert _should_route_to_judge_for_short_domain(url, p_malicious) is False

    def test_boundary_cases(self):
        """Test boundary conditions."""
        # Exactly 10 chars (should trigger)
        url_10 = "https://tenchar.co"
        assert len("tenchar.co") == 10
        assert _should_route_to_judge_for_short_domain(url_10, 0.4) is True

        # 11 chars (should NOT trigger)
        url_11 = "https://elevenchar.co"
        assert len("elevenchar.co") == 13  # Actually longer
        assert _should_route_to_judge_for_short_domain(url_11, 0.4) is False

        # Exactly p = 0.5 (boundary)
        url_short = "https://bit.ly"
        assert _should_route_to_judge_for_short_domain(url_short, 0.5) is False
        assert _should_route_to_judge_for_short_domain(url_short, 0.499) is True


class TestEnhancedDecisionLogic:
    """Integration tests for enhanced decision logic."""

    def test_high_confidence_allow(self):
        """p < low threshold should ALLOW without judge."""
        url = "https://example.com"
        p_malicious = 0.001
        outcome = decide_with_judge(url, p_malicious, MOCK_THRESHOLDS)

        assert outcome.final_decision == "ALLOW"
        assert outcome.policy_reason == "policy-band"
        assert outcome.judge is None

    def test_high_confidence_block(self):
        """p > high threshold should BLOCK without judge."""
        url = "https://phishing-site.evil"
        p_malicious = 0.999
        outcome = decide_with_judge(url, p_malicious, MOCK_THRESHOLDS)

        assert outcome.final_decision == "BLOCK"
        assert outcome.policy_reason == "policy-band"
        assert outcome.judge is None

    def test_gray_zone_standard(self):
        """Normal domain in gray zone should invoke judge."""
        url = "https://suspicious-but-long-domain.com"
        p_malicious = 0.35
        outcome = decide_with_judge(url, p_malicious, MOCK_THRESHOLDS)

        # Judge should be invoked
        assert outcome.judge is not None
        # Decision depends on judge verdict
        assert outcome.final_decision in ["ALLOW", "REVIEW", "BLOCK"]
        # Reason should indicate judge was used
        assert "judge" in outcome.policy_reason

    def test_short_domain_gray_zone(self):
        """Short domain in gray zone should have enhanced routing."""
        url = "https://npm.org"
        p_malicious = 0.35
        outcome = decide_with_judge(url, p_malicious, MOCK_THRESHOLDS)

        # Judge should be invoked
        assert outcome.judge is not None
        # Reason should indicate short domain handling
        assert "short-domain" in outcome.policy_reason


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_malformed_url(self):
        """Malformed URL should still process."""
        url = "not-a-valid-url"
        p_malicious = 0.35
        # Should not crash
        outcome = decide_with_judge(url, p_malicious, MOCK_THRESHOLDS)
        assert outcome.final_decision in ["ALLOW", "REVIEW", "BLOCK"]

    def test_empty_extras(self):
        """Empty extras should not crash."""
        url = "https://example.com"
        p_malicious = 0.35
        outcome = decide_with_judge(url, p_malicious, MOCK_THRESHOLDS, extras={})
        assert outcome is not None

    def test_none_extras(self):
        """None extras should not crash."""
        url = "https://example.com"
        p_malicious = 0.35
        outcome = decide_with_judge(url, p_malicious, MOCK_THRESHOLDS, extras=None)
        assert outcome is not None


# Example test cases for manual validation
MANUAL_TEST_CASES = [
    # (url, p_malicious, expected_behavior)
    ("https://github.com", 0.001, "Whitelist fast path (main.py)"),
    ("https://npm.org", 0.35, "Short domain → judge"),
    ("https://bit.ly/abc", 0.45, "Short domain → judge"),
    ("https://t.co/xyz", 0.40, "Short domain → judge"),
    (
        "https://evil.io/phish",
        0.75,
        "Short domain but high confidence → standard gray zone",
    ),
    ("https://legitimate-company.com", 0.35, "Normal domain → standard gray zone"),
    ("https://phishing-site.evil", 0.999, "High confidence → BLOCK (no judge)"),
    ("https://safe-site.com", 0.001, "High confidence → ALLOW (no judge)"),
]

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MANUAL TEST CASES - Expected Behavior")
    print("=" * 60)

    for url, p_mal, expected in MANUAL_TEST_CASES:
        print("\nURL: {url}")
        print(f"  p_malicious: {p_mal:.3f}")
        print(f"  Expected: {expected}")

        # Check if short domain routing applies
        is_short = _should_route_to_judge_for_short_domain(url, p_mal)
        if is_short:
            print("✓ Short domain routing triggered")

        # Show threshold classification
        if p_mal < MOCK_THRESHOLDS["low"]:
            print(f"  → Policy: ALLOW (p < {MOCK_THRESHOLDS['low']})")
        elif p_mal > MOCK_THRESHOLDS["high"]:
            print(f"  → Policy: BLOCK (p > {MOCK_THRESHOLDS['high']})")
        else:
            print("→ Policy: REVIEW (gray zone)")
