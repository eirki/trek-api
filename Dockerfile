
FROM python:3.9-slim-buster

COPY requirements.txt /tmp/

RUN useradd --create-home appuser
WORKDIR /home/appuser
USER appuser

RUN python -m venv venv && venv/bin/pip install --upgrade pip && venv/bin/pip install -r /tmp/requirements.txt

COPY trek ./trek
COPY sql ./sql
COPY frontend ./frontend
