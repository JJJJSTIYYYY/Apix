FROM ubuntu:22.04

ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

RUN node -v && npm -v && python3 --version && pip3 --version

WORKDIR /workspace