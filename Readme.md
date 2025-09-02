# NetworkSecurity 2.0 — Architecture & Project Plan

**Owner:** Fitsum (with ChatGPT as co-author)

**Purpose:** Elevate the original `networksecurity` phishing detection project into a production-ready, modular system with an LLM extension that (1) judges gray-zone cases and (2) produces human-readable explanations for all results — while keeping costs at zero (local models only).

---

## 1) Executive Summary

NetworkSecurity 2.0 is a **hybrid ML system** for phishing detection. The baseline is a tabular classifier trained on engineered URL features. On top of that, we add a **selective LLM judge** for uncertain predictions and a **universal explanation layer** that outputs concise, grounded rationales. The system is containerized, observable, and deployable through CI/CD. All LLM components run **locally** via Ollama (or a compatible runtime).

**Primary outcomes**

* Higher **precision at fixed recall** (cut false positives) by routing only gray-zone cases to a small local LLM judge.
* Clear, **non-technical explanations** for every prediction based on SHAP + policy-grounded text.
* Clean architecture; strong documentation; repeatable builds; secure config; testable end-to-end.

**Key principles**

* **Selective invocation**: LLM used only when the base model is uncertain.
* **Grounded outputs**: Explanations cite features/SHAP; no hallucinated claims.
* **Reversible design**: LLM layer can be disabled without breaking core pipeline.

---

## 2) Goals & Non‑Goals

**Goals**

1. Production-grade modular architecture with clear boundaries and contracts.
2. Deterministic ML pipeline: ingest → validate → transform → train → evaluate → package.
3. LLM extension (local) for uncertainty-gated judging + human-readable explanations.
4. Strong testing (unit + e2e), observability, and secure configuration.
5. CI/CD with container images, artifact retention, and environment promotion.

**Non‑Goals**

* Live web browsing of target URLs (out-of-scope for 2.0).
* Paid or external LLM APIs.
* Replacing the baseline classifier with an LLM.

---

## 3) System Context

```
[Dataset / MongoDB] → Ingestion → Validation → Transformation → Training → Final Artifacts
                                                             ↓
                                                       Serving API
                                                   (FastAPI + Uvicorn)
                                                             ↓
                                 ┌───────── High/Low confidence ─────────┐
                                 │                                        │
                           Template Explanation                    (No LLM)
                                 │                                        │
                                 └── Gray-zone (prob in [LOW,HIGH]) ─────┘
                                                    ↓
                                           LLM Judge (local)
                                                    ↓
                                          Score Fusion + Explanation
                                                    ↓
                                            JSON / CSV / HTML output
```

---

## 4) High-Level Architecture (Components)

1. **Data Layer**

   * **Source**: MongoDB collection or local CSV (phishing dataset).
   * **Artifacts**: Timestamped folders for each run; `final_model/` for production artifacts.

2. **Pipeline Layer (Batch)**

   * **Ingestion**: Read source → feature store CSV → stratified train/test split.
   * **Validation**: Schema check; drift report; row/column counts; dtype validation.
   * **Transformation**: Imputation/encoding; save `preprocessor.pkl`; output `train.npy/test.npy`.
   * **Training**: Grid/CV over candidate models; **classification metrics** (F1-macro, PR-AUC); save `model.pkl`.
   * **Packaging**: `NetworkModel(preprocessor, model)` wrapper for inference; versioned.

3. **Serving Layer (Online)**

   * **FastAPI**: `/predict` (CSV) and `/predict_explain` (JSON) endpoints.
   * **Uncertainty Router**: LOW/HIGH thresholds; only gray-zone invokes LLM.
   * **LLM Judge**: Local Ollama model → returns `phishing_score` + `reasons[]` (strict JSON).
   * **Explanations**: SHAP-based top signals + concise text; (optional) LLM paraphrase offline.
   * **Outputs**: JSON (primary), CSV/HTML (secondary) for human review.

4. **Observability & Ops**

   * Logging to stdout (JSON lines), request/latency counters, LLM call rate.
   * Health endpoints: `/healthz`, `/version`.
   * Metrics: precision\@recall, PR-AUC, LLM hit-rate, P95 latency.

5. **Security & Config**

   * `.env` or secrets manager; no secrets in code.
   * Uniform env names: `MONGO_DB_URL`, `MLFLOW_*` (optional), `THRESHOLDS_FILE`.

6. **CI/CD**

   * Build Docker image; run unit/e2e tests; push to registry; deploy to staging/prod.
   * Artifact retention (models, preprocessor, metrics reports) via object storage.

---

## 5) Detailed Module Breakdown

### 5.1 Package layout (proposed)

```
networksecurity/
  __init__.py
  config/
    settings.py             # env & constants loader
    schema.yaml             # feature schema
    thresholds.yaml         # LOW/HIGH, fusion α, model version
  data/
    sample_input.csv        # small demo file
  components/
    data_ingestion.py
    data_validation.py
    data_transformation.py
    model_trainer.py
  pipeline/
    training_pipeline.py
    post_classifier.py      # LLM routing + fusion + assembly of outputs
  services/
    llm_judge.py            # Ollama HTTP client, pydantic-validated JSON
    explainer.py            # SHAP + templated explanations
  utils/
    io.py                   # load/save pkl, npy, yaml
    metrics.py              # f1/precision/recall, PR-AUC
    model_eval.py           # classification-aware evaluation (GridSearchCV)
    logging.py
    validators.py           # input schemas for inference (Pydantic)
  api/
    app.py                  # FastAPI endpoints
    schemas.py              # request/response models
    templates/              # optional HTML table view
  tests/
    unit/                   # modules
    e2e/                    # small end-to-end run
final_model/
Artifacts/
```

### 5.2 Contracts & I/O

* **Training input**: CSV with exact schema in `config/schema.yaml`.
* **Training output**: `final_model/model.pkl`, `final_model/preprocessor.pkl`, metrics report JSON, and `thresholds.yaml`.
* **Prediction input**: CSV (batch) or JSON (record list) with required features.
* **Prediction output** (JSON): per-row `{ label, model_prob, final_prob, llm_used, llm_reasons[], top_signals[], explanation }`.

### 5.3 LLM Judge (local)

* Runtime: **Ollama** (`qwen2:7b-instruct` quant) or `mistral:7b-instruct` quant.
* API contract: strict JSON `{ phishing_score: 0..1, reasons: [string] }`.
* Safety: temperature 0.0–0.2; truncated, sanitized context; timeouts; retries; fail-safe fallback.

### 5.4 Explanations

* **Top signals**: SHAP top-k with sign (risk↑/risk↓) and values.
* **Text**: Template-first (always free); optional LLM paraphrase behind a flag.

---

## 6) Data & Features

* Use the 31-engineered features (as in the original project) with clear dtypes and allowed ranges.
* Validate counts and dtypes; reject out-of-schema inputs with actionable errors.
* Stratified train/test split. Track class balance.

---

## 7) Algorithms & Metrics

* Candidate models: RandomForest, XGBoost/GBM, Logistic Regression (with scaling), Linear SVC (calibrated), LightGBM (optional).
* **Model selection metric**: **F1-macro** primary; **PR-AUC** secondary; report ROC-AUC, precision, recall.
* **Thresholds**: LOW/HIGH derived from validation set quantiles to target LLM call-rate (\~10–20%).
* **Fusion**: `final_prob = α * model_prob + (1-α) * llm_score` (α default 0.5; tune by grid).

---

## 8) Security & Compliance

* Secrets only from env; `.env.example` provided.
* No user PII flows to LLM.
* No raw HTML or scripts into prompts.
* Containers run as non-root; network egress minimized.

---

## 9) Observability

* Structured logs (JSON lines) for: request id, latency, llm\_used, model\_version, thresholds\_version.
* Counters: total predictions, LLM invocations, parsing failures, fallback events.
* Health: `/healthz` (OK + model loaded), `/version` (git SHA, model ts).

---

## 10) CI/CD

* **Build**: Docker multi-stage (builder → slim runtime), pinned deps.
* **Test**: run unit and e2e (tiny dataset) on PR.
* **Scan**: basic security scan (Bandit + pip-audit) in CI.
* **Deploy**: push image to registry; rollout script uses env vars; maps `8080:8000`.
* **Artifacts**: store metrics report + model to object storage with run id.

---

## 11) API Spec (draft)

### `POST /predict_explain`

Request (JSON):

```json
{
  "records": [
    {"having_IP_Address": 1, "URL_Length": 54, "SSLfinal_State": 0, ...}
  ]
}
```

Response (JSON):

```json
{
  "model_version": "2025-09-01T12:00:00Z",
  "thresholds_version": "2025-09-01",
  "results": [
    {
      "label": "phishing",
      "model_prob": 0.52,
      "final_prob": 0.66,
      "llm_used": true,
      "llm_reasons": ["suspicious TLD", "young domain age"],
      "top_signals": [
        {"feature": "URL_Length", "value": 54, "contribution": 0.19},
        {"feature": "having_IP_Address", "value": 1, "contribution": 0.12}
      ],
      "explanation": "Model confidence 0.66 for 'phishing'. Top signals: URL_Length=54 (risk↑), having_IP_Address=1 (risk↑)."
    }
  ]
}
```

### `POST /predict`

* Existing CSV → HTML/CSV output preserved for compatibility.

### `GET /healthz`

* `{ status: "ok", model_loaded: true, model_version: "..." }`

### `GET /version`

* `{ git_sha: "...", model_version: "...", thresholds_version: "..." }`

---

## 12) Known Issues from Original Zip & Fix Plan

1. **Wrong selection metric (`r2_score`)** → Replace with F1-macro & PR-AUC; update `evaluate_models()`.
2. **Column-count validation bug** → Compare against `len(schema['columns'])`.
3. **Secrets in code (MLflow creds)** → Remove from source; load from env; rotate immediately.
4. **Env var inconsistency** → Use `MONGO_DB_URL` everywhere; add `.env.example`.
5. **Port mismatch in CI** → Use `-p 8080:8000` or set Uvicorn to 8080.
6. **S3 bucket typo** → Correct and validate existence/permissions.
7. **Synchronous training via `/train`** → Move to background job or CLI-only.
8. **Input validation at inference** → Strict Pydantic models and clear error messages.

---

## 13) Daily Task Plan (with intent & approach)

> **Cadence:** 10 working days. Each day has a definition of done (DoD).

**Day 1 — Repo Hygiene & Baseline Fixes**

* Intent: Make the base project correct & reproducible.
* Tasks: fix metrics (F1/PR-AUC), column-count check, env unification, remove secrets, port mapping, bucket name, add `.env.example`.
* DoD: `python main.py` succeeds; tests pass; `/healthz` returns OK; no hardcoded secrets.

**Day 2 — Configuration & Contracts**

* Intent: Centralize configuration and schemas.
* Tasks: `config/settings.py`; `config/schema.yaml`; `config/thresholds.yaml`; Pydantic inference models.
* DoD: Invalid input is rejected with actionable 400; thresholds loadable; unit tests for validators.

**Day 3 — Evaluation & Reports**

* Intent: Proper model selection and reporting.
* Tasks: GridSearchCV with F1-macro; PR curves; metrics JSON artifact; seed script for repeatable runs.
* DoD: Metrics JSON stored per run; CI uploads report artifact.

**Day 4 — SHAP Explanations**

* Intent: Deterministic, free explanations.
* Tasks: `services/explainer.py`; top-k SHAP; template explanations; API returns `top_signals`.
* DoD: `/predict_explain` returns explanations without LLM; tests verify sign/direction formatting.

**Day 5 — Uncertainty Router**

* Intent: Gate when we invoke the LLM.
* Tasks: derive LOW/HIGH from validation percentiles; implement `post_classifier.py`; add metrics for LLM hit-rate.
* DoD: Loggable gray-zone routing; unit tests for routing boundary conditions.

**Day 6 — Local LLM Runtime (Ollama) & Judge**

* Intent: Add LLM with strict JSON contract.
* Tasks: `services/llm_judge.py` (Ollama client); prompt in `policy/prompts/`; retries & timeouts; parsing validation.
* DoD: Gray-zone rows receive `llm_reasons` + fused `final_prob`; fallback works if LLM unavailable.

**Day 7 — API Surface & Formats**

* Intent: Solid UX for consumers.
* Tasks: finalize `/predict_explain` JSON; keep CSV/HTML compatible; add `/version`.
* DoD: Example requests documented; front-end/table renders; OpenAPI shows schemas.

**Day 8 — Tests & Observability**

* Intent: Confidence and visibility.
* Tasks: unit tests (components/services), e2e test on tiny dataset; logging fields; counters; simple Prometheus exporter (optional).
* DoD: CI is green; logs show LLM hit-rate and latencies; coverage threshold met.

**Day 9 — CI/CD & Containers**

* Intent: Push-button builds & deploys.
* Tasks: multi-stage Dockerfile; compose with Ollama; GitHub Actions (build, test, scan, push); staging deploy.
* DoD: `docker compose up` runs API + Ollama locally; CI pushes image; staging responds at `/healthz`.

**Day 10 — Docs, Demo & Polishing**

* Intent: Portfolio-grade presentation.
* Tasks: README (badges, architecture diagram, runbook); sample inputs/outputs; demo script; CHANGELOG; roadmap.
* DoD: A reviewer can clone, run, and test hybrid mode in <30 minutes.

---

## 14) Risks & Mitigations

* **Latency creep** (LLM): keep model small, constrain gray-zone to 10–20%, set tight timeouts, cache prompts.
* **Explainability drift**: lock SHAP explainer to model version; store seeds.
* **Config sprawl**: single `settings.py`; `.env.example`; pre-flight config check.
* **Security leakage**: never include secrets in logs/prompts; validate inputs strictly.

---

## 15) Rollout Strategy

1. **Baseline**: LLM disabled; explanations via template only.
2. **Shadow**: Enable LLM judge but do not flip decisions; log both paths.
3. **Hybrid**: Fuse scores; monitor metrics; feature-flag thresholds.
4. **Tune**: Adjust LOW/HIGH and α to hit precision/latency targets.

---

## 16) Roadmap (post-2.0)

* Content-aware features via sandboxed fetch + embeddings (feature-flagged).
* Model registry & canary deploys.
* Drift alerts with PSI and automated retraining trigger (approval required).
* Lightweight UI dashboard for analyst triage.

---

## 17) Definition of Done (Project)

* Reproducible training & serving with no hardcoded secrets.
* Passing tests (unit + e2e) and CI/CD pipeline green.
* Measurable lift in gray-zone decisions (precision at fixed recall).
* Clear documentation and runnable demo.
