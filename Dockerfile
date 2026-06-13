FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    gettext \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project

COPY . .

RUN uv run python manage.py collectstatic --noinput --settings=ubpm.settings.prod || true

EXPOSE 8000

CMD ["sh", "-c", \
     "uv run python manage.py migrate --noinput --settings=ubpm.settings.prod && \
      uv run python manage.py ensure_admin --settings=ubpm.settings.prod && \
      uv run gunicorn ubpm.wsgi:application \
        --bind 0.0.0.0:8000 --workers 3 \
        --access-logfile - --error-logfile -"]
