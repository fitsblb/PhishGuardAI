# gateway.Dockerfile  (BRANCH: feature/docker-slim-gateway)

# ---- build stage: install runtime deps into a venv ----
FROM python:3.11-slim AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1

# minimal build tools only in builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

# copy metadata & install the project (runtime deps only; no [dev])
COPY pyproject.toml Readme.md ./
# Rename Readme.md to README.md for pyproject.toml compatibility
RUN mv Readme.md README.md
# Copy source code needed for installation
COPY src ./src
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install .

# ---- runtime stage: tiny final image ----
FROM python:3.11-slim
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# copy installed env and only the code/configs needed at runtime
COPY --from=builder /opt/venv /opt/venv
COPY src ./src
COPY configs ./configs

EXPOSE 8000
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
