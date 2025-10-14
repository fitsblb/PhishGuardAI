# Feature Extraction Documentation

## Overview
All features extracted using `src/common/feature_extraction.py` for training/serving consistency.

## Feature Definitions

### 1. IsHTTPS
- **Type:** Binary (0/1)
- **Definition:** URL uses HTTPS protocol
- **Range:** [0, 1]

### 2. TLDLegitimateProb
- **Type:** Float
- **Definition:** Bayesian legitimacy probability for TLD
- **Range:** [0, 1]
- **Source:** `common/tld_probs.json` (695 TLDs)
- **Priors:** α=1, β=2 (conservative)

### 3. CharContinuationRate
- **Type:** Float
- **Definition:** Ratio of consecutive identical characters
- **Range:** [0, 1]
- **Example:** "google.com" → 0.176

[... continue for all 8 features ...]

## Training/Serving Consistency
- ✅ Same extraction logic for training and production
- ✅ No data leakage (trained on raw PhiUSIIL URLs)
- ✅ Validated: Batch vs live extraction matches

### **Step 4: Clean Up Notebooks (30 min)**


```
notebooks/
  ├── 00_eda.ipynb                    
  ├── feature_engineering.ipynb       
  ├── 03_ablation_url_only.ipynb       
  ├── 03_ablation_url_only_copy.ipynb 
  └── archive/                         
      └── old_experiments/              
```