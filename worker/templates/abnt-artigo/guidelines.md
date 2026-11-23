# Artigo científico brasileiro — abnTeX2 (versão experimental)

Use a classe `abntex2` em modo artigo, com título, autoria provisória, resumo em português e seções: Introdução, Referencial teórico, Metodologia, Resultados e discussão, Considerações finais.

**Não declare conformidade automática às normas ABNT nem aos manuais institucionais.** A classe abnTeX2 é referência útil de LaTeX brasileiro, mas versões vigentes e exigências locais precisam ser verificadas; são especialmente relevantes NBR 6022 (artigos), NBR 10520:2023 (citações) e NBR 6023:2025 (referências).

Preserve o preâmbulo e `\bibliography{references}`. Use chaves de citações produzidas pelo agente de revisão bibliográfica. O motor recebe citações em `\citep{chave}` ou `\citet{chave}` (aliases são fornecidos no template) e deve priorizar autoria, datas e títulos reais. Se o registro experimental não contiver resultados, NÃO crie tabelas ou percentuais falsos.

O modelo é apenas um **rascunho** para revisão e adaptação. Não é um template oficial da universidade nem de uma revista.
