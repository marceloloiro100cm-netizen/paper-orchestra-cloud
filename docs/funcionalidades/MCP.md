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
  Firestore (`mcp_tokens`); o token aparece uma vez. No máximo 5 ativos por conta. Chaves criadas a partir de 28/11/2026 valem 1 ano (`TOKEN_VALID_DAYS`); as anteriores valem até serem revogadas.
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
| `criar_projeto` | título, pergunta, até 20 fontes, idioma, tipo e modelo (a norma: `abnt-artigo`, `apa7` ou `artigo-simples`; a lista vem de `formatos/`); dispara o preparo |
| `listar_projetos`, `estado_do_projeto` | andamento, quem entregou cada etapa, independência |
| `proxima_etapa` | papel, instruções e material da etapa atual; emite a cabeça redatora ou o passe |
| `abrir_passe` | numa conversa nova: cabeça revisora ou verificadora, só com o material da etapa |
| `referencias_do_projeto`, `ficha_da_fonte` | chaves oficiais e ficha sem IA |
| `buscar_trechos`, `ler_trecho` | busca BM25 nos trechos e texto integral para citar |
| `entregar_etapa` | entrega; volta com erros se não passar nas checagens |
| `compilar` | PDF com a bibliografia oficial (worker, TeX restrito). Versão final só com todas as referências confirmadas e sem erro de LaTeX; `rascunho=true` (ou qualquer pendência) gera PDF marcado como RASCUNHO |
| `corrigir_referencia` | confirma ou corrige autor, título, ano, tipo, veículo e DOI pelo próprio documento (título exato ou quase idêntico a uma linha ou título de seção das primeiras páginas); mantém a chave |
| `refazer_referencias` | refaz a bibliografia com as regras atuais (worker, sem IA), mantendo as chaves citadas e as correções; nunca rebaixa uma referência |
| `reabrir_reescrita` | reabre a reescrita e a verificação depois de aceitas, para corrigir um problema que só apareceu na compilação (a reescrita recebe o texto anterior e os erros de LaTeX) |

## Etapas e cabeças

1. Planejamento (redatora): plano em Markdown que usa as chaves do projeto.
2. Evidências (redatora): JSON com no mínimo 8 itens; cada `citacao_literal` é conferida no texto da fonte.
3. Redação (redatora): corpo LaTeX com resumo, 3+ seções e só chaves existentes. Cada citação direta
   (entre aspas, 4 ou mais palavras) precisa estar, palavra por palavra, numa fonte citada no mesmo
   parágrafo; trecho com "[...]" é conferido por partes, e "tradução nossa" dispensa a conferência literal.
   Se o trecho estiver em outra fonte, a entrega volta dizendo qual. O mesmo vale para a reescrita.
4. **Revisão (revisora, conversa nova por passe)**: JSON com nota e problemas tipados.
5. Reescrita (redatora): corpo LaTeX tratando a revisão.
6. **Verificação (verificadora, conversa nova por passe)**: 10+ afirmações com veredito; citações conferidas.

Regras de independência: a cabeça que entrou por passe não escreve; uma cabeça que já
entregou outra etapa não revisa nem verifica. O relatório marca `outra_ia` (modelo ou
cliente diferentes), `outra_conversa` (mesma IA, conversa nova) ou `mesma_cabeca`. O
modelo é **declarado** pela IA e o cliente vem do protocolo (ou do User-Agent): é
registro de boa-fé, não prova.

## Modo revisão sistemática

`criar_projeto(..., tipo="revisao_sistematica")`. Ideias trazidas da LENAI, plataforma de
revisão sistemática de uma colega do mestrado (só as ideias; nenhum código copiado).

| Etapa | Cabeça | O que o Scriptorium confere |
|---|---|---|
| Protocolo | redatora | PICOC, QP, IC, EC, AQ, escala (3+ respostas com peso), nota de corte, campos de extração, busca declarada |
| Triagem | redatora | todas as fontes decididas uma vez; IC/EC coerentes com a decisão; checklist de leitura; citação literal |
| Triagem independente | triadora, **conversa nova por passe, às cegas** | o mesmo; o servidor calcula o kappa de Cohen e as divergências |
| Consenso | redatora | resolve só as divergências (pulada automaticamente se não houver) |
| Qualidade e extração | redatora | nota pela escala; cada campo e os trechos de método, resultados e limitações com citação literal conferida |
| Síntese por questão | redatora | todas as QP respondidas, só com estudos da amostra final |
| Redação, revisão, reescrita, verificação | como no artigo | a redação recebe protocolo, PRISMA, kappa, matriz e síntese |

- Decisão `fora_da_triagem` para guias de método e textos teóricos: ficam fora do PRISMA.
- `excluir_abaixo_do_corte` no protocolo tira da amostra final os estudos com nota abaixo do corte.
- PRISMA 2020 calculado das decisões, com conferência de conservação (identificados, duplicados,
  excluídos no título e resumo, não recuperados, avaliados, excluídos, incluídos). A figura entra
  no PDF na linha `%PRISMA` (ou antes de Resultados), em LaTeX simples.
- Zonas do artigo (resumo, método, resultados, limitações...) pelo título da seção:
  `buscar_trechos(..., zona="metodo")`.
- Site: na etapa Execuções e Auditorias, cada projeto abre etapas, concordância, PRISMA, matriz de
  extração (CSV) e a síntese por questão. O pesquisador pode gravar a **versão final** de cada
  resposta; ela substitui a da IA na redação e fica registrada na proveniência.

## Confiança das referências e trava do PDF final

Achado do teste de 25/11/2026: o PDF saiu "pronto" com 7 referências erradas e uma correspondência
falsa do OpenAlex (Kitchenham virou "Department of Computer Science, 2013") sem aviso.

| Origem (`how`) | Confiança | Quando |
|---|---|---|
| `doi` | confirmada | DOI registrado na importação da fonte |
| `corrigida_pelo_texto` | confirmada | `corrigir_referencia`, conferida no documento |
| `doi_no_texto`, `texto_do_pdf`, `titulo_do_pdf` | sugerida | busca no OpenAlex; pode ser outra obra |
| `arquivo` | a conferir | só o que o arquivo diz |

- A tabela é a mesma em `api/mcp_flow.py` e `worker/bib_integrity.py` (teste impede divergência).
- `compilar` recusa a versão final com referência sugerida ou a conferir. O worker confere de novo e,
  se houver pendência, erro de LaTeX ou citação sem referência, gera RASCUNHO (título e topo do PDF
  marcados, motivos no estado do projeto). Com erro de LaTeX, compila de novo já marcado.
- Cada referência guarda `consulta.status` (`ok`, `sem_resultado`, `api_recusou`, `parcial`,
  `sem_consulta`): uma recusa do OpenAlex não se confunde mais com "obra não encontrada".
- OpenAlex: desde 13/02/2026 a API exige chave. Rode uma vez, como administrador,
  `PROJECT_ID=paperorchestra-mestrado bash scripts/setup-openalex-key.sh`: a chave vai para o Secret
  Manager (`scriptorium-openalex`) e para o worker como `OPENALEX_API_KEY`. O deploy automático preserva.
- Site: em Seus artigos, cada referência pendente mostra o nível; o botão "Refazer referências"
  (`POST /api/mcp-conta/projetos/{id}/referencias/refazer`) faz o mesmo que `refazer_referencias`.

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

## O que o estudante vê no site

- **Comece aqui**: três passos com estado (fontes enviadas, IA conectada, artigo pedido). Some quando os três estão feitos.
- **Conectar sua IA** (Minha conta): escolha da IA (Claude, ChatGPT ou Gemini), chave de conexão, os três passos só daquela IA e o primeiro pedido pronto para copiar. "Token" aparece no site como "chave de conexão".
- **Seus artigos**: cada projeto mostra o progresso, o próximo passo em linguagem simples com o pedido pronto para copiar (inclusive o passe da conversa nova), as referências que ainda pedem conferência e o que o Scriptorium já conferiu (citações literais, revisão, verificação, kappa). A lógica fica em `api/mcp_student.py`, sem IA; as rotas `/api/mcp-conta/projetos` devolvem esses campos.
- **Pesquisas anteriores**: as pesquisas do modo com API ficam recolhidas; cada uma mostra o PDF e o resto em "Mais arquivos, relatórios e opções".
