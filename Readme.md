## 🚀 Runbook: Local Dev & Demo

This project runs fully **locally** with a URL-only model and a judge that’s either a **deterministic stub** (default) or an **LLM via Ollama** (optional). Follow these steps in order.

### 0) Prereqs
- Python 3.11 in a virtual env (conda or venv)
- Editable install:
  ```bash
  pip install -U pip
  pip install -e ".[dev]"
