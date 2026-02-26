FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps (keep minimal for now)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==1.8.3"

# Copy only dependency files first (better caching)
COPY pyproject.toml poetry.lock* /app/

# Install deps (no virtualenv inside container)
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

# Copy app code
COPY . /app
