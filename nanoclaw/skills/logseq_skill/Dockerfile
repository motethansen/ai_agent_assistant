FROM python:3.11-slim

WORKDIR /app

COPY logseq_agent.py logseq_later_agent.py config_utils.py skill_runner.py ./

RUN pip install --no-cache-dir

ENV LOGSEQ_DIR=/logseq

ENTRYPOINT ["python", "skill_runner.py"]
