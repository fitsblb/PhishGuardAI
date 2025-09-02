FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt
COPY src ./src
EXPOSE 8001
CMD ["uvicorn", "src.feature_svc.main:app", "--host", "0.0.0.0", "--port", "8001"]
