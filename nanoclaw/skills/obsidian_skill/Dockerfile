FROM python:3.11-slim

WORKDIR /app

# Copy only what the skill needs — no full project, no credentials
COPY obsidian_agent.py config_utils.py skill_runner.py ./

RUN pip install --no-cache-dir rich

# Vault is always mounted at /vault at runtime via --volume flag
ENV WORKSPACE_DIR=/vault

ENTRYPOINT ["python", "skill_runner.py"]
