# Histórico de versões

Formato inspirado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). As versões `-piloto` são congeladas para a coleta empírica do produto técnico-tecnológico (ver [docs/pesquisa/REPLICABILIDADE-PTT.md](docs/pesquisa/REPLICABILIDADE-PTT.md)); cada uma tem uma [Release](https://github.com/marceloloiro100cm-netizen/scriptorium/releases) no GitHub.

## [Não lançado]

### Adicionado
- Normas de formatação reunidas em `formatos/`, uma pasta por norma, com APA 7 configurável (#107).
- Exclusão segura de textos escritos, com confirmação e limpeza dos arquivos gerados (#106).
- Licença AGPL-3.0, `CITATION.cff`, guia de contribuição, código de conduta, política de segurança e modelos de issue e PR.
- Documentação reorganizada por público em `docs/` (uso, arquitetura, desenvolvimento, pesquisa e histórico) (#109).
- Cabeçalho de segurança CSP em modo só relatório (#110).
- Chaves de conexão do MCP com validade de 1 ano; limite de 10 apontamentos a cada 10 minutos no link do orientador.
- CI com lint (ruff) e relatório de cobertura dos testes.
- Rótulos curtos nos ícones do cabeçalho no celular; resumo do README em inglês; guia do DOI pelo Zenodo.

### Alterado
- "Como usar" virou botão ao lado de "Minha conta"; a faixa "Comece aqui" saiu (#104).
- Workflows do GitHub Actions com nomes padronizados por prefixo; os de uso único foram removidos (#109).
- Testes renomeados pelo assunto, não pela fase em que foram escritos (#109).
- CSS e dois scripts do `index.html` em arquivos próprios; nome Scriptorium na API e no cabeçalho (#110).
- Scripts de implantação aceitam `SCRIPTORIUM_PROJECT` e `SCRIPTORIUM_SITE`, para replicar o Scriptorium em outro projeto.
- Repositório renomeado de `paper-orchestra-cloud` para `scriptorium`; o nome antigo saiu de textos, código e workflows (continua só na infraestrutura que o Google não deixa renomear).

### Corrigido
- Artigo ABNT compila com o abnTeX2 1.9.7; o build da imagem do worker passou a rodar nos PRs (#108).
- Exportação .txt do Guia preserva as quebras de linha (#105).
- No computador, sem login, "Guia de escrita" rola até o guia (#110).
- Mudanças em `public/guia/` e `public/brand/` passam a disparar o deploy do site (#109).
- A checagem de sintaxe do CI conferia só o primeiro script; agora confere todos.
- Botões e campos sem nome acessível para leitores de tela.

## [v1.1.2-piloto] — 2026-11-26

### Adicionado
- Bloqueio de envio duplicado de fontes, listagem resumida com detalhe sob demanda e navegação conforme o modo de autonomia (#103).

## [v1.1.1-piloto] — 2026-11-26

### Corrigido
- Leitura de citações ABNT com três autores e citações múltiplas, metadados da ficha de leitura e ajustes de interface encontrados na auditoria de ponta a ponta com dois artigos (#102).

## [v1.1-piloto] — 2026-11-26

Versão de referência para a coleta empírica do PTT.

### Adicionado
- Núcleo Zotero/ABNT, fichamento por página, comando `/citar` e declaração de uso de IA conforme a IN IFRS 16/2026 (#99).
- Tutor socrático, resumo PRISMA, comentários da orientação, mapa visual do fio condutor e rubrica 0–15 (#100).
- Ponte de mão dupla entre Biblioteca e Guia; tutor socrático também nas conversas de revisão (#101).

## [v1.0-piloto] — 2026-11-26

Primeira versão congelada para o estudo piloto. Reúne o trabalho de 23 a 26/11/2026:

- **Modo sem API (MCP):** a IA do próprio pesquisador escreve; o Scriptorium entrega trechos e confere cada etapa (#80, #81).
- **Guia de escrita** em oito etapas, integrado ao site (#88, #91, #94).
- **Referências confiáveis:** confirmação pelo texto da fonte, três níveis de confiança e trava do PDF final (#84, #85, #92, #93).
- **Revisão sistemática** no fluxo MCP (#86).
- **Dissertação e TCC ABNT** e exportação para Word (#96).
- **Orientação:** link temporário, ajuda progressiva e tour sem jargão (#97).
- **Estudo piloto ético:** TCLE, SUS e transferência sem IA (#98).
- **Biblioteca:** importação de PDFs de acesso aberto por DOI ou link (#69, #76, #77).
- **Busca nas fontes** avaliada num corpus de referência de 30 documentos (#65–#71).
- **Backups** do Firestore e do Storage com retenção (#73–#75).
- **Identidade visual** em duas cores e endereço oficial `scriptoriummpie.web.app` (#60, #62).

O histórico detalhado da implantação está em [docs/historico/IMPLANTACAO-2026-11.md](docs/historico/IMPLANTACAO-2026-11.md).

[Não lançado]: https://github.com/marceloloiro100cm-netizen/scriptorium/compare/v1.1.2-piloto...main
[v1.1.2-piloto]: https://github.com/marceloloiro100cm-netizen/scriptorium/compare/v1.1.1-piloto...v1.1.2-piloto
[v1.1.1-piloto]: https://github.com/marceloloiro100cm-netizen/scriptorium/compare/v1.1-piloto...v1.1.1-piloto
[v1.1-piloto]: https://github.com/marceloloiro100cm-netizen/scriptorium/compare/v1.0-piloto...v1.1-piloto
[v1.0-piloto]: https://github.com/marceloloiro100cm-netizen/scriptorium/releases/tag/v1.0-piloto
