FROM python:3.12-slim-bookworm

WORKDIR /app

# Pin uv to the Python version available in the image to avoid downloading
# another interpreter at runtime.
ENV UV_PYTHON=3.12

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# System dependencies for easyocr, python-magic, crawl4ai, etc.
# Use Tsinghua mirror + retries + fix-missing to tolerate flaky networks.
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends --fix-missing -o Acquire::Retries=3 \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libmagic1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Sync dependencies
RUN uv sync --no-dev --frozen

# Copy source
COPY . .

EXPOSE 5091

CMD ["uv", "run", "main.py"]
