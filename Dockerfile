FROM python:3.14.8-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

EXPOSE 8080

# Railway PORT;
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
