"""
Shared feature extraction for training and inference.
Ensures consistency between notebooks and production services.

This module extracts the optimal 8 URL-only features used by our
phishing detection models. It supports both 7-feature (production)
and 8-feature (shadow/research) models.

Features:
1. IsHTTPS - Protocol indicator (HTTPS=1, HTTP=0)
2. TLDLegitimateProb - TLD reputation score from historical data
3. CharContinuationRate - Character repetition rate in URL
4. SpacialCharRatioInURL - Special character density
5. URLCharProb - Character frequency probability score
6. LetterRatioInURL - Letter character density
7. NoOfOtherSpecialCharsInURL - Count of special characters
8. DomainLength - Domain string length

Usage:
    # Extract all 8 features (for 8-feature model)
    features = extract_features("https://example.com/login")

    # Extract only 7 features (for 7-feature model)
    features = extract_features("https://example.com/login", include_https=False)
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
FEATURE_NAMES_8 = [
    "IsHTTPS",
    "TLDLegitimateProb",
    "CharContinuationRate",
    "SpacialCharRatioInURL",
    "URLCharProb",
    "LetterRatioInURL",
    "NoOfOtherSpecialCharsInURL",
    "DomainLength",
]

FEATURE_NAMES_7 = [
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
    url: str, include_https: bool = True
) -> Dict[str, Union[int, float]]:
    """
    Extract URL-only features for phishing detection.

    Args:
        url: URL to extract features from (e.g., "https://example.com/login")
        include_https: If True, include IsHTTPS feature (8-feature model)
                      If False, exclude IsHTTPS (7-feature model)

    Returns:
        Dictionary mapping feature names to values.
        Keys are in consistent order matching training data.

    Example:
        >>> features = extract_features("https://example.com/login?id=123")
        >>> features['IsHTTPS']
        1
        >>> features['TLDLegitimateProb']
        0.877
    """
    if not url or not isinstance(url, str):
        # Return zero features for invalid input
        return _zero_features(include_https)

    try:
        # Parse URL components
        parsed = urlparse(url)
        extracted = tldextract.extract(url)

        features = {}

        # Feature 1: IsHTTPS (optional)
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

    # Normalize to roughly match training distribution (mean ~0.055)
    # Training data showed URLCharProb has mean 0.055, std 0.010
    # Our score is in [0,1], so scale down
    normalized = score * 0.06  # Scale to [0, 0.06] range

    return normalized


def _zero_features(include_https: bool) -> Dict[str, Union[int, float]]:
    """
    Return dictionary of zero-valued features (for error cases).

    Args:
        include_https: If True, include IsHTTPS=0 in output

    Returns:
        Dict with all features set to 0 or safe defaults
    """
    features = {
        "TLDLegitimateProb": 0.5,  # Neutral default
        "CharContinuationRate": 0.0,
        "SpacialCharRatioInURL": 0.0,
        "URLCharProb": 0.05,  # Safe default
        "LetterRatioInURL": 0.0,
        "NoOfOtherSpecialCharsInURL": 0,
        "DomainLength": 0,
    }

    if include_https:
        features["IsHTTPS"] = 0.0

    return features


# ============================================================
# UTILITY FUNCTIONS
# ============================================================


def get_feature_names(include_https: bool = True) -> list[str]:
    """
    Get feature names in consistent order.

    Args:
        include_https: If True, return 8-feature names (with IsHTTPS)
                      If False, return 7-feature names (without IsHTTPS)

    Returns:
        List of feature names in order matching training data

    Example:
        >>> get_feature_names(include_https=True)
        ['IsHTTPS', 'TLDLegitimateProb', ...]
        >>> get_feature_names(include_https=False)
        ['TLDLegitimateProb', 'CharContinuationRate', ...]
    """
    return FEATURE_NAMES_8 if include_https else FEATURE_NAMES_7


def validate_features(features: Dict[str, float], include_https: bool = True) -> bool:
    """
    Validate that extracted features are correct.

    Checks:
    1. All expected feature names present
    2. All values are numeric
    3. Probability features in [0, 1]
    4. Count features >= 0

    Args:
        features: Dict returned by extract_features()
        include_https: Expected feature set (8 or 7 features)

    Returns:
        True if valid, False otherwise
    """
    expected_names = get_feature_names(include_https)

    # Check 1: All features present
    if set(features.keys()) != set(expected_names):
        print(
            f"[validate] Missing features: {set(expected_names) - set(features.keys())}"
        )
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

    return True


# ============================================================
# MODULE TEST (runs when imported)
# ============================================================

if __name__ == "__main__":
    # Quick smoke test
    print("\n" + "=" * 60)
    print("FEATURE EXTRACTION - SMOKE TEST")
    print("=" * 60)

    test_urls = [
        "https://example.com",
        "http://example.com/login",
        "https://example.com/login?id=123&token=abc&redirect=https://evil.com",
        "http://suspicious-phishing-site.top/verify-account",
    ]

    for url in test_urls:
        print(f"\nURL: {url}")
        print("-" * 60)

        # Extract 8 features
        features_8 = extract_features(url, include_https=True)
        print("8-Feature Model:")
        for name, value in features_8.items():
            if isinstance(value, float):
                print(f"  {name:30s} = {value:.4f}")
            else:
                print(f"  {name:30s} = {value}")

        # Validate
        is_valid = validate_features(features_8, include_https=True)
        print(f"Valid: {is_valid}")

    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)
