FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends procps && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY watchdog.py .
COPY config.yaml .

# Non-root user with docker socket access (GID 999 on host)
RUN groupadd -g 999 docker && \
    useradd -r -s /bin/false -G docker watchdog && \
    chown -R watchdog:watchdog /app

USER watchdog

ENTRYPOINT ["python", "watchdog.py"]
