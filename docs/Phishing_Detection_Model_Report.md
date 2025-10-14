## Phishing Detection Model Report: Performance, Optimization, and Distribution Shift Analysis

### 1. Executive Summary

This report details the successful development and optimization of two phishing detection models: an 8-feature "Research Model" and a 7-feature "Production Model." Both models demonstrate exceptional performance, with PR-AUC scores of 0.9992 and 0.9988, respectively. The Production Model is recommended for deployment due to its robustness against future changes in the HTTPS landscape.

A sophisticated threshold optimization strategy has been implemented, incorporating a "gray-zone" for uncertain classifications that require review. While the models exhibit near-perfect accuracy on in-distribution data, a critical finding reveals a significant "distribution shift" issue. Major legitimate websites like Google.com and GitHub.com are being misclassified as phishing due to discrepancies between their URL features and the characteristics of the training data. This report delves into the root causes and offers a clear understanding of this challenge.

### 2. Model Development and Artifacts

Two primary models have been developed and saved for production:

*   **Research Model (8-feature with IsHTTPS):**
    *   **Performance (PR-AUC):** 0.9992
    *   **Purpose:** Achieves maximum performance on the current dataset.
    *   **Path:** `models\dev\model_8feat.pkl`

*   **Production Model (7-feature without IsHTTPS):**
    *   **Performance (PR-AUC):** 0.9988
    *   **Purpose:** Designed for robustness against the anticipated 2025 HTTPS phishing landscape, removing `IsHTTPS` as a feature.
    *   **Path:** `models\dev\model_7feat.pkl`
    *   **Recommendation:** **RECOMMENDED FOR DEPLOYMENT**

Associated metadata and optimized thresholds for both models have also been saved, ensuring readiness for service integration.

### 3. Enhanced Threshold Optimization and Decision Logic

A refined threshold optimization process has been implemented, moving beyond a simple binary classification to include a "REVIEW" gray-zone:

*   **Optimal Decision Threshold (`t_star`):** 0.350 (achieving an F1-macro of 0.9972)
*   **Gray-Zone Band:** A range from 0.004 (Low) to 0.999 (High) creates a 10.9% gray-zone rate.
*   **Decision Distribution:**
    *   **ALLOW:** 48.1% (22,584 samples)
    *   **REVIEW:** 10.9% (5,135 samples)
    *   **BLOCK:** 41.0% (19,234 samples)

This multi-tiered decision logic allows for a more nuanced handling of URLs, flagging uncertain cases for manual review rather than making a potentially incorrect automated decision.

### 4. Model Performance and Key Insight: Distribution Shift

The models exhibit excellent performance on validation data, demonstrating high confidence in their predictions:

*   **Validation Prediction Distribution:**
    *   **Extreme Phishing (p >= 0.99):** 41.5%
    *   **Extreme Legitimate (p <= 0.01):** 55.2%
    *   **Moderate (0.01 < p < 0.99):** Only 3.3% (Uncertain)

*   **Misclassification Rate:** A remarkably low 0.09% misclassification rate for legitimate URLs (only 23 out of 26,970 legitimate samples were misclassified as phishing).

However, a critical issue identified is the misclassification of well-known legitimate URLs (e.g., `https://google.com`, `https://github.com`) as phishing.

This anomaly is attributed to a **distribution shift** between the training data and these common URLs. The training data, sourced from the PhiUSIIL dataset (2019-2020), primarily focuses on obscure and suspicious URLs and lacks representation from major legitimate tech companies.

### 5. Root Cause Analysis: The Impact of `URLCharProb` and `DomainLength`

Detailed debugging of `https://google.com` revealed specific feature disparities:

*   **`URLCharProb` Outlier:** The `URLCharProb` for `google.com` (1.000) is an extreme outlier, 4073.95 standard deviations from the training data mean (0.060). This feature, indicating the probability of characters appearing in URLs, suggests `google.com` uses a character distribution vastly different from the training examples.
*   **`DomainLength` Discrepancy:** `google.com` has a `DomainLength` of 10 characters, significantly shorter than the training data's average of 21.467 characters. The model appears to associate shorter, simpler domains with suspicious characteristics.
*   **`TLDLegitimateProb`:** While `google.com`'s TLDLegitimateProb (0.612) is within the training average, it is slightly lower than the average legitimate training TLD probability of 0.709.

**Conclusion:** The model's classification of `google.com` as phishing stems from its feature set being out-of-distribution compared to the training data. The model was trained on a dataset where legitimate URLs tended to have longer domains and different character probability distributions, leading it to perceive well-known, short, and simple legitimate domains as suspicious.

### 6. Recommendations

1.  **Deploy the 7-feature Production Model:** Proceed with the deployment of `model_7feat.pkl` as recommended, leveraging its robust design.
2.  **Implement Robust Out-of-Distribution Handling:** Develop and integrate a mechanism to detect and appropriately handle URLs that are significantly out-of-distribution. This could involve:
    *   **Whitelisting:** Create and maintain a curated whitelist of known legitimate domains that bypass model prediction.
    *   **Ensemble Methods:** Explore integrating other detection methods or a secondary model specifically designed for high-confidence legitimate URLs.
    *   **Data Augmentation:** Incrementally expand the training dataset to include a diverse range of legitimate, well-known URLs.
3.  **Monitor Gray-Zone Effectively:** Establish clear protocols and tools for reviewing URLs flagged within the "REVIEW" gray-zone to continuously refine the model and its thresholds.
4.  **Feature Engineering Review:** Re-evaluate features like `URLCharProb` and `DomainLength` to ensure they are universally applicable or consider alternative normalizations that are less susceptible to domain length biases.

### 7. Visualizing the Decision Process

>![alt text](../outputs/Visualizing_Decision_Proces.png)

*An illustrative flowchart showing the model's decision process: input URL, feature extraction, model prediction, threshold application (ALLOW, REVIEW, BLOCK), and finally, the output decision.*

This report highlights the dual success of achieving high-performing phishing detection models and the critical challenge of distribution shift. Addressing this shift through strategic data augmentation and robust OOD handling will be paramount for real-world reliability.