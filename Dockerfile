FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

WORKDIR /app
COPY . .


# The API only enqueues jobs onto Redis, it never imports onecrawler or
# launches a browser — so it doesn't need the onecrawler package at all.
FROM base AS api

RUN pip install --no-cache-dir .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


# Worker actually drives onecrawler + Playwright, so it needs both the
# published PyPI package and the Chromium browser binaries.
FROM base AS worker

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir .[worker]
RUN playwright install chromium --with-deps

CMD ["arq", "src.worker.settings.WorkerSettings"]
