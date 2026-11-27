FROM python:3.11-slim
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates gcc g++ libgl1 libglib2.0-0 \
    texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-bibtex-extra texlive-fonts-recommended \
    texlive-publishers texlive-lang-portuguese lmodern biber \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Revisão auditada do projeto original. Atualizar somente após testes.
# Origem: R02 em docs/upstreams.json (o teste do registro confere este commit).
ARG PAPER_ORCHESTRA_COMMIT=d9bae997e793a015ed38bb1605be9eb58c00284f
# Exposto ao runner para o manifesto de proveniência (M14).
ENV PAPER_ORCHESTRA_COMMIT=${PAPER_ORCHESTRA_COMMIT}
RUN git clone https://github.com/google-research/paper-orchestra.git /app/orchestra \
    && cd /app/orchestra && git checkout "$PAPER_ORCHESTRA_COMMIT"
RUN pip install --no-cache-dir -r /app/orchestra/requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY templates/abnt-artigo/ /app/orchestra/templates/abnt-artigo/
COPY templates/abnt-dissertacao/ /app/orchestra/templates/abnt-dissertacao/
# O build falha se a classe brasileira ou os modelos não compilarem.
RUN kpsewhich abntex2.cls && kpsewhich abntex2cite.sty && \
    for name in abnt-artigo abnt-dissertacao; do \
      (cd "/app/orchestra/templates/$name" && \
       pdflatex -interaction=nonstopmode -halt-on-error template.tex >/tmp/abnt-smoke.log 2>&1) \
       || (cat /tmp/abnt-smoke.log && exit 1); \
    done

# Todos os módulos do worker (tests/test_container_modules.py confere os imports).
COPY *.py /app/
# Normas de formatação (pasta formatos/ na raiz do repositório, copiada para cá pelo deploy).
COPY formatos/ /app/formatos/
# O build falha se alguma norma não compilar um exemplo com citações resolvidas (inclui APA 7 com biber).
RUN cd /app && python format_smoke.py
# Corpus de referência (gate G2): cópia de docs/corpus, conferida por tests/test_retrieval_eval.py.
COPY corpus_ref/ /app/corpus_ref/
CMD ["python", "/app/runner.py"]
