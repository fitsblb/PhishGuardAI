# Feature Extraction Documentation

## Overview
All features extracted using `src/common/feature_extraction.py` for training/serving consistency.

## Feature Definitions

### IsHTTPS
- **Type:** Binary (0/1)
- **Definition:** Whether URL uses HTTPS protocol
- **Legitimate URLs:** 95% use HTTPS
- **Phishing URLs:** 60% use HTTPS (mixed)

### TLDLegitimateProb
- **Type:** Float [0, 1]
- **Definition:** Bayesian legitimacy probability for top-level domain
- **Source:** `common/tld_probs.json` (695 TLDs with frequency counts)
- **Priors:** α=1, β=2 (conservative, assumes unknown TLDs are risky)
- **Examples:**
  - .com: 0.611
  - .org: 0.709
  - .tk (Tokelau): 0.019 (high phishing)

### 3. CharContinuationRate
- **Type:** Float [0, 1]
- **Definition:** Ratio of consecutive identical characters
- **Formula:** (count of repeated chars) / (total chars - 1)
- **Examples:**
  - "abc" → 0.0 (no repetition)
  - "aaa" → 1.0 (all repeated)
  - "google.com" → 0.176 (some repetition)

### 4. SpacialCharRatioInURL
- **Type:** Float [0, 1]
- **Definition:** Density of special characters in URL
- **Special chars:** ! @ # $ % ^ & * ( ) _ + - = [ ] { } | ; : , . < > ? /
- **Formula:** (count of special chars) / (total chars)
- **Examples:**
  - "http://example.com" → 0.16
  - "http://ex.com/login?id=123&token=abc" → 0.23

### 5. URLCharProb
- **Type:** Float [0, 1]
- **Definition:** Proportion of common URL characters (alphanumeric + :/.?=&-_)
- **Formula:** (count of common chars) / (total chars)
- **Purpose:** Measures how "URL-like" the character distribution is
- **Examples:**
  - "http://example.com" → 0.95 (all common chars)
  - "http://ex.com/@@##$$" → 0.70 (unusual chars)

### 6. LetterRatioInURL
- **Type:** Float [0, 1]
- **Definition:** Density of letter characters (A-Za-z) in URL
- **Formula:** (count of letters) / (total chars)
- **Examples:**
  - "http://example.com" → 0.63
  - "http://ex.com/123" → 0.47

### 7. NoOfOtherSpecialCharsInURL
- **Type:** Integer [0, ∞)
- **Definition:** Total count of special characters in URL
- **Same character set as SpacialCharRatioInURL but returns count**
- **Examples:**
  - "http://example.com" → 3
  - "http://ex.com/login?id=123&token=abc" → 8

### 8. DomainLength
- **Type:** Integer [0, ∞)
- **Definition:** Length of the domain component (netloc)
- **Examples:**
  - "http://example.com" → 11
  - "https://www.very-long-suspicious-domain.com" → 32

## Training/Serving Consistency
- ✅ Same extraction code for training and production
- ✅ No data leakage (trained on raw PhiUSIIL URLs only)
- ✅ Validated: Batch extraction matches live extraction
- ✅ Deterministic (same URL always gives same features)

### **Step 4: Clean Up Notebooks (30 min)**


