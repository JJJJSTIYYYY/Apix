FROM ubuntu:22.04

ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY

ENV DEBIAN_FRONTEND=noninteractive

# Use Tsinghua mirror for apt to improve connectivity in this environment
RUN sed -i 's/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g; s/security.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y \
    curl \
    git \
    unzip \
    build-essential \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    # libreoffice \
    # libreoffice-writer \
    # libreoffice-calc \
    # libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

RUN node -v && npm -v && python3 --version && pip3 --version

WORKDIR /workspace