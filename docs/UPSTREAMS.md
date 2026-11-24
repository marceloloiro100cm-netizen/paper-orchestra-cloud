# Registro de upstreams (origens externas)

<!-- Arquivo gerado por scripts/upstreams.py render a partir de docs/upstreams.json. Não edite à mão. -->

Atualizado em 2026-11-24. Documento de origem: Scriptorium V2: Plano técnico de implantação e manutenção, 27 módulos P1/P2, revisão 1.0 de 24/11/2026.

- Fonte única de rastreabilidade. docs/UPSTREAMS.md e docs/V2-MODULOS.md são gerados a partir deste arquivo por scripts/upstreams.py render.
- IDs R01 a R29 seguem o plano V2. R30 em diante são dependências que o projeto já usava antes do plano.
- license_status 'a conferir' bloqueia copiar ou distribuir código até conferir o LICENSE do commit adotado, as dependências transitivas e, quando houver, os pesos dos modelos.
- O workflow 'Vigiar upstreams' consulta GitHub, PyPI e npm toda semana e abre ou atualiza a issue de rastreio.

## Resumo

| ID | Componente | Tipo | Em uso | Licença | Versão fixada | Módulos |
|---|---|---|---|---|---|---|
| R01 | [Projeto Scriptorium (paper-orchestra-cloud)](https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud) | codigo_proprio | sim | a definir | - | V1, M01-M27 |
| R02 | [PaperOrchestra original (Google Research)](https://github.com/google-research/paper-orchestra) | biblioteca | sim | Apache-2.0 | d9bae997e793a015ed38bb1605be9eb58c00284f | V1, M25 |
| R03 | [Docling](https://github.com/docling-project/docling) | biblioteca | não | MIT | - | M01, M19, M23 |
| R04 | [Docling-Parse](https://github.com/docling-project/docling-parse) | biblioteca | não | MIT | - | M01, M02, M19 |
| R05 | [FAISS (Meta)](https://github.com/facebookresearch/faiss) | biblioteca | não | MIT | - | M03, M04 |
| R06 | [SQLite FTS5](https://www.sqlite.org/fts5.html) | biblioteca | sim | blessing | - | M03, M04 |
| R07 | [LangExtract (Google)](https://github.com/google/langextract) | biblioteca | não | Apache-2.0 | - | M02, M05, M06, M08, M17, M25 |
| R08 | [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/) | api | sim | termos do serviço | - | V1, M06, M07, M18 |
| R09 | [OpenAlex API](https://docs.openalex.org/) | api | sim | termos do serviço | - | V1, M06, M18 |
| R10 | [Semantic Scholar API](https://www.semanticscholar.org/product/api) | api | sim | termos do serviço | - | V1, M06 |
| R11 | [Retraction Watch via Crossref](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/) | api | sim | termos do serviço | - | M07 |
| R12 | [Estudo MIT: citações por ponteiros](https://dspace.mit.edu/entities/publication/2994e161-6c34-4f88-973e-c13d1e8cd2ef) | artigo | não | não se aplica | - | M05, M10 |
| R13 | [GapView (UC Irvine)](https://escholarship.org/uc/item/2zs4w991) | artigo | não | não se aplica | - | M09, M16 |
| R14 | [FIRE (MBZUAI)](https://github.com/mbzuai-nlp/fire) | prototipo | não | a conferir | - | M22 |
| R15 | [RA-RAG (POSTECH)](https://github.com/ml-postech/RA-RAG) | prototipo | não | MIT | - | M18 |
| R16 | [InRanker (UNICAMP)](https://github.com/unicamp-dl/InRanker) | prototipo | não | Apache-2.0 | - | M20 |
| R17 | [FlagEmbedding (BAAI)](https://github.com/FlagOpen/FlagEmbedding) | biblioteca | não | MIT | - | M20 |
| R18 | [olmOCR (AI2)](https://github.com/allenai/olmocr) | biblioteca | não | Apache-2.0 | - | M23 |
| R19 | [SciELO](https://www.scielo.org/) | api | não | políticas próprias | - | M24 |
| R20 | [BRAPCI](https://brapci.inf.br/) | api | não | a conferir | - | M24 |
| R21 | [Zotero Web API v3](https://www.zotero.org/support/dev/web_api/v3/start) | api | não | termos do serviço | - | M26 |
| R22 | [Better BibTeX for Zotero](https://github.com/retorquere/zotero-better-bibtex) | biblioteca | não | MIT | - | M26 |
| R23 | [Citation.js](https://github.com/citation-js/citation-js) | biblioteca | não | MIT | - | M27 |
| R24 | [CSL Styles](https://github.com/citation-style-language/styles) | biblioteca | não | CC-BY-SA-3.0 | - | M27 |
| R25 | [IFRS: Instrução Normativa nº 16/2026 (IA generativa)](https://ifrs.edu.br/documentos/instrucao-normativa-ifrs-n-16-2026/) | normativo | sim | não se aplica | - | M11, M12 |
| R26 | [PRISMA 2020](https://www.prisma-statement.org/prisma-2020-checklist) | normativo | não | não se aplica | - | M09, M16 |
| R27 | [OWASP GenAI Security Project](https://genai.owasp.org/) | normativo | sim | não se aplica | - | M13 |
| R28 | [OSV-Scanner (Google)](https://github.com/google/osv-scanner) | ferramenta | sim | Apache-2.0 | - | M15 |
| R29 | [Dependabot (GitHub)](https://docs.github.com/en/code-security/dependabot) | servico | sim | termos do serviço | - | M15 |
| R30 | [FastAPI](https://github.com/fastapi/fastapi) | biblioteca | sim | MIT | >=0.115,<1 | V1 |
| R31 | [Uvicorn](https://github.com/Kludex/uvicorn) | biblioteca | sim | BSD-3-Clause | >=0.30,<1 | V1 |
| R32 | [Pydantic](https://github.com/pydantic/pydantic) | biblioteca | sim | MIT | >=2.5,<3 | V1 |
| R33 | [Firebase Admin SDK para Python](https://github.com/firebase/firebase-admin-python) | biblioteca | sim | Apache-2.0 | >=6.5,<8 | V1 |
| R34 | [Google Cloud Client Libraries para Python (Firestore, Storage, Run, Secret Manager)](https://github.com/googleapis/google-cloud-python) | biblioteca | sim | Apache-2.0 | faixas em api/requirements.txt e worker/requirements.txt | V1 |
| R35 | [Google Gen AI SDK para Python (google-genai)](https://github.com/googleapis/python-genai) | biblioteca | sim | Apache-2.0 | >=2.34.0,<3 | V1, M25 |
| R36 | [Requests](https://github.com/psf/requests) | biblioteca | sim | Apache-2.0 | >=2.31,<3 | V1, M07 |
| R37 | [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | biblioteca | sim | AGPL-3.0 | >=2.1,<3 | V1, M01, M02, M23 |
| R38 | [abnTeX2](https://github.com/abntex/abntex2) | biblioteca | sim | LPPL-1.3c | versão do pacote Debian texlive-publishers da imagem python:3.11-slim | V1, M27 |
| R39 | [Firebase JavaScript SDK](https://github.com/firebase/firebase-js-sdk) | biblioteca | sim | Apache-2.0 | 11.10.0 | V1 |
| R40 | [OSV-Scanner GitHub Action (workflows reutilizáveis)](https://github.com/google/osv-scanner-action) | ferramenta | sim | Apache-2.0 | v2.7.1 | M15 |
| R41 | [GitHub Actions usadas nos workflows (actions/checkout, setup-python, setup-node; google-github-actions/auth, setup-gcloud)](https://github.com/google-github-actions/auth) | ferramenta | sim | Apache-2.0 | checkout@v4, setup-python@v5, setup-node@v4, auth@v3, setup-gcloud@v3 | V1, M15 |
| R42 | [Imagem base python:3.11-slim (Docker Official Images)](https://hub.docker.com/_/python) | ferramenta | sim | PSF-2.0 | python:3.11-slim (tag móvel, sem digest) | V1 |

## Fichas

### R01 · Projeto Scriptorium (paper-orchestra-cloud)

- **Fonte canônica:** https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud
- **Versões:** https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud/releases
- **Erros e correções:** https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud/issues
- **Avisos de segurança:** https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** a definir
- **Situação da licença:** código próprio; o repositório ainda não tem arquivo LICENSE
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** api/, worker/, public/
- **Política de atualização:** Todo PR: CI verde, revisão e plano de rollback.
- **Frequência de revisão:** por_pr
- **Risco:** Mudanças de schema, custo ou permissão exigem migração reversível.
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R02 · PaperOrchestra original (Google Research)

- **Fonte canônica:** https://github.com/google-research/paper-orchestra
- **Versões:** https://github.com/google-research/paper-orchestra/commits
- **Erros e correções:** https://github.com/google-research/paper-orchestra/issues
- **Avisos de segurança:** https://github.com/google-research/paper-orchestra/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** confirmada no LICENSE do commit fixado (24/11/2026)
- **Licença dos pesos:** -
- **Versão fixada:** d9bae997e793a015ed38bb1605be9eb58c00284f
- **Versão instalada:** d9bae997e793a015ed38bb1605be9eb58c00284f
- **Última versão revisada:** d9bae997e793a015ed38bb1605be9eb58c00284f
- **Onde é usado:** worker/Dockerfile (ARG PAPER_ORCHESTRA_COMMIT), worker/runner.py
- **Política de atualização:** Commit fixado no Dockerfile. Atualizar só por PR, depois de gerar uma pesquisa de teste e comparar PDF, LaTeX e logs.
- **Frequência de revisão:** mensal
- **Risco:** Não publica releases. Seu requirements.txt não fixa versões, então dependências transitivas (PyMuPDF, openai, streamlit etc.) mudam a cada build.
- **Nota de migração:** Os IDs de modelo preview (gemini-3.1-pro-preview, gemini-3-flash-preview) vêm deste código.
- **Resultado de benchmark:** -
- **Rollback:** d9bae997e793a015ed38bb1605be9eb58c00284f
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R03 · Docling

- **Fonte canônica:** https://github.com/docling-project/docling
- **Versões:** https://github.com/docling-project/docling/releases
- **Erros e correções:** https://github.com/docling-project/docling/issues
- **Avisos de segurança:** https://github.com/docling-project/docling/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** MIT
- **Situação da licença:** confirmada no plano V2 (24/11/2026)
- **Licença dos pesos:** a conferir (modelos de layout e tabelas baixados em tempo de execução)
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Release mensal; alerta de segurança imediato; versão fixada no build.
- **Frequência de revisão:** mensal
- **Risco:** Uso alto de CPU e RAM; baixa pesos de modelos durante o build ou a execução.
- **Nota de migração:** Onda 1 usa PyMuPDF (R37) como parser estrutural. Docling entra só depois do corpus de avaliação de 30 PDFs, comparando ordem de leitura, títulos e tabelas.
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R04 · Docling-Parse

- **Fonte canônica:** https://github.com/docling-project/docling-parse
- **Versões:** https://github.com/docling-project/docling-parse/releases
- **Erros e correções:** https://github.com/docling-project/docling-parse/issues
- **Avisos de segurança:** https://github.com/docling-project/docling-parse/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** MIT
- **Situação da licença:** confirmada no plano V2 (24/11/2026)
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Mesma matriz de versões do Docling.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** Onda 1 usa PyMuPDF (R37) como parser estrutural. Docling entra só depois do corpus de avaliação de 30 PDFs, comparando ordem de leitura, títulos e tabelas.
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R05 · FAISS (Meta)

- **Fonte canônica:** https://github.com/facebookresearch/faiss
- **Versões:** https://github.com/facebookresearch/faiss/releases
- **Erros e correções:** https://github.com/facebookresearch/faiss/issues
- **Avisos de segurança:** https://github.com/facebookresearch/faiss/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** MIT
- **Situação da licença:** confirmada no plano V2 (24/11/2026)
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Ciclo mensal; mudar a versão dos embeddings força reindexação controlada.
- **Frequência de revisão:** mensal
- **Risco:** Índice serializado no GCS não é banco distribuído; reavaliar para muitos usuários.
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R06 · SQLite FTS5

- **Fonte canônica:** https://www.sqlite.org/fts5.html
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** https://www.sqlite.org/changes.html
- **Licença (SPDX):** blessing
- **Situação da licença:** domínio público (SQLite); validar a distribuição usada no contêiner
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** SQLite embutido no Python da imagem python:3.11-slim (módulo sqlite3)
- **Última versão revisada:** -
- **Onde é usado:** worker/lexical_index.py
- **Política de atualização:** Acompanhar o release log do SQLite e a versão empacotada no Python da imagem.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R07 · LangExtract (Google)

- **Fonte canônica:** https://github.com/google/langextract
- **Versões:** https://github.com/google/langextract/releases
- **Erros e correções:** https://github.com/google/langextract/issues
- **Avisos de segurança:** https://github.com/google/langextract/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** confirmada no plano V2 (24/11/2026)
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Releases e issues mensalmente.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R08 · Crossref REST API

- **Fonte canônica:** https://www.crossref.org/documentation/retrieve-metadata/
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** https://www.crossref.org/categories/rest-api/
- **Licença (SPDX):** termos do serviço
- **Situação da licença:** metadados e serviço com termos próprios
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** worker/reference_verification.py, worker/editorial_status.py
- **Política de atualização:** Mensal e antes de cada release: campos, filtros, cotas e etiqueta (polite pool).
- **Frequência de revisão:** mensal
- **Risco:** Indisponibilidade vira 'inconclusivo', nunca 'inexistente'.
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R09 · OpenAlex API

- **Fonte canônica:** https://docs.openalex.org/
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** termos do serviço
- **Situação da licença:** dados com termos próprios
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** worker/reference_verification.py
- **Política de atualização:** Mensal: documentação, changelog e exigência de chave (OPENALEX_API_KEY).
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R10 · Semantic Scholar API

- **Fonte canônica:** https://www.semanticscholar.org/product/api
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** termos do serviço
- **Situação da licença:** dados com termos próprios
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** worker/reference_verification.py
- **Política de atualização:** Mensal: limites de requisição e campos.
- **Frequência de revisão:** mensal
- **Risco:** Sem chave dedicada, 429 é frequente; tratado como inconclusivo.
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R11 · Retraction Watch via Crossref

- **Fonte canônica:** https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** https://www.crossref.org/blog/retraction-watch-retractions-now-in-the-crossref-api/
- **Licença (SPDX):** termos do serviço
- **Situação da licença:** dados abertos pela Crossref; conferir termos antes de sincronizar o CSV
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** worker/editorial_status.py
- **Política de atualização:** Mensal. O CSV completo (gitlab.com/crossref/retraction-watch-data) ainda não é sincronizado.
- **Frequência de revisão:** mensal
- **Risco:** Ausência de aviso nas bases não prova que a obra nunca foi retratada.
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R12 · Estudo MIT: citações por ponteiros

- **Fonte canônica:** https://dspace.mit.edu/entities/publication/2994e161-6c34-4f88-973e-c13d1e8cd2ef
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** não se aplica
- **Situação da licença:** artigo científico; implementar o princípio com código próprio
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Acompanhar revisões e trabalhos relacionados.
- **Frequência de revisão:** trimestral
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R13 · GapView (UC Irvine)

- **Fonte canônica:** https://escholarship.org/uc/item/2zs4w991
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** não se aplica
- **Situação da licença:** referência de pesquisa
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Revisitar a cada semestre.
- **Frequência de revisão:** semestral
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R14 · FIRE (MBZUAI)

- **Fonte canônica:** https://github.com/mbzuai-nlp/fire
- **Versões:** https://github.com/mbzuai-nlp/fire/commits
- **Erros e correções:** https://github.com/mbzuai-nlp/fire/issues
- **Avisos de segurança:** https://github.com/mbzuai-nlp/fire/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** a conferir
- **Situação da licença:** a conferir
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Trimestral; se copiar código, fixar commit e conferir licença.
- **Frequência de revisão:** trimestral
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R15 · RA-RAG (POSTECH)

- **Fonte canônica:** https://github.com/ml-postech/RA-RAG
- **Versões:** https://github.com/ml-postech/RA-RAG/commits
- **Erros e correções:** https://github.com/ml-postech/RA-RAG/issues
- **Avisos de segurança:** https://github.com/ml-postech/RA-RAG/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** MIT
- **Situação da licença:** confirmada pela API do GitHub (vigia de 24/11/2026)
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Trimestral; não instalar automaticamente.
- **Frequência de revisão:** trimestral
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R16 · InRanker (UNICAMP)

- **Fonte canônica:** https://github.com/unicamp-dl/InRanker
- **Versões:** https://github.com/unicamp-dl/InRanker/commits
- **Erros e correções:** https://github.com/unicamp-dl/InRanker/issues
- **Avisos de segurança:** https://github.com/unicamp-dl/InRanker/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** confirmada pela API do GitHub (vigia de 24/11/2026); pesos a conferir separadamente
- **Licença dos pesos:** a conferir
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Trimestral; repositório e model card.
- **Frequência de revisão:** trimestral
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R17 · FlagEmbedding (BAAI)

- **Fonte canônica:** https://github.com/FlagOpen/FlagEmbedding
- **Versões:** https://github.com/FlagOpen/FlagEmbedding/releases
- **Erros e correções:** https://github.com/FlagOpen/FlagEmbedding/issues
- **Avisos de segurança:** https://github.com/FlagOpen/FlagEmbedding/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** MIT
- **Situação da licença:** código confirmado no plano V2; pesos a conferir
- **Licença dos pesos:** a conferir por modelo
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Mensal: releases e model cards.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R18 · olmOCR (AI2)

- **Fonte canônica:** https://github.com/allenai/olmocr
- **Versões:** https://github.com/allenai/olmocr/releases
- **Erros e correções:** https://github.com/allenai/olmocr/issues
- **Avisos de segurança:** https://github.com/allenai/olmocr/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** código confirmado no plano V2; pesos e endpoint separados
- **Licença dos pesos:** a conferir
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Mensal: releases e modelos.
- **Frequência de revisão:** mensal
- **Risco:** OCR remoto pode transferir dados pessoais; priorizar processamento privado.
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R19 · SciELO

- **Fonte canônica:** https://www.scielo.org/
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** políticas próprias
- **Situação da licença:** metadados com políticas e licenças aplicáveis
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Mensal: termos e endpoints oficiais.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R20 · BRAPCI

- **Fonte canônica:** https://brapci.inf.br/
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** a conferir
- **Situação da licença:** termos e acesso a conferir; não presumir API
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Mensal: site e políticas; sem scraping agressivo.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R21 · Zotero Web API v3

- **Fonte canônica:** https://www.zotero.org/support/dev/web_api/v3/start
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** termos do serviço
- **Situação da licença:** API com autenticação e políticas próprias
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Mensal: documentação e anúncios; credenciais só no Secret Manager.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R22 · Better BibTeX for Zotero

- **Fonte canônica:** https://github.com/retorquere/zotero-better-bibtex
- **Versões:** https://github.com/retorquere/zotero-better-bibtex/releases
- **Erros e correções:** https://github.com/retorquere/zotero-better-bibtex/issues
- **Avisos de segurança:** https://github.com/retorquere/zotero-better-bibtex/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** MIT
- **Situação da licença:** confirmada no plano V2 (24/11/2026)
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Changelog mensal; opção do lado do cliente.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R23 · Citation.js

- **Fonte canônica:** https://github.com/citation-js/citation-js
- **Versões:** https://github.com/citation-js/citation-js/releases
- **Erros e correções:** https://github.com/citation-js/citation-js/issues
- **Avisos de segurança:** https://github.com/citation-js/citation-js/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** MIT
- **Situação da licença:** confirmada pela API do GitHub (vigia de 24/11/2026)
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Mensal: releases e issues.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R24 · CSL Styles

- **Fonte canônica:** https://github.com/citation-style-language/styles
- **Versões:** https://github.com/citation-style-language/styles/commits
- **Erros e correções:** https://github.com/citation-style-language/styles/issues
- **Avisos de segurança:** https://github.com/citation-style-language/styles/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** CC-BY-SA-3.0
- **Situação da licença:** a conferir: licença por estilo
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Commit fixado; novos estilos passam por testes de snapshot.
- **Frequência de revisão:** semestral
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R25 · IFRS: Instrução Normativa nº 16/2026 (IA generativa)

- **Fonte canônica:** https://ifrs.edu.br/documentos/instrucao-normativa-ifrs-n-16-2026/
- **Versões:** https://ifrs.edu.br/wp-content/uploads/2026/05/Anexo-IN-IAGen.pdf
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** não se aplica
- **Situação da licença:** normativa institucional
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** IN 16/2026 de 27/05/2026
- **Última versão revisada:** -
- **Onde é usado:** worker/ai_declaration.py
- **Política de atualização:** Semestral e sempre que a norma ou o anexo mudar; revisão humana do texto da declaração.
- **Frequência de revisão:** semestral
- **Risco:** O texto do Anexo (declaração) ainda não foi conferido item a item; o rascunho gerado não afirma conformidade.
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R26 · PRISMA 2020

- **Fonte canônica:** https://www.prisma-statement.org/prisma-2020-checklist
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** não se aplica
- **Situação da licença:** diretriz de relato científico
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** -
- **Política de atualização:** Semestral.
- **Frequência de revisão:** semestral
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R27 · OWASP GenAI Security Project

- **Fonte canônica:** https://genai.owasp.org/
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** não se aplica
- **Situação da licença:** guia de segurança
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** worker/document_guard.py
- **Política de atualização:** Mensal; CVEs críticos imediatamente.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R28 · OSV-Scanner (Google)

- **Fonte canônica:** https://github.com/google/osv-scanner
- **Versões:** https://github.com/google/osv-scanner/releases
- **Erros e correções:** https://github.com/google/osv-scanner/issues
- **Avisos de segurança:** https://github.com/google/osv-scanner/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** confirmada pela API do GitHub (vigia de 24/11/2026)
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** v2.7.1
- **Onde é usado:** .github/workflows/osv-scanner-pr.yml, .github/workflows/osv-scanner-scheduled.yml
- **Política de atualização:** A versão usada vem do R40 (workflow reutilizável v2.7.1).
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R29 · Dependabot (GitHub)

- **Fonte canônica:** https://docs.github.com/en/code-security/dependabot
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** termos do serviço
- **Situação da licença:** serviço GitHub
- **Licença dos pesos:** -
- **Versão fixada:** -
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** .github/dependabot.yml
- **Política de atualização:** PRs semanais de pip e GitHub Actions.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R30 · FastAPI

- **Fonte canônica:** https://github.com/fastapi/fastapi
- **Versões:** https://github.com/fastapi/fastapi/releases
- **Erros e correções:** https://github.com/fastapi/fastapi/issues
- **Avisos de segurança:** https://github.com/fastapi/fastapi/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** MIT
- **Situação da licença:** a conferir pelo vigia semanal
- **Licença dos pesos:** -
- **Versão fixada:** >=0.115,<1
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** api/requirements.txt
- **Política de atualização:** Dependabot semanal; testes da API antes do merge.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R31 · Uvicorn

- **Fonte canônica:** https://github.com/Kludex/uvicorn
- **Versões:** https://github.com/Kludex/uvicorn/releases
- **Erros e correções:** https://github.com/Kludex/uvicorn/issues
- **Avisos de segurança:** https://github.com/Kludex/uvicorn/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** BSD-3-Clause
- **Situação da licença:** a conferir pelo vigia semanal
- **Licença dos pesos:** -
- **Versão fixada:** >=0.30,<1
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** api/requirements.txt
- **Política de atualização:** Dependabot semanal.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** Repositório movido de encode/uvicorn para Kludex/uvicorn (detectado pelo vigia em 24/11/2026).
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R32 · Pydantic

- **Fonte canônica:** https://github.com/pydantic/pydantic
- **Versões:** https://github.com/pydantic/pydantic/releases
- **Erros e correções:** https://github.com/pydantic/pydantic/issues
- **Avisos de segurança:** https://github.com/pydantic/pydantic/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** MIT
- **Situação da licença:** a conferir pelo vigia semanal
- **Licença dos pesos:** -
- **Versão fixada:** >=2.5,<3
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** api/requirements.txt
- **Política de atualização:** Dependabot semanal.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R33 · Firebase Admin SDK para Python

- **Fonte canônica:** https://github.com/firebase/firebase-admin-python
- **Versões:** https://github.com/firebase/firebase-admin-python/releases
- **Erros e correções:** https://github.com/firebase/firebase-admin-python/issues
- **Avisos de segurança:** https://github.com/firebase/firebase-admin-python/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** a conferir pelo vigia semanal
- **Licença dos pesos:** -
- **Versão fixada:** >=6.5,<8
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** api/requirements.txt, worker/requirements.txt
- **Política de atualização:** Dependabot semanal; revisar mudanças de verificação de token.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R34 · Google Cloud Client Libraries para Python (Firestore, Storage, Run, Secret Manager)

- **Fonte canônica:** https://github.com/googleapis/google-cloud-python
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** a conferir pelo vigia semanal
- **Licença dos pesos:** -
- **Versão fixada:** faixas em api/requirements.txt e worker/requirements.txt
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** api/requirements.txt, worker/requirements.txt
- **Política de atualização:** Dependabot semanal.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R35 · Google Gen AI SDK para Python (google-genai)

- **Fonte canônica:** https://github.com/googleapis/python-genai
- **Versões:** https://github.com/googleapis/python-genai/releases
- **Erros e correções:** https://github.com/googleapis/python-genai/issues
- **Avisos de segurança:** https://github.com/googleapis/python-genai/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** a conferir pelo vigia semanal
- **Licença dos pesos:** -
- **Versão fixada:** >=2.34.0,<3
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** worker/requirements.txt, worker/neon_review.py
- **Política de atualização:** Dependabot semanal; conferir IDs de modelo e preços na documentação oficial.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R36 · Requests

- **Fonte canônica:** https://github.com/psf/requests
- **Versões:** https://github.com/psf/requests/releases
- **Erros e correções:** https://github.com/psf/requests/issues
- **Avisos de segurança:** https://github.com/psf/requests/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** a conferir pelo vigia semanal
- **Licença dos pesos:** -
- **Versão fixada:** >=2.31,<3
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** worker/requirements.txt, worker/reference_verification.py
- **Política de atualização:** Dependabot semanal.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R37 · PyMuPDF

- **Fonte canônica:** https://github.com/pymupdf/PyMuPDF
- **Versões:** https://github.com/pymupdf/PyMuPDF/releases
- **Erros e correções:** https://github.com/pymupdf/PyMuPDF/issues
- **Avisos de segurança:** https://github.com/pymupdf/PyMuPDF/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** AGPL-3.0
- **Situação da licença:** a conferir: licença dupla (AGPL-3.0 ou comercial da Artifex)
- **Licença dos pesos:** -
- **Versão fixada:** >=2.1,<3
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** worker/requirements.txt, worker/structured_extract.py, worker/source_materials.py, worker/scientific_audit.py, worker/neon_review.py
- **Política de atualização:** Faixa fixada em worker/requirements.txt (antes vinha sem versão do PaperOrchestra); Dependabot semanal; testes de extração de PDF no CI.
- **Frequência de revisão:** mensal
- **Risco:** AGPL: o serviço é acessível pela rede. O código do projeto é público, o que ajuda, mas a conformidade precisa ser conferida.
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R38 · abnTeX2

- **Fonte canônica:** https://github.com/abntex/abntex2
- **Versões:** https://github.com/abntex/abntex2/releases
- **Erros e correções:** https://github.com/abntex/abntex2/issues
- **Avisos de segurança:** https://github.com/abntex/abntex2/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** LPPL-1.3c
- **Situação da licença:** a conferir pelo vigia semanal
- **Licença dos pesos:** -
- **Versão fixada:** versão do pacote Debian texlive-publishers da imagem python:3.11-slim
- **Versão instalada:** 1.9.7 (pacote Debian texlive-publishers)
- **Última versão revisada:** 2018-11-24-v1.9.7-ctan
- **Onde é usado:** worker/Dockerfile, worker/templates/abnt-artigo, worker/templates/abnt-dissertacao
- **Política de atualização:** Semestral, junto com a revisão das NBR 6022, 10520 e 6023.
- **Frequência de revisão:** semestral
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R39 · Firebase JavaScript SDK

- **Fonte canônica:** https://github.com/firebase/firebase-js-sdk
- **Versões:** https://github.com/firebase/firebase-js-sdk/releases
- **Erros e correções:** https://github.com/firebase/firebase-js-sdk/issues
- **Avisos de segurança:** https://github.com/firebase/firebase-js-sdk/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** a conferir pelo vigia semanal
- **Licença dos pesos:** -
- **Versão fixada:** 11.10.0
- **Versão instalada:** 11.10.0
- **Última versão revisada:** -
- **Onde é usado:** public/app.js (import do CDN www.gstatic.com/firebasejs/11.10.0)
- **Política de atualização:** Mensal; o Dependabot não cobre imports por URL, então a atualização é manual.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R40 · OSV-Scanner GitHub Action (workflows reutilizáveis)

- **Fonte canônica:** https://github.com/google/osv-scanner-action
- **Versões:** https://github.com/google/osv-scanner-action/releases
- **Erros e correções:** https://github.com/google/osv-scanner-action/issues
- **Avisos de segurança:** https://github.com/google/osv-scanner-action/security/advisories
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** confirmada pela API do GitHub (vigia de 24/11/2026)
- **Licença dos pesos:** -
- **Versão fixada:** v2.7.1
- **Versão instalada:** v2.7.1
- **Última versão revisada:** v2.7.1
- **Onde é usado:** .github/workflows/osv-scanner-pr.yml, .github/workflows/osv-scanner-scheduled.yml
- **Política de atualização:** Dependabot (github-actions) e vigia semanal; versão igual à dos exemplos oficiais.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R41 · GitHub Actions usadas nos workflows (actions/checkout, setup-python, setup-node; google-github-actions/auth, setup-gcloud)

- **Fonte canônica:** https://github.com/google-github-actions/auth
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** -
- **Licença (SPDX):** Apache-2.0
- **Situação da licença:** a conferir
- **Licença dos pesos:** -
- **Versão fixada:** checkout@v4, setup-python@v5, setup-node@v4, auth@v3, setup-gcloud@v3
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** .github/workflows/
- **Política de atualização:** Dependabot (github-actions) semanal.
- **Frequência de revisão:** mensal
- **Risco:** -
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24

### R42 · Imagem base python:3.11-slim (Docker Official Images)

- **Fonte canônica:** https://hub.docker.com/_/python
- **Versões:** -
- **Erros e correções:** -
- **Avisos de segurança:** -
- **Histórico de mudanças:** https://github.com/docker-library/python
- **Licença (SPDX):** PSF-2.0
- **Situação da licença:** Python sob PSF; pacotes Debian com licenças próprias
- **Licença dos pesos:** -
- **Versão fixada:** python:3.11-slim (tag móvel, sem digest)
- **Versão instalada:** -
- **Última versão revisada:** -
- **Onde é usado:** api/Dockerfile, worker/Dockerfile
- **Política de atualização:** Semestral; planejar a troca de Python antes do fim do suporte do 3.11 (outubro de 2027).
- **Frequência de revisão:** semestral
- **Risco:** Tag móvel: cada build pode receber outra versão do Debian e do TeX Live.
- **Nota de migração:** -
- **Resultado de benchmark:** -
- **Rollback:** -
- **Responsável:** marceloloiro100cm-netizen
- **Última checagem:** 2026-11-24
