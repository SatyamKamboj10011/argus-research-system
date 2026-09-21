# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies are copied and installed first so the layer caches across code edits.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY argus/ ./argus/
COPY api.py agents.py pipeline.py tools.py ./

# Run as a non-root user.
RUN useradd --create-home --uid 10001 argus && chown -R argus:argus /app
USER argus

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/', timeout=4).status==200 else 1)"

CMD ["sh", "-c", "uvicorn argus.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
