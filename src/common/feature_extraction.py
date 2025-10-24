"""
Shared feature extraction for training and inference.
Ensures consistency between notebooks and production services.

This module extracts URL-only features for phishing detection.
Production model uses 7 features (IsHTTPS removed due to distribution shift).

DISTRIBUTION SHIFT DISCOVERY:
- Initial 8-feature model achieved 99.92% PR-AUC with IsHTTPS as strongest feature
- Production FN audit revealed 100% of FNs were HTTPS phishing (115/115)
- Training data (2019-2020) only 48.9% of phishing was HTTPS
- Modern phishing (2024+) adopted HTTPS universally (Let's Encrypt free certs)
- Model learned "HTTPS = Legitimate" from outdated data
- Removed IsHTTPS: PR-AUC 99.88% (-0.04%), but massive FN reduction
- Decision: Security > marginal AUC gain

PRODUCTION MODEL (7 features):
1. TLDLegitimateProb - TLD reputation score from historical data
2. CharContinuationRate - Character repetition rate in URL
3. SpacialCharRatioInURL - Special character density
4. URLCharProb - Character frequency probability score
5. LetterRatioInURL - Letter character density
6. NoOfOtherSpecialCharsInURL - Count of special characters
7. DomainLength - Domain string length

SHADOW MODEL (8 features - for research/comparison):
- Includes IsHTTPS for temporal drift monitoring

Usage:
    # Extract 7 features (PRODUCTION - default)
    features = extract_features("https://example.com/login")

    # Extract 8 features (RESEARCH/SHADOW - explicit opt-in)
    features = extract_features("https://example.com/login", include_https=True)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Union
from urllib.parse import urlparse

import tldextract

# ============================================================
# CONFIGURATION
# ============================================================

# Path to TLD probability lookup table
TLD_PROBS_PATH = Path(__file__).parent.parent.parent / "data" / "tld_probs.json"

# Feature names in canonical order (matches training data)
FEATURE_NAMES_7 = [
    "TLDLegitimateProb",
    "CharContinuationRate",
    "SpacialCharRatioInURL",
    "URLCharProb",
    "LetterRatioInURL",
    "NoOfOtherSpecialCharsInURL",
    "DomainLength",
]

FEATURE_NAMES_8 = [
    "IsHTTPS",  # REMOVED from production due to distribution shift
    "TLDLegitimateProb",
    "CharContinuationRate",
    "SpacialCharRatioInURL",
    "URLCharProb",
    "LetterRatioInURL",
    "NoOfOtherSpecialCharsInURL",
    "DomainLength",
]

# ============================================================
# TLD PROBABILITY LOOKUP
# ============================================================

# Load TLD probabilities at module initialization
_TLD_PROBS: Dict[str, float] = {}

try:
    if TLD_PROBS_PATH.exists():
        with open(TLD_PROBS_PATH, "r", encoding="utf-8") as f:
            _TLD_PROBS = json.load(f)
        print(f"[feature_extraction] Loaded {len(_TLD_PROBS)} TLD probabilities")
    else:
        print(f"[feature_extraction] WARNING: TLD probs not found at {TLD_PROBS_PATH}")
        print("[feature_extraction] Will use default 0.5 for all TLDs")
except Exception as e:
    print(f"[feature_extraction] ERROR loading TLD probs: {e}")
    _TLD_PROBS = {}


# ============================================================
# FEATURE EXTRACTION
# ============================================================


def extract_features(
    url: str, include_https: bool = False
) -> Dict[str, Union[int, float]]:
    """
    Extract URL-only features for phishing detection.

    IMPORTANT: Default behavior changed to exclude IsHTTPS (7-feature production model).

    Args:
        url: URL to extract features from (e.g., "https://example.com/login")
        include_https: If True, include IsHTTPS feature (8-feature shadow model)
                      If False (DEFAULT), exclude IsHTTPS (7-feature production model)

    Returns:
        Dictionary mapping feature names to values.
        Keys are in consistent order matching training data.

    Why IsHTTPS Removed by Default:
        - 100% of production FNs were HTTPS phishing (vs 48.9% in 2019-2020 training)
        - Modern phishing adopted HTTPS universally (Let's Encrypt free certs)
        - IsHTTPS gave false legitimacy signal to HTTPS phishing
        - Removing it reduced FN rate while only losing 0.04% PR-AUC
        - Future-proof: won't degrade as HTTPS adoption increases

    Example:
        >>> # Production (7 features, no IsHTTPS)
        >>> features = extract_features("https://example.com/login?id=123")
        >>> features['TLDLegitimateProb']
        0.877
        >>> 'IsHTTPS' in features
        False

        >>> # Shadow model (8 features, with IsHTTPS)
        >>> features = extract_features("https://example.com/login", include_https=True)
        >>> features['IsHTTPS']
        1.0
    """
    if not url or not isinstance(url, str):
        # Return suspicious features for invalid input (fail-secure)
        return _zero_features(include_https)

    try:
        # Parse URL components
        parsed = urlparse(url)
        extracted = tldextract.extract(url)

        features = {}

        # Feature 1: IsHTTPS (OPTIONAL - only for shadow model)
        # REMOVED from production due to distribution shift
        # Kept as optional parameter for monitoring temporal drift
        if include_https:
            features["IsHTTPS"] = 1.0 if parsed.scheme == "https" else 0.0

        # Feature 2: TLDLegitimateProb
        tld = extracted.suffix.lower() if extracted.suffix else ""
        features["TLDLegitimateProb"] = _TLD_PROBS.get(
            tld, 0.5
        )  # Default 0.5 for unknown

        # Feature 3: CharContinuationRate
        features["CharContinuationRate"] = _calc_char_continuation(url)

        # Feature 4: SpacialCharRatioInURL
        features["SpacialCharRatioInURL"] = _calc_special_char_ratio(url)

        # Feature 5: URLCharProb
        features["URLCharProb"] = _calc_url_char_prob(url)

        # Feature 6: LetterRatioInURL
        features["LetterRatioInURL"] = _calc_letter_ratio(url)

        # Feature 7: NoOfOtherSpecialCharsInURL
        features["NoOfOtherSpecialCharsInURL"] = _count_special_chars(url)

        # Feature 8: DomainLength
        domain = parsed.netloc if parsed.netloc else ""
        features["DomainLength"] = len(domain)

        return features

    except Exception as e:
        print(f"[feature_extraction] ERROR extracting features from {url}: {e}")
        return _zero_features(include_https)


# ============================================================
# HELPER FUNCTIONS (Feature Calculations)
# ============================================================


def _calc_char_continuation(url: str) -> float:
    """
    Calculate character repetition rate.

    Measures how often consecutive characters are the same.
    Higher values indicate more repetition (e.g., "aaa", "---").

    Formula: (count of repeated chars) / (total chars - 1)

    Examples:
        "abc" → 0.0 (no repetition)
        "aaa" → 1.0 (all repeated)
        "abbc" → 0.33 (one pair repeated)
    """
    if len(url) < 2:
        return 0.0

    continuations = sum(1 for i in range(len(url) - 1) if url[i] == url[i + 1])
    return continuations / (len(url) - 1)


def _calc_special_char_ratio(url: str) -> float:
    """
    Calculate density of special characters in URL.

    Special characters: ! @ # $ % ^ & * ( ) _ + - = [ ] { } | ; : , . < > ? /

    Formula: (count of special chars) / (total chars)

    Examples:
        "http://example.com" → 0.16 (3 special: :, /, /)
        "http://ex.com/login?id=123&token=abc" → 0.23 (8 special)
    """
    if not url:
        return 0.0

    special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?/")
    special_count = sum(1 for c in url if c in special_chars)

    return special_count / len(url)


def _count_special_chars(url: str) -> int:
    """
    Count total number of special characters.

    Same character set as _calc_special_char_ratio but returns count.

    Examples:
        "http://example.com" → 3
        "http://ex.com/login?id=123&token=abc" → 8
    """
    if not url:
        return 0

    special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?/")
    return sum(1 for c in url if c in special_chars)


def _calc_letter_ratio(url: str) -> float:
    """
    Calculate density of letter characters in URL.

    Formula: (count of letters A-Za-z) / (total chars)

    Examples:
        "http://example.com" → 0.63 (12 letters / 19 total)
        "http://ex.com/123" → 0.47 (8 letters / 17 total)
    """
    if not url:
        return 0.0

    letter_count = sum(1 for c in url if c.isalpha())
    return letter_count / len(url)


def _calc_url_char_prob(url: str) -> float:
    """
    Calculate URL character probability score.

    This is a simplified heuristic measuring how "URL-like" the
    character distribution is. Lower scores indicate unusual characters.

    Implementation: Measures proportion of common URL characters
    (alphanumeric + :/.?=&-_)

    Formula: (count of common chars) / (total chars)

    Examples:
        "http://example.com" → 0.95 (all common chars)
        "http://ex.com/login" → 0.94
        "http://ex.com/@@##$$" → 0.70 (unusual chars)
    """
    if not url:
        return 0.0

    # Common URL characters (alphanumeric + standard URL syntax)
    common_chars = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:/.?=&-_"
    )

    common_count = sum(1 for c in url if c in common_chars)
    score = common_count / len(url)

    return score


def _zero_features(include_https: bool) -> Dict[str, Union[int, float]]:
    """
    Return dictionary of suspicious features for error cases (fail-secure).

    SECURITY DESIGN: If we can't parse a URL, treat it as suspicious.
    Better to block a broken URL than allow a potentially malicious one.

    Args:
        include_https: If True, include IsHTTPS=0 in output (shadow model)
                      If False, omit IsHTTPS (production model)

    Returns:
        Dict with all features set to suspicious values (high phishing likelihood)
    """
    features = {
        "TLDLegitimateProb": 0.05,  # Very suspicious TLD (low legitimacy)
        "CharContinuationRate": 0.6,  # High repetition (suspicious pattern)
        "SpacialCharRatioInURL": 0.25,  # Many special chars (obfuscation)
        "URLCharProb": 0.02,  # Very unusual characters (vs normal ~1.0)
        "LetterRatioInURL": 0.3,  # Low letter ratio (suspicious)
        "NoOfOtherSpecialCharsInURL": 15,  # Many special chars (obfuscation)
        "DomainLength": 60,  # Very long domain (typosquatting)
    }

    if include_https:
        features["IsHTTPS"] = 0.0  # No HTTPS (suspicious in error case)

    return features


# ============================================================
# UTILITY FUNCTIONS
# ============================================================


def get_feature_names(include_https: bool = False) -> list[str]:
    """
    Get feature names in consistent order.

    IMPORTANT: Default changed to 7-feature production model (no IsHTTPS).

    Args:
        include_https: If True, return 8-feature names (with IsHTTPS - shadow model)
                      If False (DEFAULT), return 7-feature names (production model)

    Returns:
        List of feature names in order matching training data

    Example:
        >>> # Production model (7 features)
        >>> get_feature_names()
        ['TLDLegitimateProb', 'CharContinuationRate', ...]

        >>> # Shadow model (8 features)
        >>> get_feature_names(include_https=True)
        ['IsHTTPS', 'TLDLegitimateProb', ...]
    """
    return FEATURE_NAMES_8 if include_https else FEATURE_NAMES_7


def validate_features(features: Dict[str, float], include_https: bool = False) -> bool:
    """
    Validate that extracted features are correct.

    Checks:
    1. All expected feature names present
    2. All values are numeric
    3. Probability features in [0, 1]
    4. Count features >= 0

    Args:
        features: Dict returned by extract_features()
        include_https: Expected feature set (7-feature production or 8-feature shadow)

    Returns:
        True if valid, False otherwise
    """
    expected_names = get_feature_names(include_https)

    # Check 1: All features present
    if set(features.keys()) != set(expected_names):
        missing = set(expected_names) - set(features.keys())
        extra = set(features.keys()) - set(expected_names)
        if missing:
            print(f"[validate] Missing features: {missing}")
        if extra:
            print(f"[validate] Extra features: {extra}")
        return False

    # Check 2: All numeric
    if not all(isinstance(v, (int, float)) for v in features.values()):
        print("[validate] Non-numeric feature values found")
        return False

    # Check 3: Probability features in [0, 1]
    prob_features = [
        "TLDLegitimateProb",
        "CharContinuationRate",
        "SpacialCharRatioInURL",
        "URLCharProb",
        "LetterRatioInURL",
    ]
    for feat in prob_features:
        if feat in features:
            val = features[feat]
            if not (0.0 <= val <= 1.0):
                print(f"[validate] {feat}={val} not in [0, 1]")
                return False

    # Check 4: Count/length features >= 0
    count_features = ["NoOfOtherSpecialCharsInURL", "DomainLength"]
    for feat in count_features:
        if feat in features:
            val = features[feat]
            if val < 0:
                print(f"[validate] {feat}={val} is negative")
                return False

    # Check 5: IsHTTPS (if present) is binary
    if "IsHTTPS" in features:
        val = features["IsHTTPS"]
        if val not in [0.0, 1.0]:
            print(f"[validate] IsHTTPS={val} not binary (0.0 or 1.0)")
            return False

    return True


# ============================================================
# MODULE TEST (runs when imported or executed directly)
# ============================================================

if __name__ == "__main__":
    # Smoke test
    print("\n" + "=" * 80)
    print("FEATURE EXTRACTION - SMOKE TEST")
    print("=" * 80)
    print("\nPRODUCTION MODEL: 7 features (IsHTTPS removed due to distribution shift)")
    print("SHADOW MODEL: 8 features (IsHTTPS for temporal drift monitoring)")
    print("=" * 80)

    test_urls = [
        "https://example.com",
        "http://example.com/login",
        "https://example.com/login?id=123&token=abc&redirect=https://evil.com",
        "http://suspicious-phishing-site.top/verify-account",
        "https://google.com",  # Known FN case (would be 100% phishing with IsHTTPS)
    ]

    for url in test_urls:
        print(f"\n{'=' * 80}")
        print(f"URL: {url}")
        print(f"{'=' * 80}")

        # Extract 7 features (PRODUCTION)
        print("\n🟢 PRODUCTION MODEL (7 features, no IsHTTPS):")
        print("-" * 80)
        features_7 = extract_features(url, include_https=False)
        for name, value in features_7.items():
            if isinstance(value, float):
                print(f"  {name:35s} = {value:.4f}")
            else:
                print(f"  {name:35s} = {value}")

        is_valid_7 = validate_features(features_7, include_https=False)
        print(f"\n  ✓ Valid: {is_valid_7}")

        # Extract 8 features (SHADOW - for comparison)
        print("\n🔵 SHADOW MODEL (8 features, with IsHTTPS):")
        print("-" * 80)
        features_8 = extract_features(url, include_https=True)
        for name, value in features_8.items():
            if isinstance(value, float):
                print(f"  {name:35s} = {value:.4f}")
            else:
                print(f"  {name:35s} = {value}")

        is_valid_8 = validate_features(features_8, include_https=True)
        print(f"\n  ✓ Valid: {is_valid_8}")

        # Highlight IsHTTPS difference
        if "IsHTTPS" in features_8:
            https_value = features_8["IsHTTPS"]
            if https_value == 1.0:
                print(
                    "\n  💡 Note: IsHTTPS=1.0 (HTTPS) - Would give legitimacy boost in 8-feat model"
                )
            else:
                print(
                    "\n  💡 Note: IsHTTPS=0.0 (HTTP) - Would give phishing signal in 8-feat model"
                )

    print("\n" + "=" * 80)
    print("SMOKE TEST COMPLETE")
    print("=" * 80)
    print("\n📊 SUMMARY:")
    print("  - Production model: 7 features (default)")
    print("  - Shadow model: 8 features (opt-in with include_https=True)")
    print("  - IsHTTPS removed from production due to 100% FN rate on HTTPS phishing")
    print(
        "  - PR-AUC: 99.88% (7-feat) vs 99.92% (8-feat) = -0.04% acceptable trade-off"
    )
    print("=" * 80 + "\n")
