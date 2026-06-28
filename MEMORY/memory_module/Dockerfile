FROM python:3.12-slim-bookworm

WORKDIR /app

# Pin uv to the Python version available in the image.
ENV UV_PYTHON=3.12

# Install system dependencies (curl for healthcheck)
RUN apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends --fix-missing -o Acquire::Retries=3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Sync dependencies
RUN uv sync --no-dev --frozen

# Copy source
COPY . .

EXPOSE 5093

CMD ["uv", "run", "main.py"]
