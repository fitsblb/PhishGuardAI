FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY requirements-docker.txt .
COPY pyproject.toml Readme.md ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements-docker.txt
COPY data/tld_probs.json ./data/tld_probs.json
COPY configs ./configs
COPY models ./models
EXPOSE 8002
CMD ["uvicorn", "src.model_svc.main:app", "--host", "0.0.0.0", "--port", "8002"]
