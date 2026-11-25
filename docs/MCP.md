# Modo sem API: a IA do próprio pesquisador escreve (MCP)

## Por quê

Gerar um artigo inteiro pela API Gemini custa caro e estoura o limite de gasto de quem
testa. Neste modo o Scriptorium **não chama modelo nenhum**: cada pesquisador usa a IA
que já tem (assinatura ou plano gratuito) e o Scriptorium vira acervo e cartório.

| Quem faz | O quê |
|---|---|
| IA do pesquisador (Claude, Gemini CLI, ChatGPT...) | lê, planeja, escreve, revisa, verifica |
| Scriptorium (API) | guarda fontes, entrega trechos (BM25), confere cada entrega, controla a ordem das etapas e as cabeças |
| Scriptorium (worker, sem IA) | lê as fontes (trechos + BibTeX oficial via OpenAlex) e compila o PDF |

O modo com chave Gemini continua disponível para quem tiver créditos.

## Endereço e autenticação

- Endereço: `https://scriptoriummpie.web.app/api/mcp` (Streamable HTTP, sem estado,
  respostas JSON; aceita as revisões 2025-03-26, 2025-06-18, 2025-11-25 e 2026-07-28 via SDK oficial).
- Token pessoal gerado no site (Minha conta > Conectar sua IA). Só o hash SHA-256 fica no
  Firestore (`mcp_tokens`); o token aparece uma vez. No máximo 5 ativos por conta.
- Envio: `Authorization: Bearer scr_...` ou, para clientes que só aceitam um endereço,
  `/api/mcp/t/<token>`. Nesse caso o token aparece no log de acesso do Cloud Run: por isso
  é revogável e só abre as ferramentas abaixo.
- O token vale enquanto a conta tiver acesso ao Scriptorium (mesma regra do site).
- Próxima fase: OAuth (para o Claude conectar sem token no endereço). Exige expor
  `/.well-known/oauth-*` no Firebase Hosting.

## Ferramentas

| Ferramenta | Para quê |
|---|---|
| `listar_fontes` | itens da biblioteca (PDF, DOCX, TXT) |
| `criar_projeto` | título, pergunta, até 20 fontes, idioma, modelo (`abnt-artigo` ou `artigo-simples`); dispara o preparo |
| `listar_projetos`, `estado_do_projeto` | andamento, quem entregou cada etapa, independência |
| `proxima_etapa` | papel, instruções e material da etapa atual; emite a cabeça redatora ou o passe |
| `abrir_passe` | numa conversa nova: cabeça revisora ou verificadora, só com o material da etapa |
| `referencias_do_projeto`, `ficha_da_fonte` | chaves oficiais e ficha sem IA |
| `buscar_trechos`, `ler_trecho` | busca BM25 nos trechos e texto integral para citar |
| `entregar_etapa` | entrega; volta com erros se não passar nas checagens |
| `compilar` | PDF com a bibliografia oficial (worker, TeX restrito) |

## Etapas e cabeças

1. Planejamento (redatora): plano em Markdown que usa as chaves do projeto.
2. Evidências (redatora): JSON com no mínimo 8 itens; cada `citacao_literal` é conferida no texto da fonte.
3. Redação (redatora): corpo LaTeX com resumo, 3+ seções e só chaves existentes.
4. **Revisão (revisora, conversa nova por passe)**: JSON com nota e problemas tipados.
5. Reescrita (redatora): corpo LaTeX tratando a revisão.
6. **Verificação (verificadora, conversa nova por passe)**: 10+ afirmações com veredito; citações conferidas.

Regras de independência: a cabeça que entrou por passe não escreve; uma cabeça que já
entregou outra etapa não revisa nem verifica. O relatório marca `outra_ia` (modelo ou
cliente diferentes), `outra_conversa` (mesma IA, conversa nova) ou `mesma_cabeca`. O
modelo é **declarado** pela IA e o cliente vem do protocolo (ou do User-Agent): é
registro de boa-fé, não prova.

## Segurança do LaTeX

O corpo vem de uma IA e é compilado no worker. Duas barreiras:

1. A API recusa `\input`, `\include`, `\write`, `\openin`, `\csname`, `\def`, `\usepackage`,
   `\documentclass`, `^^` e afins (lista em `api/mcp_flow.py`, idêntica à do worker por teste).
2. O worker compila com `-no-shell-escape`, `openin_any=p`, `openout_any=p` e
   `shell_escape=f`: o TeX não lê nem escreve fora do diretório de trabalho.

## Arquivos

- Firestore: `mcp_projects`, `mcp_tokens`, `mcp_passes`; os trabalhos do worker usam
  `research_jobs` com modos `mcp_prepare` e `mcp_compile` (fora da lista de pesquisas).
- Cloud Storage: `mcp/{uid}/{projeto}/` com `sources.json`, `references.json/.bib`,
  `index.sqlite`, `etapas/{etapa}-v{n}.txt/.json` e `final/` (PDF, .tex, .bib,
  `proveniencia.json` com a declaração sugerida de uso de IA).

## Limites conhecidos

- A qualidade depende da IA de cada pesquisador.
- A busca é só lexical (BM25); vetores exigiriam modelo no servidor.
- PDF escaneado sem texto não entra (o preparo avisa).
- O texto do pesquisador vai para o provedor da IA dele, nas condições da conta dele
  (IN IFRS 16/2026, Art. 9º).
