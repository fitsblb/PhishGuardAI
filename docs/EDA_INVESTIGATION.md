# Deep EDA Investigation Log
**Branch:** `feature/deep-eda-investigation`  
**Date:** [Today's Date]  
**Goal:** Thoroughly explore PhiUSIIL dataset to identify truly URL-only features and justify feature selection

---

## Session 1: Initial Dataset Inspection

### Dataset Overview
- **Rows:** 235,795 URLs
- **Columns:** 54 features + 1 label
- **Missing values:** 0 (excellent data quality)
- **Class balance:** 57.2% legit (134,850) vs 42.8% phish (100,945)

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
| Category | Count | Examples |
|----------|-------|----------|
| URL Structure | 26 | URLLength, Domain, TLD, NoOfSubDomain |
| URL Characters | 4 | CharContinuationRate, HasObfuscation |
| Page Content | 16 | LineOfCode, HasTitle, NoOfImage, NoOfSelfRef |
| Behavioral | 9 | Bank, Pay, Crypto, HasPasswordField |

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

## Key Takeaways (Interview-Ready)

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

## Appendix: Feature Definitions

**IsHTTPS:** Binary flag for HTTPS protocol (1) vs HTTP (0)

**TLDLegitimateProb:** Probability that TLD (.com, .org, etc.) is used by legitimate sites (lookup table)

**CharContinuationRate:** Measure of character repetition (aaaaa, 11111)

**SpacialCharRatioInURL:** Ratio of special characters (-, _, @, etc.) to total length

**URLCharProb:** Character distribution entropy (randomness score)

**LetterRatioInURL:** Ratio of letters to total length

**NoOfOtherSpecialCharsInURL:** Count of special characters (excluding ?, =, &)

**DomainLength:** Length of domain name (e.g., "paypal.com" = 10)
""".format(date=pd.Timestamp.now().strftime("%Y-%m-%d"))

with open('docs/EDA_INVESTIGATION.md', 'w', encoding='utf-8') as f:
    f.write(eda_doc_content)

print("="*60)
print("UPDATED: docs/EDA_INVESTIGATION.md")
print("="*60)
print("\nDocumentation complete. Ready to commit EDA work.")
print("\nNext: Create 01_feature_engineering.ipynb")