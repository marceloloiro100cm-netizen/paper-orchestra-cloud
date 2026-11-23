# PaperOrchestra — etapas 1 a 3 (23/11/2026)

## 1. Auditoria científica

- Auditoria já integrada ao Cloud Run Job: gera `scientific_audit.json` **apenas em trabalhos novos**.
- Revisão offline do PDF demonstrativo de 6 páginas, informado pelo usuário: foram identificados 9 percentuais em texto extraído e múltiplas referências a mecanismos de verificação. Isso não é teste de precisão e não permite afirmar que todos os percentuais são falsos.
- Em um arquivo sem experimentos relatados, percentuais de desempenho precisam de origem empírica explícita; a auditoria sinaliza, mas **não altera automaticamente** o texto.
- Para homologar a redação em `pt-BR` de ponta a ponta é necessário executar **nova geração** (chamadas Gemini/Cloud Run podem gerar cobranças), pois a preferência de idioma é uma instrução ao modelo e não garante todos os trechos em português.

## 2. Conferência bibliográfica externa

- Consulta Crossref, OpenAlex e Semantic Scholar para os primeiros **20** registros `@article/@book/etc` identificados em `references.bib`.
- Por referência, usa DOI quando disponível ou pesquisa por título. Relatório privado `reference_verification.json`, com `metadata_match`, `possible_match`, `metadata_conflict`, `not_found`, `inconclusive` ou `insufficient_metadata`.
- **Metadados compatíveis não comprovam que a publicação existe em texto integral, nem que sustenta a frase citada.** Não reescreve bibliografia, não altera o artigo nem produz score científico.
- Sem chave, tenta acesso público; limites/HTTP 429 são tratados como `inconclusive` em vez de denunciar obra inexistente. Chaves opcionais: `SEMANTIC_SCHOLAR_API_KEY` e `OPENALEX_API_KEY` somente em variáveis do worker/Secret Manager (nunca GitHub). Crossref não requer chave; uso responsável: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- API OpenAlex: https://help.openalex.org/api/ ; Semantic Scholar: https://api.semanticscholar.org/api-docs/
- Dados continuam em Cloud Storage privado, com leitura pela API autenticada e restrita ao mesmo UID da pesquisa.
- O botão **Conferir referências** é exibido apenas em gerações novas cujo relatório foi criado.

## 3. Templates acadêmicos brasileiros experimentais

- `abnt-artigo` e `abnt-dissertacao`: arquivos `template.tex` e `guidelines.md` baseados na classe LaTeX aberta **abnTeX2**; incluídos na imagem do worker com TeX Live (`texlive-publishers` e `texlive-lang-portuguese`).
- O Dockerfile executa `pdflatex` em ambos os templates na construção da imagem. Build sem sucesso impede publicar o novo motor.
- O motor original foi desenvolvido para **artigos**; a opção dissertação produz apenas uma **estrutura inicial experimental**, não uma dissertação terminada.
- O abnTeX2 inclui estilos que podem refletir versões anteriores; conferir normas recentes de trabalhos acadêmicos (NBR 14724:2024), citações (NBR 10520:2023), referências (NBR 6023:2025) e a norma de artigos NBR 6022, além do **manual do programa de pós-graduação**. Referência: https://www.abntex.net.br/ e orientações institucionais da universidade.
- Não foi recebida a identificação do programa nem o modelo institucional. A aplicação **não promete conformidade automática às normas ABNT atuais**, e dados de autoria/capa são placeholders para preenchimento humano.

## O que foi testado

- Testes de progresso dos agentes, de sinalização heurística e de integração bibliográfica com respostas simuladas (sem rede/chaves/API paga);
- Verificação do esqueleto dos templates na CI; compilação LaTeX prevista no Docker build;
- Primeiro PDF analisado offline apenas quanto aos sinais verificáveis do texto.

## Pendências de homologação após publicação

1. Nova geração em português, com `abnt-artigo`, sem gráficos, usando Gemini Flash. Isso consome recursos e pode falhar por limitação do modelo; não repetir automaticamente.
2. Verificar se ambos os arquivos JSON são gerados, se o relatório bibliográfico mostra fontes acessíveis e se o PDF real compila.
3. Confrontar o arquivo com as instruções do seu programa e corrigir o template para o padrão institucional antes de submeter uma dissertação.
4. Opcionalmente solicitar chaves de API dedicadas e configurá-las no Secret Manager para reduzir rate limiting.

**Dados anteriores preservados:** o deploy apenas atualiza imagens, frontend e versão de código; não altera ou apaga pesquisas armazenadas.
