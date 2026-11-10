FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

WORKDIR /app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY app ./app
COPY tests ./tests

RUN pip install --no-cache-dir ".[dev]"

RUN chown -R app:app /app
USER app

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.wsgi:app"]
