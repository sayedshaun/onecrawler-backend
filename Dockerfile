FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

WORKDIR /app
COPY . .


# The API never imports onecrawler or launches a browser (that's the
# worker's job) but does drive the agent (LangGraph + deepagents) in-process,
# so its own dependencies cover that.
FROM base AS api

RUN pip install --no-cache-dir .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


# Worker actually drives onecrawler + Playwright, so it needs both the
# package (currently installed from source, see the `worker` extra in
# pyproject.toml) and the Chromium browser binaries.
FROM base AS worker

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir .[worker]
RUN playwright install chromium --with-deps

CMD ["arq", "src.worker.settings.WorkerSettings"]
