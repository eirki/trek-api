
FROM python:3.9-slim-buster

RUN apt-get -y update \
    && apt-get install -y --fix-missing --no-install-recommends \
    curl \
    fontconfig && \
    curl -L  https://github.com/casey/just/releases/download/0.10.5/just-0.10.5-x86_64-unknown-linux-musl.tar.gz > just.tar.gz && \
    tar -xf just.tar.gz  -C /usr/local/bin && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/

RUN useradd --create-home appuser
WORKDIR /home/appuser
USER appuser

RUN python -m venv .venv

COPY requirements.txt ./requirements.txt
RUN .venv/bin/pip install -r ./requirements.txt

COPY trek ./trek
COPY justfile ./justfile
