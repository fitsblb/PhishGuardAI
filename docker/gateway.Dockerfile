FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt
COPY src ./src
EXPOSE 8080
CMD ["uvicorn", "src.gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]
