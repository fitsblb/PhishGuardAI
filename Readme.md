## 🚀 Runbook: Local Dev & Demo

This project runs fully **locally** with a URL-only model and a judge that’s either a **deterministic stub** (default) or an **LLM via Ollama** (optional). Follow these steps in order.

### 0) Prereqs
- Python 3.11 in a virtual env (conda or venv)
- Editable install:
  ```bash
  pip install -U pip
  pip install -e ".[dev]"
  ```

## 🐳 Docker Quick Start

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
