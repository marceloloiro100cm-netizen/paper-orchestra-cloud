# Scriptorium V2: situação dos 27 módulos

<!-- Arquivo gerado por scripts/upstreams.py render a partir de docs/upstreams.json. Não edite à mão. -->

Atualizado em 2026-11-24. Implementados: 0; parciais: 16; não iniciados: 11.

As ondas seguem o plano V2 (0: base segura; 1: leitura escalável; 2: busca e evidência; 3: auditoria científica; 4: pesquisa guiada; 5: ecossistema editorial).

| Módulo | Nome | Prioridade | Onda | Situação | Origens | Próximo passo |
|---|---|---|---|---|---|---|
| M11 | Declaração institucional de uso de IA | P1 | 0 | parcial | R25 (IFRS: Instrução Normativa nº 16/2026 (IA generativa)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Gera rascunho a partir do manifesto. Falta conferir item a item com o Anexo da IN 16/2026 e registrar a aprovação do orientador (M12). |
| M13 | Segurança de documentos e isolamento | P1 | 0 | parcial | R27 (OWASP GenAI Security Project), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Feito: neutralização de delimitadores, remoção de caracteres invisíveis e sinais de instrução embutida. Falta varredura de malware no upload e quarentena. |
| M14 | Proveniência e rastreabilidade de execução | P1 | 0 | parcial | R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Manifesto por execução com versões, hashes e eventos. O motor original não expõe tokens nem prompts por chamada; custos ficam como não medidos. |
| M15 | Orçamento, telemetria e regressão | P1 | 0 | parcial | R28 (OSV-Scanner (Google)), R29 (Dependabot (GitHub)), R40 (OSV-Scanner GitHub Action (workflows reutilizáveis)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Feito: Dependabot, OSV-Scanner e vigia de upstreams. Falta orçamento por etapa e cancelamento de Job pelo navegador. |
| M01 | Parsing estrutural de documentos | P1 | 1 | parcial | R03 (Docling), R04 (Docling-Parse), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Extração estruturada por blocos com PyMuPDF (títulos por tamanho de fonte e estilo DOCX). Falta comparar com Docling (R03) no corpus de 30 PDFs e extrair tabelas. |
| M02 | Evidência visual por página e coordenadas | P1 | 1 | parcial | R04 (Docling-Parse), R07 (LangExtract (Google)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Cada bloco e trecho guarda página e bbox normalizada; DOCX/TXT ficam sem coordenadas. Falta o visualizador que abre o PDF na área do trecho. |
| M03 | Fragmentação e indexação persistente | P1 | 1 | parcial | R05 (FAISS (Meta)), R06 (SQLite FTS5), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Trechos com cache privado por SHA-256 + versões no GCS; índice FTS5 montado por execução. Falta índice vetorial (FAISS, R05) e índice persistente por conta. |
| M19 | Granularidade inteligente de fragmentos | P2 | 1 | parcial | R03 (Docling), R04 (Docling-Parse), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Política section-paragraph-1 (seção/parágrafo, ~1200 caracteres, heading_path). Falta benchmark em pt-BR contra janelas móveis. |
| M23 | OCR seletivo e documentos complexos | P2 | 1 | parcial | R18 (olmOCR (AI2)), R03 (Docling), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Detecção de páginas digitalizadas, vazias ou com texto quebrado, registrada no manifesto. Falta executar OCR (olmOCR R18 ou alternativa) só nessas páginas. |
| M04 | Recuperação híbrida BM25 + vetores | P1 | 2 | parcial | R05 (FAISS (Meta)), R06 (SQLite FTS5), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Parte lexical (BM25, FTS5) com rodízio entre fontes, atrás da flag SCRIPTORIUM_V2_RETRIEVAL. Falta parte vetorial e fusão RRF, que dependem da política de embeddings. |
| M05 | Citações por ponteiros resolvidos | P1 | 2 | não iniciado | R12 (Estudo MIT: citações por ponteiros), R07 (LangExtract (Google)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Depende do M02 e do M04. |
| M08 | Matriz de Evidências e proveniência | P1 | 2 | não iniciado | R07 (LangExtract (Google)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Depende de chunks com localizador (M02). |
| M10 | Abstenção quando há evidência insuficiente | P1 | 2 | não iniciado | R01 (Projeto Scriptorium (paper-orchestra-cloud)), R12 (Estudo MIT: citações por ponteiros) | Depende de recuperação com scores (M04). |
| M20 | Reranking especializado | P2 | 2 | não iniciado | R16 (InRanker (UNICAMP)), R17 (FlagEmbedding (BAAI)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Benchmark cego em corpus de educação pt-BR. |
| M06 | Escudo de auditoria científica em camadas | P1 | 3 | parcial | R07 (LangExtract (Google)), R08 (Crossref REST API), R09 (OpenAlex API), R10 (Semantic Scholar API), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | A V1 já faz auditoria heurística e conferência de metadados; os estágios de ponteiro e suporte semântico dependem do M05. |
| M07 | Detecção de retratações e atualizações editoriais | P1 | 3 | parcial | R11 (Retraction Watch via Crossref), R08 (Crossref REST API), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Implementado via Crossref REST (inclui Retraction Watch). Falta sincronizar o CSV completo e reavaliar ao reabrir um manuscrito. |
| M17 | Detecção de contradições entre estudos | P2 | 3 | não iniciado | R07 (LangExtract (Google)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Depende do M08. |
| M18 | Confiabilidade contextual das fontes | P2 | 3 | não iniciado | R15 (RA-RAG (POSTECH)), R08 (Crossref REST API), R09 (OpenAlex API), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Pode reaproveitar o status editorial do M07. |
| M24 | Metadados brasileiros: SciELO e BRAPCI | P2 | 3 | não iniciado | R19 (SciELO), R20 (BRAPCI), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Confirmar se há API oficial da SciELO e os termos da BRAPCI antes de codificar. |
| M09 | Mapa de omissões e cobertura | P1 | 4 | parcial | R13 (GapView (UC Irvine)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | retrieval_coverage.json registra, por fonte, trechos totais, encontrados e selecionados. Falta painel na interface. |
| M12 | Checkpoints de validação humana | P1 | 4 | não iniciado | R01 (Projeto Scriptorium (paper-orchestra-cloud)), R25 (IFRS: Instrução Normativa nº 16/2026 (IA generativa)) | Exige dividir o motor original em etapas retomáveis. |
| M16 | GapView: diagnóstico pré-pesquisa | P2 | 4 | não iniciado | R13 (GapView (UC Irvine)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Depende do M09. |
| M21 | Fichamentos persistentes e cache | P2 | 4 | parcial | R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Primeira camada (parsing e trechos por SHA-256 + versões) implementada. Falta cache de fichamentos por modelo e política. |
| M22 | FIRE: auditoria iterativa e parada dinâmica | P2 | 4 | não iniciado | R14 (FIRE (MBZUAI)), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Conferir licença do R14 antes de qualquer cópia. |
| M25 | Revisão adversarial de argumentos | P2 | 4 | parcial | R01 (Projeto Scriptorium (paper-orchestra-cloud)), R07 (LangExtract (Google)) | A revisão crítica opcional da V1 existe; falta acesso restrito à matriz de evidências (M08). |
| M26 | Importação Zotero somente leitura | P2 | 5 | não iniciado | R21 (Zotero Web API v3), R22 (Better BibTeX for Zotero), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Hoje a biblioteca já aceita .bib e .ris exportados do Zotero. |
| M27 | Exportação bibliográfica e estilos | P2 | 5 | parcial | R23 (Citation.js), R24 (CSL Styles), R38 (abnTeX2), R01 (Projeto Scriptorium (paper-orchestra-cloud)) | Templates ABNT (abnTeX2) existem; falta exportação CSL e testes de estilo. |

## Arquivos por módulo

- **M01:** `worker/structured_extract.py`
- **M02:** `worker/structured_extract.py`, `worker/chunking.py`
- **M03:** `worker/chunking.py`, `worker/lexical_index.py`, `worker/source_materials.py`
- **M04:** `worker/lexical_index.py`, `worker/retrieval_context.py`
- **M06:** `worker/scientific_audit.py`, `worker/reference_verification.py`
- **M07:** `worker/editorial_status.py`, `worker/reference_verification.py`
- **M09:** `worker/retrieval_context.py`
- **M11:** `worker/ai_declaration.py`
- **M13:** `worker/document_guard.py`, `worker/source_materials.py`, `api/library.py`
- **M14:** `worker/run_manifest.py`
- **M15:** `.github/dependabot.yml`, `.github/workflows/osv-scanner-pr.yml`, `.github/workflows/osv-scanner-scheduled.yml`, `.github/workflows/watch-upstreams.yml`, `scripts/upstreams.py`
- **M19:** `worker/chunking.py`
- **M21:** `worker/source_materials.py`, `worker/runner.py`
- **M23:** `worker/ocr_router.py`
- **M25:** `worker/neon_review.py`
- **M27:** `worker/templates/abnt-artigo`, `worker/templates/abnt-dissertacao`
