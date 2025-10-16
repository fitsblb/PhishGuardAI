# 🛡️ PhishGuard v0.1.0

![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

**Modern, explainable phishing-URL screening**, a small, production-shaped MVP you can run locally, in Docker, or wire to a tiny LLM judge.

> **At a glance**
> - URL-only baseline model (fast, reproducible), calibrated and served via a lightweight API  
> - Gateway applies **policy bands** with a configurable **gray zone** (≈14% by default)  
> - "Borderline" cases get a second opinion from a **Judge** (rule-based stub or **LLM via Ollama**)  
> - Clear observability (`/stats`), data contract checks, and slim Docker image

---

## 🎯 Why PhishGuard?

Phishing detection lives on a spectrum: some URLs are obviously benign or malicious, while many sit in the **gray zone**. PhishGuard embraces that reality:
- **Decide confidently** where possible (ALLOW/BLOCK).
- **Escalate thoughtfully** (REVIEW) when signals are borderline.
- **Explain decisions** with human-readable rationales.

This design mirrors real incident response workflows and scales from local demos to heavier pipelines.

---

## 🧭 How it works (high level)

```
[ Client ] → /predict ─┬─> Policy (thresholds)
                       │   ├─ p < low → ALLOW
                       │   ├─ p ≥ high → BLOCK
                       │   └─ low ≤ p < high → REVIEW → Judge (stub or LLM)
                       └──> Final decision + rationale (if judged)
```

- **Model Service** returns `p_malicious = P(phish)` from a saved, calibrated pipeline (heuristic fallback if model is absent).
- **Gateway** reads thresholds, applies the banding policy, and consults the **Judge** only in the gray zone.
- **Judge** can be a deterministic stub (default) or a tiny LLM via **Ollama**; errors auto-fallback to the stub (no downtime).

---

## 🗂️ Repository Structure (what goes where)

```
├─ src/                                    # Core application source code
│  ├─ gateway/                            # FastAPI gateway service - handles policy bands, judge integration, and API endpoints
│  │  ├─ main.py                          # Gateway FastAPI application with /predict, /health, /stats endpoints
│  │  └─ judge_wire.py                    # Judge service integration and wiring logic
│  ├─ model_svc/                          # FastAPI model service - serves calibrated ML models for phishing prediction
│  │  └─ main.py                          # Model service FastAPI app with /predict endpoint for p_malicious scoring
│  ├─ judge_svc/                          # Judge service components - provides second opinion for gray-zone cases
│  │  ├─ contracts.py                     # Pydantic schemas for JudgeRequest/JudgeResponse data contracts
│  │  ├─ stub.py                          # Deterministic rule-based judge implementation (default, fast, explainable)
│  │  └─ adapter.py                       # LLM judge adapter for Ollama integration with automatic fallback to stub
│  └─ common/                             # Shared utilities and cross-service components
│     ├─ thresholds.py                    # Threshold loading and decision logic helpers for policy bands
│     ├─ stats.py                         # In-process metrics collection and /stats endpoint implementation
│     └─ audit.py                         # Optional MongoDB audit logging (fail-open, development-only)
├─ configs/                                # Configuration files for different environments
│  └─ dev/                                # Development environment configurations
│     └─ thresholds.json                  # Policy band thresholds (low/high bounds, gray-zone rate ~14%)
├─ models/                                 # Trained ML model artifacts and metadata
│  └─ dev/                                # Development model versions
│     ├─ model.pkl                        # Serialized calibrated classifier pipeline (production-ready)
│     └─ model_meta.json                  # Model metadata (feature order, class mapping, probability column index)
├─ notebooks/                              # Jupyter notebooks for data exploration, model development, and analysis
│  ├─ 00_eda.ipynb                        # Exploratory Data Analysis (EDA) - dataset profiling and feature discovery
│  ├─ 01_baseline_and_calibration.ipynb   # Baseline model training and probability calibration experiments
│  └─ 03_ablation_url_only.ipynb          # URL-only model development, ablation studies, and threshold optimization
├─ scripts/                                # Utility scripts for data processing and validation
│  ├─ materialize_url_features.py         # Feature engineering pipeline for URL morphological analysis
│  └─ ge_check.py                         # Data contract validation using Great Expectations (columns, types, ranges)
├─ docker/                                 # Docker-related files and configurations
│  └─ gateway.Dockerfile                  # Multi-stage Docker build for slim production gateway image
├─ .github/workflows/                     # GitHub Actions CI/CD pipelines
│  ├─ ci.yml                              # Main CI pipeline (tests, linting, Docker build)
│  └─ data-contract.yml                   # Data validation pipeline (runs ge_check.py on pull requests)
├─ README.md                              # Project documentation (this file)
└─ .env.example                           # Environment variable template (judge backend, thresholds, etc.)

# Additional Project Directories & Files

├─ data/                                  # Dataset storage and processing artifacts
│  ├─ raw/                                # Raw, unmodified datasets (PhiUSIIL Phishing URL Dataset)
│  ├─ processed/                          # Cleaned and engineered datasets ready for model training
│  └─ tld_probs.json                      # Pre-computed legitimate probability scores for top-level domains
├─ docs/                                  # Documentation and analysis artifacts
│  ├─ EDA_INVESTIGATION.md                # Exploratory data analysis findings and insights
│  ├─ model_docs.md                       # Model architecture and performance documentation
│  └─ MODELING.md                         # Modeling methodology, experiments, and results
├─ outputs/                               # Analysis outputs and generated artifacts
│  ├─ eda/                                # EDA visualizations and statistical summaries
│  ├─ model/                              # Model training outputs and evaluation metrics
│  └─ feature_comparison_v1_vs_v2.csv     # Feature engineering comparison results
├─ tests/                                 # Test suite for quality assurance
│  ├─ test_gateway_*.py                   # Gateway service integration and unit tests
│  ├─ test_judge_*.py                     # Judge service functionality tests
│  ├─ test_model_svc.py                   # Model service API and prediction tests
│  └─ test_threshold_*.py                 # Threshold logic and policy band tests
├─ gx/                                    # Great Expectations data validation suite
│  ├─ great_expectations.yml              # GX configuration and data source definitions
│  ├─ expectations/                       # Data quality expectation suites
│  ├─ checkpoints/                        # Validation checkpoints and test definitions
│  └─ validations/                        # Validation run results and reports
├─ mlartifacts/                           # MLflow experiment tracking artifacts
│  └─ [experiment_id]/                    # Individual experiment runs and metadata
├─ mlruns/                                # MLflow run tracking database and logs
├─ requirements*.txt                      # Python dependency specifications for different environments
├─ pyproject.toml                         # Python project configuration (dependencies, tools, metadata)
├─ pytest.ini                             # Pytest testing framework configuration
├─ .pre-commit-config.yaml                # Pre-commit hooks configuration (linting, formatting)
├─ .flake8, .bandit                       # Code quality and security linting configurations
└─ docker-compose.yml                     # Multi-service Docker composition for local development
```

---

## Quick Start

### **Local (stub judge, no Docker)**

```bash
pip install -U pip && pip install -e ".[dev]"
uvicorn model_svc.main:app --reload --port 9000   # terminal A (serves model)
# Optional: tiny LLM via Ollama on host (e.g., llama3.2:1b)
# ollama serve && ollama pull llama3.2:1b
export MODEL_SVC_URL=http://127.0.0.1:9000        # terminal B
uvicorn gateway.main:app --reload
```

**Test:**

```bash
curl -X POST localhost:8000/predict -H "Content-Type: application/json" \
  -d '{"url":"http://ex.com/login?acct=12345","p_malicious":0.45}'
```

### **Docker (mount your thresholds; stub or LLM)**

**Build:**

```bash
docker build -f docker/gateway.Dockerfile -t phishguard-gateway:local .
```

**Run (stub judge; thresholds mounted):**

```bash
docker run --rm -p 8000:8000 \
  -e THRESHOLDS_JSON=/app/configs/dev/thresholds.json \
  -v "$PWD/configs/dev/thresholds.json:/app/configs/dev/thresholds.json:ro" \
  phishguard-gateway:local
```

**Run (LLM judge via Ollama on host):**

```bash
docker run --rm -p 8000:8000 \
  -e THRESHOLDS_JSON=/app/configs/dev/thresholds.json \
  -e JUDGE_BACKEND=llm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -e JUDGE_MODEL=llama3.2:1b \
  phishguard-gateway:local
```

### **Endpoints**

- `/health` – service liveness
- `/config` – active thresholds & source
- `/predict` – decision API (POST JSON: `{"url": "...", "p_malicious": 0.45}` or omit `p_malicious` to let the gateway call the model service)
- `/stats`, `/stats/reset` – simple counters for demos

---

## Configuration (env toggles)

| Key | Default | Notes |
|-----|---------|-------|
| `THRESHOLDS_JSON` | `configs/dev/thresholds.json` | Banding policy (low, high, t_star, gray_zone_rate) |
| `JUDGE_BACKEND` | `stub` | `stub` \| `llm` (Ollama) |
| `OLLAMA_HOST` | `http://localhost:11434` | Only if `JUDGE_BACKEND=llm` |
| `JUDGE_MODEL` | `llama3.2:1b` | Tiny model for rationales |
| `MODEL_SVC_URL` | (unset) | If set, gateway queries model service when client omits `p_malicious` |
| `MAX_REQ_BYTES` | `8192` | Gateway body size limit (413) |
| `MONGO_URI` | (unset) | Optional audit logs (dev only; fail-open) |

---

## Data, Features & Contract

**Dataset:** [PhiUSIIL Phishing URL Dataset](https://www.kaggle.com/datasets/ndarvind/phiusiil-phishing-url-dataset) — 235,795 URLs with URL-level & page-level features.

**Citation:** Prasad, A., & Chandra, S. (2023). PhiUSIIL: A diverse security profile empowered phishing URL detection framework based on similarity index and incremental learning. *Computers & Security*, 103545.  
**DOI:** [10.1016/j.cose.2023.103545](https://doi.org/10.1016/j.cose.2023.103545)

**MVP scope:** URL-only signals (fast, portable). The trained pipeline and manifest are frozen to avoid leakage across feature families.

**Data contract:** `scripts/ge_check.py` validates required columns (`url_len`, `url_digit_ratio`, `url_subdomains`), dtypes, and ranges. CI runs it when a processed CSV is present.

---

## Quality & Dev Workflow

- **Tests:** unit + e2e (FastAPI TestClient); run `pytest -q`
- **Pre-commit:** black, isort, flake8, mypy, bandit (`pre-commit run --all-files`)
- **Branching:** feature branches → squash-merge into dev; main is protected and release-tagged.
- **Releases:** v0.1.0 tagged; next minor improvements tracked as issues/milestones.

---

## Observability & Audit

- `/stats` exposes in-process counters (policy vs final decisions; judge verdicts).
- Optional Mongo audit writes are behind `MONGO_URI` (no-op by default, guarded with fail-open behavior).

---

## Safety Notes

- Inputs are validated (URL length caps, body size 413, localhost-only CORS for dev).
- The judge never blocks the service: if LLM is unavailable, PhishGuard falls back to the stub.

---

## Roadmap (v0.2 ideas)

- MLflow/registry integration (optional)
- Rich judge dashboards (Mongo → charts)  
- Prompt tuning & confidence calibration
- Cloud deploy (container runtime with secrets)

---

## Attribution

**Dataset:** PhiUSIIL Phishing URL Dataset — © the respective authors. Used under the terms provided by the source. Please cite:

> Prasad, A., & Chandra, S. (2023). PhiUSIIL: A diverse security profile empowered phishing URL detection framework based on similarity index and incremental learning. *Computers & Security*, 103545. DOI: [10.1016/j.cose.2023.103545](https://doi.org/10.1016/j.cose.2023.103545).

---

## License

MIT License. See [LICENSE](LICENSE) file for details.
```

---

## Runbook: Local Dev & Demo

This project runs fully **locally** with a URL-only model and a judge that’s either a **deterministic stub** (default) or an **LLM via Ollama** (optional). Follow these steps in order.

### 0) Prereqs

- Python 3.11 in a virtual env (conda or venv)
- Editable install:

  ```bash
  pip install -U pip
  pip install -e ".[dev]"
  ```

## Docker Quick Start

This image runs the **gateway** with either the deterministic **stub** judge (default) or an **LLM** judge via **Ollama**. It's a slim multi-stage image; no dev deps included.

### Build (local image)

```bash
docker build -f docker/gateway.Dockerfile -t phishguard-gateway:local .
```

### Run with stub judge (no Ollama needed)

```bash
docker run --rm -p 8000:8000 \
  -e THRESHOLDS_JSON=/app/configs/dev/thresholds.json \
  phishguard-gateway:local
```

### Run with LLM judge (tiny model via Ollama)

On the host, start Ollama and pull a small model (e.g., llama3.2:1b).

Start the container and point it at the host:

```bash
docker run --rm -p 8000:8000 \
  -e THRESHOLDS_JSON=/app/configs/dev/thresholds.json \
  -e JUDGE_BACKEND=llm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -e JUDGE_MODEL=llama3.2:1b \
  -e JUDGE_TIMEOUT_SECS=12 \
  phishguard-gateway:local
```

### Smoke checks

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/config
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"url":"http://ex.com/login?acct=12345","p_malicious":0.45}'
curl http://127.0.0.1:8000/stats
```

---

### Latest aditions will organize

---

## Model Performance

**Validation Metrics (PhiUSIIL Dataset):**

- PR-AUC (phishing detection): **99.92%**
- F1-Macro: **99.70%**
- Brier Score: **0.0026**
- False Positive Rate: **0.09%** (23/26,970 legitimate URLs)

**Feature Set (8 features):**

- IsHTTPS, TLDLegitimateProb, CharContinuationRate
- SpacialCharRatioInURL, URLCharProb, LetterRatioInURL
- NoOfOtherSpecialCharsInURL, DomainLength

**Threshold Policy:**
- Low threshold: 0.004 → ALLOW (below this)
- High threshold: 0.999 → BLOCK (above this)
- Gray zone: 10.9% → REVIEW (escalate to judge)

**Known Limitations:**
- Model trained on PhiUSIIL dataset (2019-2020 URLs)
- Major tech companies (google.com, github.com) are out-of-distribution
- Whitelist override implemented for known legitimate short domains

## 🎯 Model Performance

**Validation Metrics (PhiUSIIL Dataset, 47,074 samples):**
- **PR-AUC:** 99.92%
- **F1-Macro:** 99.70%
- **Brier Score:** 0.0026
- **False Positive Rate:** 0.09% (23/26,970 legitimate URLs)

**Feature Set (8 URL-only features):**
1. IsHTTPS - Protocol security
2. TLDLegitimateProb - TLD legitimacy (695 TLDs, Bayesian priors)
3. CharContinuationRate - Character repetition ratio
4. SpacialCharRatioInURL - Special character density
5. URLCharProb - Character probability score
6. LetterRatioInURL - Alphabetic ratio
7. NoOfOtherSpecialCharsInURL - Special character count
8. DomainLength - Domain length

**Decision Framework:**
- **Whitelist:** 15 major domains (google.com, github.com, etc.) → Fast-path ALLOW
- **Policy Bands:** 89% automated (p<0.004 → ALLOW, p>0.999 → BLOCK)
- **Short Domain Routing:** len≤10, p<0.5 → Judge review (handles npm.org, bit.ly edge cases)
- **Gray Zone:** 11% escalated to judge for explainable decisions

**Performance (Single Instance):**
- Whitelist path: <10ms (p95)
- Model path: 20-30ms (p95)
- Judge path: 50-100ms (p95)
- Throughput: ~150 req/sec

See [JUDGE_LOGIC.md](docs/JUDGE_LOGIC.md) for complete decision flow.


Add to README.md:

## Performance Characteristics

**Latency (p95):**
- Whitelist path: <10ms
- Policy band (no judge): ~20-30ms
- Gray zone (with judge): ~50-100ms

**Throughput:**
- Single instance: ~150 req/sec
- Scalability: Horizontal scaling via Kubernetes

**Tested on:** Local development machine
═══════════════════════════════════════════════════════════════ PHASE 4: FINAL POLISH (15 minutes) ═══════════════════════════════════════════════════════════════

4.1: Update README.md (10 min)
Add these sections:

## Model Performance

**Validation Metrics (PhiUSIIL Dataset, 47,074 samples):**
- **PR-AUC:** 99.92%
- **F1-Macro:** 99.70%
- **Brier Score:** 0.0026
- **False Positive Rate:** 0.09% (23/26,970 legitimate URLs)

**Feature Set (8 URL-only features):**
1. IsHTTPS - Protocol security
2. TLDLegitimateProb - TLD legitimacy (Bayesian priors)
3. CharContinuationRate - Character repetition
4. SpacialCharRatioInURL - Special character density
5. URLCharProb - Character probability
6. LetterRatioInURL - Alphabetic ratio
7. NoOfOtherSpecialCharsInURL - Special char count
8. DomainLength - Domain length

**Enhanced Routing:**
- Whitelist: 14 major tech domains (OOD handling)
- Policy Bands: 89% automated (ALLOW/BLOCK)
- Short Domain Routing: len≤10, p<0.5 → Judge
- Gray Zone: 11% escalated for review

### Enhanced Routing Logic

PhishGuardAI uses intelligent routing for edge cases:

- **Whitelist:** Known legitimate domains (Google, GitHub, etc.) → Fast-path ALLOW
- **Policy Bands:** High confidence cases (p<0.004 or p>0.999) → Automated ALLOW/BLOCK
- **Short Domain Routing:** Short domains (≤10 chars) with moderate confidence (p<0.5) → Judge review
- **Standard Gray Zone:** Normal domains in gray zone → Judge review

This handles distribution shift for short legitimate domains (npm.org, bit.ly) that aren't in the training data.

See [JUDGE_LOGIC.md](docs/JUDGE_LOGIC.md) for full decision flow.

See [JUDGE_LOGIC.md](docs/JUDGE_LOGIC.md) for decision flow details.