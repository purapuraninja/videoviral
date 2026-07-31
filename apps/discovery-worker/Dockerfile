FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY packages/contracts /app/packages/contracts
COPY packages/database /app/packages/database
COPY packages/shared /app/packages/shared
COPY integrations/wigolo /app/integrations/wigolo
COPY apps/discovery-worker /app/apps/discovery-worker

RUN pip install --no-cache-dir \
    ./packages/contracts ./packages/shared ./packages/database \
    ./integrations/wigolo ./apps/discovery-worker

CMD ["python", "-m", "vvf_discovery_worker.main"]
