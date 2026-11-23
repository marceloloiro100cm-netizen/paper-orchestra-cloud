FROM python:3.11-slim
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates gcc g++ libgl1 libglib2.0-0 \
    texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-bibtex-extra texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Revisão auditada do projeto original. Atualizar somente após testes.
ARG PAPER_ORCHESTRA_COMMIT=d9bae997e793a015ed38bb1605be9eb58c00284f
RUN git clone https://github.com/google-research/paper-orchestra.git /app/orchestra \
    && cd /app/orchestra && git checkout "$PAPER_ORCHESTRA_COMMIT"
RUN pip install --no-cache-dir -r /app/orchestra/requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY agent_progress.py /app/agent_progress.py
COPY scientific_audit.py /app/scientific_audit.py
COPY runner.py /app/runner.py
CMD ["python", "/app/runner.py"]
