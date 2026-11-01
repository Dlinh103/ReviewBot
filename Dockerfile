FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install system dependencies if required (curl, build-essential for any c-ext)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

COPY src/ ./src/
COPY alembic.ini ./
COPY migrations/ ./migrations/

EXPOSE 8000

CMD ["uvicorn", "reviewbot.main:app", "--host", "0.0.0.0", "--port", "8000"]
