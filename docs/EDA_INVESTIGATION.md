# Exploratory Data Analysis Report: Phishing URL Detection

**Project Branch:** `feature/deep-eda-investigation`  
**Date:** October 10, 2025  
**Objective:** Conduct comprehensive exploratory data analysis on the PhiUSIIL dataset to identify optimal URL-only features for phishing detection and justify feature selection decisions.

---

## Executive Summary

This report documents the exploratory data analysis (EDA) performed on the PhiUSIIL Phishing URL Dataset. The analysis focused on data quality assessment, feature evaluation, and selection of URL-only features to ensure reliable, high-performance phishing detection without requiring webpage content access.

**Key Outcomes:**

- Dataset cleaned: 235,370 unique URLs after removing duplicates.
- Feature set optimized: 8 URL-only features selected based on separation analysis and correlation checks.
- Categorical features evaluated: TLD retained via numeric encoding; Domain excluded due to cardinality and bias issues.

---

## Methodology

The EDA followed a systematic approach:

1. **Data Inspection:** Verified data integrity, class balance, and feature availability.
2. **Duplicate Removal:** Identified and removed URL duplicates to prevent data leakage.
3. **Feature Categorization:** Classified features into URL-only vs. page-content categories.
4. **Separation Analysis:** Computed effect sizes to rank feature discriminative power.
5. **Correlation Analysis:** Assessed redundancy among numeric features.
6. **Categorical Evaluation:** Analyzed TLD and Domain for inclusion feasibility.
7. **Feature Selection:** Prioritized top-performing features balancing performance and interpretability.

---

## Dataset Overview

- **Rows:** 235,795 URLs
- **Columns:** 54 features + 1 label
- **Missing values:** 0 (excellent data quality)
- **Class balance:** 57.2% legitimate (134,850) vs 42.8% phishing (100,945)

### Key Observations

#### 1. Feature Duplication Found

The dataset already contains:

- `URLLength` (but we compute `url_len`)
- `NoOfSubDomain` (but we compute `url_subdomains`)
- `DegitRatioInURL` (similar to our `url_digit_ratio`)

#### 2. TLD Diversity

- **695 unique TLDs** - shows real-world variety
- Common ones likely: `.com`, `.net`, `.org`
- Suspicious ones likely: `.tk`, `.ml`, `.ga` (free domains)

#### 3. Feature Categories (Revised)

| Category      | Count | Examples                                      |
|---------------|-------|-----------------------------------------------|
| URL Structure | 26    | URLLength, Domain, TLD, NoOfSubDomain         |
| URL Characters| 4     | CharContinuationRate, HasObfuscation          |
| Page Content  | 16    | LineOfCode, HasTitle, NoOfImage, NoOfSelfRef  |
| Behavioral    | 9     | Bank, Pay, Crypto, HasPasswordField           |

---

## Critical Issues Found

### Issue 1: URLLength Discrepancy
- Dataset's `URLLength` is consistently **1 character shorter** than actual URL length
- Example: `http://www.teramill.com` → Dataset says 22, actual is 23
- **Root cause:** TBD (investigating if dataset excludes protocol, trailing slash, or encoding issue)
- **Decision:** Use `len(URL)` as ground truth; validates our `url_len` feature engineering

### Issue 2: Label Encoding Verification
- Dataset convention: `0 = phishing`, `1 = legitimate` ✅
- Model training correctly treats `0` as positive class for fraud metrics ✅
- Display labels in notebook: **Verified correct** ✅


## Session 3: URLLength Discrepancy - RESOLVED

### Finding: Systematic +1 Offset
- **79.37%** of URLs: Dataset `URLLength` is 1 character shorter than actual
- **20.63%** of URLs: Exact match
- **Pattern:** Not correlated with protocol (`http` vs `https`)
- **Outliers:** Only 2 URLs with larger discrepancies

### Root Cause: Unknown Dataset Processing
- Likely an indexing or parsing quirk in original feature extraction
- Examples: https://www.southbankmosaics.com
→ Dataset: 31 | Actual: 32 (off by 1)

### Decision: Use `len(URL)` as Ground Truth ✅
**Rationale:**
1. Verifiable and reproducible
2. No mystery offset to explain
3. Ensures accuracy for new data without pre-computed features

**Trade-off:**
- Adds minimal computation (negligible)
- Slightly different from dataset's feature but more trustworthy

### Action Items:
- [x] Confirmed discrepancy is systematic (+1 in 79% of cases)
- [x] Decided to use `url_len = len(URL)` in feature manifest
- [ ] Document this in README (why we engineered 3 features)

## Session 4: Duplicate URL Removal

### Finding: 425 Duplicate URLs (0.18%)
- **Total rows:** 235,795
- **Unique URLs:** 235,370
- **Duplicates:** 425 URLs appearing exactly twice
- **Label consistency:** ✅ All duplicates have consistent labels

### Examples of Duplicated URLs: https://disclosepack.myportfolio.com/
https://barlandas.com/reprisedefunction/unzupdm/
http://34.149.138.117/

### Decision: Remove Duplicates ✅

**Rationale:**
1. **Prevent train/test leakage** - Eliminates risk of same URL in both sets
2. **Best practice** - Standard ML pipeline step
3. **Negligible data loss** - Only 0.18% of dataset
4. **Ensures generalization** - Model learns patterns, not specific URLs

**After deduplication:**
- **235,370 unique URLs** (matches fingerprint)
- Label distribution unchanged
- Ready for train/test split

### Interview Talking Points:
- "Found and removed 425 duplicate URLs to prevent data leakage"
- "All duplicates had consistent labels (no contradictions)"
- "Final dataset: 235,370 unique URLs for training"

eda_doc_content = """# Deep EDA Investigation Log
**Branch:** `feature/deep-eda-investigation`  
**Date:** {date}  
**Goal:** Thoroughly explore PhiUSIIL dataset and select optimal URL-only features

---

## Executive Summary

### Dataset After Cleaning
- **235,370 unique URLs** (removed 425 duplicates)
- **Class balance:** 57.3% legitimate, 42.7% phishing (well-balanced)
- **Zero missing values** (excellent data quality)
- **25 URL-only features** identified (no page fetching required)

### Feature Selection Decision: OPTIMAL 8 FEATURES
After systematic evaluation of all 25 URL-only features using separation analysis and correlation checks, selected:

1. **IsHTTPS** (separation: 2.829) - Strongest discriminator
2. **TLDLegitimateProb** (separation: 2.012) - TLD reputation score
3. **CharContinuationRate** (separation: 1.372) - Character repetition patterns
4. **SpacialCharRatioInURL** (separation: 1.330) - Special character density
5. **URLCharProb** (separation: 0.889) - Character distribution entropy
6. **LetterRatioInURL** (separation: 0.825) - Letter density
7. **NoOfOtherSpecialCharsInURL** (separation: 0.562) - Special char count
8. **DomainLength** (separation: 0.324) - Domain name length

**Rationale:**
- Prioritized features with separation > 0.8 (strong discriminators)
- Avoided highly correlated pairs (URLLength corr=0.96 with NoOfLettersInURL)
- Balanced predictive power with interpretability
- All features extractable from URL string alone (no page fetch)

---

## Session 1-3: Data Quality & Duplicates

### Duplicate URL Removal
- **Found:** 425 duplicate URLs (0.18% of dataset)
- **Pattern:** All duplicates appeared exactly twice
- **Label consistency:** All duplicates had consistent labels (no contradictions)
- **Action:** Removed duplicates, kept first occurrence
- **Result:** 235,370 unique URLs for modeling

**Why this matters:**
Prevents train/test leakage where same URL appears in both sets, which would artificially inflate validation metrics.

### URLLength Discrepancy Investigation
- **Finding:** Dataset's `URLLength` systematically 1 char shorter than actual (79% of cases)
- **Root cause:** URLs without trailing slash are off by +1; those with slash match 64% of time
- **Decision:** Will engineer `url_len = len(URL)` as ground truth in feature engineering notebook

---

## Session 4: Feature Distribution Analysis

### URL-Only Feature Identification
Total of **25 features** can be extracted from URL alone:

**Structure (7):** URLLength, DomainLength, IsDomainIP, TLD, TLDLength, NoOfSubDomain, IsHTTPS

**Characters (15):** NoOfLettersInURL, LetterRatioInURL, NoOfDegitsInURL, DegitRatioInURL, 
NoOfEqualsInURL, NoOfQMarkInURL, NoOfAmpersandInURL, NoOfOtherSpecialCharsInURL, 
SpacialCharRatioInURL, HasObfuscation, NoOfObfuscatedChar, ObfuscationRatio, 
CharContinuationRate, URLCharProb, TLDLegitimateProb

**Behavioral (3):** Bank, Pay, Crypto (keyword presence)

### Separation Score Analysis

**Methodology:**
separation = |median_phish - median_legit| / pooled_std
**Tier Classification:**
- **TIER 1 (Must-Have):** separation > 1.3 → 4 features
- **TIER 2 (Strong):** 0.8 < separation < 1.3 → 2 features  
- **TIER 3 (Moderate):** 0.3 < separation < 0.8 → 2 features
- **TIER 4 (Weak):** separation < 0.3 → 16 features (excluded)

**Key Finding:**
`IsHTTPS` has separation of **2.829** - phishing sites use HTTP 50.9% of time, legitimate sites use HTTPS 100% of time. This is the single strongest discriminator.

---

## Session 5: Correlation Analysis

### High Correlation Pairs (|r| > 0.8)
- URLLength ↔ NoOfLettersInURL: **0.96** (strong redundancy)
- URLLength ↔ NoOfDegitsInURL: **0.84** (redundant)
- NoOfDegitsInURL ↔ NoOfEqualsInURL: **0.81** (query param correlation)

**Implication:** Including both `URLLength` and `NoOfLettersInURL` adds minimal information. Selected `DomainLength` instead for specificity.

### Moderate Correlations (0.6 < |r| < 0.8)
- SpacialCharRatioInURL ↔ CharContinuationRate: **-0.71** (inverse relationship)
- DegitRatioInURL ↔ URLCharProb: **-0.71**

**Action:** Both included in final selection as they capture different aspects (character density vs distribution entropy).

---

## Session 6: Final Feature Selection

### Comparison: Original vs Optimal

**Original 8-feature selection:**
- 3 TIER 1 features (good)
- 1 TIER 2 feature (good)
- 1 TIER 3 feature (moderate)
- **3 TIER 4 features (weak)** ← Problem!

Included weak features: `URLLength` (0.18), `DegitRatioInURL` (0.00), `NoOfSubDomain` (0.00)

Missing: `IsHTTPS` (strongest predictor)

**Optimal 8-feature selection:**
- 4 TIER 1 features
- 2 TIER 2 features
- 2 TIER 3 features
- 0 TIER 4 features ← Much stronger

**Decision:** Adopt optimal selection for maximum predictive power.

---

---

## Session 7: Categorical Feature Analysis

### TLD and Domain Evaluation

This section examines the categorical features TLD and Domain to assess their suitability for inclusion in the feature set.

#### TLD Analysis

Key findings from TLD distribution analysis:

1. **High-Risk TLDs (phishing rate > 80%)**

   - `.top`: 99.9% phishing (2,325 out of 2,327 URLs)
   - `.dev`: 98.6% phishing (2,289 out of 2,322)
   - `.app`: 97.8% phishing (6,327 out of 6,467)
   - `.co`: 91.5% phishing (4,950 out of 5,408)
   - `.io`: 89.7% phishing (3,742 out of 4,174)

   These five TLDs account for 19,633 phishing URLs, representing a significant portion of malicious activity.

2. **TLDLegitimateProb Validation**

   Comparison of actual phishing rates with TLDLegitimateProb scores:

   - `.app`: Actual phishing rate 97.8% | TLDLegitimateProb: 0.002 (accurately identifies as high-risk)
   - `.co`: Actual phishing rate 91.5% | TLDLegitimateProb: 0.006 (accurately identifies as high-risk)
   - `.org`: Actual phishing rate 12.1% | TLDLegitimateProb: 0.080 (accurately identifies as low-risk)
   - `.edu`: Actual phishing rate 0.3% | TLDLegitimateProb: High (expected for legitimate TLD)

   **Conclusion**: TLDLegitimateProb effectively captures TLD-based risk, providing a numeric feature with strong discriminative power (separation score: 2.012). It serves as an efficient encoding of TLD reputation.

#### Domain Analysis

Analysis of the Domain feature reveals several limitations:

- **High Cardinality**: 220,086 unique domains across 235,370 URLs, resulting in an average of 1.07 URLs per domain. One-hot encoding would generate 220,000 features, most of which would be sparse and ineffective.

- **Limited Generalization**: Only 54 domains (0.025%) appear in both phishing and legitimate classes, indicating poor overlap. Models trained on this would primarily memorize specific domains rather than learn generalizable patterns.

- **Data Collection Bias**: Prominent domains such as `docs.google.com` and `s3.amazonaws.com` exhibit 100% phishing rates due to the dataset capturing only abusive instances, not legitimate usage. This introduces significant bias and potential for overfitting.

**Recommendation**: Exclude the Domain feature due to its specificity, high cardinality, and associated risks of data leakage and poor generalization. Focus on TLD-level features for domain-related insights.

---

## Conclusions

### 1. Why URL-Only Features?

- **Speed:** 5-10ms prediction (no HTTP fetch)
- **Reliability:** No dependency on site availability or anti-scraping
- **Compliance:** Passive analysis, no interaction with suspect sites
- **Simplicity:** 8 numeric features, easy to validate and monitor

### 2. Feature Engineering Philosophy

- Started with 25 URL-only candidates
- Ranked by separation score (discriminative power)
- Removed highly correlated pairs (avoid redundancy)
- Selected top 8 balancing performance and interpretability

### 3. Data Quality Steps

- Removed 425 duplicates (0.18%) to prevent train/test leakage
- Validated feature consistency (URLLength discrepancy found and documented)
- Confirmed zero missing values

### 4. Trade-offs Acknowledged

- Excluded page-content features (HTMLLineOfCode, NoOfImages) for speed
- Accepted moderate correlation between SpacialCharRatio and CharContinuationRate
- Prioritized interpretability over complex feature interactions

---

## Artifacts Generated

### Visualizations

- `outputs/eda/all_url_only_features_distribution.png` - Feature distributions by class
- `outputs/eda/url_features_correlation_heatmap.png` - Correlation matrix

### Data Files

- `data/processed/phiusiil_clean_deduped.csv` - Cleaned, deduplicated dataset
- `outputs/eda/feature_separation_scores.csv` - Separation analysis for all features
- `outputs/eda/feature_correlations.csv` - Correlation matrix
- `outputs/eda/eda_summary.json` - Structured summary

---

## Next Steps

1. **Feature Engineering Notebook** (`01_feature_engineering.ipynb`)
   - Engineer: `url_len`, `url_digit_ratio`, `url_subdomains` for validation
   - Map optimal 8 features to dataset columns
   - Save final feature set: `phiusiil_clean_urlfeats.csv`

2. **Model Training Notebook** (`02_baseline_and_calibration.ipynb`)
   - Train on optimal 8 features
   - Compare performance vs original selection
   - Calibrate probabilities (isotonic)

3. **Documentation Updates**
   - Update README with feature selection rationale
   - Document trade-offs in model card

---

## Final Decision: Feature Set LockedFeature Definitions

**IsHTTPS:** Binary flag for HTTPS protocol (1) vs HTTP (0)  (separation: 2.829)

**TLDLegitimateProb:** Probability that TLD (.com, .org, etc.) is used by legitimate sites (lookup table)(separation: 2.012)

**CharContinuationRate:** Measure of character repetition (aaaaa, 11111) (separation: 1.372)

**SpacialCharRatioInURL:** Ratio of special characters (-, _, @, etc.) to total length (separation: 1.330)

**URLCharProb:** Character distribution entropy (randomness score) (separation: 0.889)

**LetterRatioInURL:** Ratio of letters to total length  (separation: 0.825)

**NoOfOtherSpecialCharsInURL:** Count of special characters (excluding ?, =, &)  (separation: 0.562)

**DomainLength:** Length of domain name (e.g., "paypal.com" = 10)
""".format(date=pd.Timestamp.now().strftime("%Y-%m-%d")) (separation: 0.324)

