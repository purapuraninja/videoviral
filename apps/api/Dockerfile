FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the VVF packages (src layout) by copying them and installing editable.
COPY packages/contracts /app/packages/contracts
COPY packages/database /app/packages/database
COPY packages/shared /app/packages/shared
COPY integrations/wigolo /app/integrations/wigolo
COPY integrations/money-printer-turbo /app/integrations/money-printer-turbo
COPY apps/api /app/apps/api

RUN pip install --no-cache-dir \
    ./packages/contracts ./packages/shared ./packages/database \
    ./integrations/wigolo ./integrations/money-printer-turbo \
    ./apps/api

EXPOSE 8000
CMD ["uvicorn", "vvf_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
