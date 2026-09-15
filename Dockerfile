FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADE_DATA_DIR=/workspace/ade-data \
    ADE_CONFIG=/app/config/runtime.json

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
COPY ade ./ade
COPY config ./config
COPY prompts ./prompts
COPY docs ./docs
COPY runpod_handler.py ./runpod_handler.py

RUN mkdir -p /workspace/ade-data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "ade.api:app", "--host", "0.0.0.0", "--port", "8000"]
