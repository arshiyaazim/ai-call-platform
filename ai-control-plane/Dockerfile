FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends procps && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ai_devops_brain.py .
COPY system_analyzer.py .
COPY auto_repair_engine.py .
COPY infra_agent.py .
COPY config.yaml .

# Non-root user with docker socket access (GID 999 on host)
RUN groupadd -g 999 docker && \
    useradd -r -s /bin/false -G docker controlplane && \
    mkdir -p /var/log/ai-infra-reports && \
    chown -R controlplane:controlplane /app /var/log/ai-infra-reports

USER controlplane

ENTRYPOINT ["python", "infra_agent.py"]
