# Formatos e normas do Scriptorium

Esta pasta é o único lugar onde as normas de formatação moram. A API, o worker (PDF), a exportação
para Word e o site leem tudo daqui. Para oferecer uma norma nova (Vancouver, Chicago, IEEE, a norma de
uma revista), crie uma subpasta: nenhum código precisa mudar.

## O que já existe

| Pasta | Família | Tipos de trabalho | Citação | Referências no PDF |
|---|---|---|---|---|
| `abnt-artigo/` | ABNT | artigo, revisão sistemática | (SILVA; SOUZA, 2020) | abntex2cite + BibTeX |
| `abnt-dissertacao/` | ABNT | dissertação | (SILVA; SOUZA, 2020) | abntex2cite + BibTeX |
| `abnt-tcc/` | ABNT | TCC | (SILVA; SOUZA, 2020) | abntex2cite + BibTeX (usa o preâmbulo da dissertação) |
| `apa7/` | APA 7 | artigo, revisão sistemática | (Silva & Souza, 2020) | biblatex-apa + biber |
| `artigo-simples/` | Artigo simples | todos (só pela IA, fora do site) | (Silva and Souza, 2020) | natbib + BibTeX |

No site, a pessoa escolhe o **tipo de trabalho** e a **norma** (a família). O Scriptorium pega a pasta da
família que atende aquele tipo: ABNT + dissertação vira `abnt-dissertacao`, por exemplo.

## Arquivos de cada pasta

- `formato.json` (obrigatório): descrição e regras de montagem, detalhadas abaixo.
- `preambulo.tex` (obrigatório, pode ser compartilhado): o LaTeX antes do corpo, terminando em
  `\begin{document}` e na capa. Campos `%(title)s`, `%(author)s`, `%(date)s`, `%(babel)s` e
  `%(work_type)s` são preenchidos pelo Scriptorium; os de `latex.textos` também. Outros `%` são
  comentários LaTeX normais.
- `regras.md` (opcional): resumo da norma que a IA recebe em cada etapa (citação, estrutura, estilo).
- arquivo `.csl` (opcional): estilo CSL oficial, para Zotero, Mendeley e Word. O site oferece o download.

## Campos do `formato.json`

| Campo | Para que serve |
|---|---|
| `id` | Igual ao nome da pasta (minúsculas e hífens). Fica gravado no projeto. |
| `nome`, `descricao` | Texto mostrado no site e entregue à IA. |
| `familia` | Nome da norma no seletor do site (ABNT, APA 7...). Pastas da mesma família se completam por tipo. |
| `status` | `estavel` ou `experimental` (o site mostra o aviso). |
| `tipos` | Quais de `artigo`, `dissertacao`, `tcc`, `revisao_sistematica` a pasta atende. |
| `no_site` | `false` esconde do seletor do site (continua disponível pela IA). |
| `areas` | Áreas que costumam usar a norma; aparece como dica no site. |
| `estrutura.secoes` | Seções ou capítulos que a IA deve escrever, em ordem. |
| `estrutura.resumo` | Ambiente LaTeX do resumo (`resumo`, `abstract`). |
| `estrutura.usa_capitulos` | `true` transforma `\section` em `\chapter` e gera sumário. |
| `citacao.parentetica`, `citacao.narrativa` | Comandos que a IA deve usar para citar. |
| `citacao.exemplos` | Como a citação aparece no texto (site, Word e IA). |
| `latex.preambulo` | Caminho a partir desta pasta (`apa7/preambulo.tex`). |
| `latex.bibliografia` | `bibtex` ou `biber` (motor que o worker roda entre os pdflatex). |
| `latex.apos_resumo` | LaTeX inserido logo depois do fim do resumo (ex.: `\textual` no abnTeX2). |
| `latex.fecho` | LaTeX antes de `\end{document}`: onde entram as referências. |
| `latex.tipo_trabalho`, `latex.textos` | Rótulos da capa; `textos` aceita um bloco por idioma (`pt-BR`, `en`). |
| `word` | Exportação .docx: `referencias` (`abnt` ou `apa7`), `espacamento`, `margens_cm`, `recuo_cm`, `fonte`, `tamanho_pt`. |
| `origem` | De onde veio cada arquivo de terceiros: repositório, commit, licença e o ID em `docs/upstreams.json`. |

## Como adicionar uma norma

1. Copie a pasta mais parecida (`apa7/` para autor-data com biblatex, `abnt-artigo/` para abnTeX2) com o novo `id`.
2. Ajuste `formato.json`, o preâmbulo e `regras.md`.
3. Se usar arquivo de terceiros (um `.csl`, um estilo biblatex), registre em `origem` e em
   `docs/upstreams.json`, e rode `python scripts/upstreams.py render`.
4. Se o preâmbulo precisar de pacote LaTeX novo, inclua o pacote Debian em `worker/Dockerfile`.
5. Rode `python -m unittest tests/test_formatos.py`. No deploy, o worker compila um exemplo de cada
   formato (`worker/format_smoke.py`) e o build para se algum não gerar PDF.

Os estilos CSL oficiais ficam em https://github.com/citation-style-language/styles (ex.: `vancouver.csl`,
`chicago-author-date.csl`, `ieee.csl`, `associacao-brasileira-de-normas-tecnicas.csl`).

## Fora desta pasta

`worker/templates/` guarda os modelos do motor antigo com API do Gemini (aba Nova pesquisa). Eles seguem
o formato do PaperOrchestra original e não usam este registro.
