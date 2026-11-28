> **Arquivo histórico.** Este era o README do repositório até 28/11/2026: registra a implantação e as ondas do plano V2 na ordem em que aconteceram. A visão atual do sistema está no [README](../README.md).

# 🎻 PaperOrchestra Cloud — laboratório permanente de pesquisa

**Arquitetura Firebase/Google Cloud independente do Cormyr**, projetada para ser usada durante um mestrado de dois anos, pelo navegador do celular ou PC.

- **Firebase Hosting:** site responsivo em português, sempre disponível na URL `https://SEU-PROJETO.web.app`.
- **Firebase Authentication:** login com Google autorizado por lista de emails no backend.
- **Cloud Run (API):** endpoints para criar pesquisas, listar histórico, consultar progresso e baixar arquivos. Escala a zero para reduzir custos.
- **Cloud Run Jobs (worker):** motor original PaperOrchestra em Python 3.11 com LaTeX, executado como tarefa independente do navegador, com timeout de até 180 minutos.
- **Cloud Firestore:** histórico/status das pesquisas.
- **Cloud Storage:** ideias, registros experimentais, PDFs, fontes LaTeX e logs persistentes.
- **Vertex AI:** acesso Gemini via conta de serviço sem chave estática (padrão). **Secret Manager:** alternativa protegida para chave Gemini.
- **GitHub público:** somente código. Manuscritos, dados e credenciais nunca são commitados.

A conta de faturamento Google Cloud que você já usa pode pagar **outro projeto Firebase**, separado do Cormyr. Isso NÃO significa uso ilimitado gratuito: consumo do Gemini, Cloud Run Jobs, Storage, Build e demais APIs pode ser cobrado.

> **Status (23/11/2026):** Firebase Hosting, login Google, API e Cloud Run Job implantados. Uma pesquisa demonstrativa concluiu e gerou PDF/LaTeX. A versão com painel de agentes e modelo de revisão independente foi incorporada ao `main`; verifique o workflow [Atualizar API e agentes](https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud/actions/workflows/deploy-services.yml) para saber se a atualização de infraestrutura foi concluída. Este sistema não certifica resultados científicos. O PaperOrchestra original não é um produto Google oficialmente suportado.

## Como colocar no ar — primeira implantação

1. O repositório GitHub público destinado ao código é `marceloloiro100cm-netizen/paper-orchestra-cloud`. O projeto é independente do Cormyr.
2. Em [Firebase Console](https://console.firebase.google.com/), selecione o projeto **PaperOrchestra Mestrado** recém-criado. O **ID do projeto** já foi confirmado: `paperorchestra-mestrado`. O plano **Blaze** já foi confirmado. Mantenha o projeto independente de `cormyr`. Não altere o projeto `cormyr`.
3. Ative Firestore (database padrão, modo nativo), Firebase Authentication > Google, e registre um **Web App** nas configurações do projeto.
4. O aplicativo Web Firebase já foi registrado, e `public/config.js` já foi versionado com os valores públicos de configuração. **Não insira chaves do Gemini, credenciais IAM ou tokens privados nesse arquivo.**
5. Entre no [Google Cloud Shell](https://shell.cloud.google.com/) com o novo projeto e clone o novo repositório: `git clone https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud.git && cd paper-orchestra-cloud`.
6. Crie `public/config.js` no Cloud Shell (ex.: `nano public/config.js`) com o conteúdo configurado, e rode:

   ```bash
   PROJECT_ID=paperorchestra-mestrado bash scripts/deploy-cloud-shell.sh
   ```

   Por padrão, o script solicita seu email autorizado e usa **Vertex AI com a identidade da conta de serviço do Cloud Run Job**, sem precisar de chave Gemini. Esse caminho depende da disponibilidade e cotas do modelo no novo projeto. Como alternativa, defina `AI_PROVIDER=gemini_api` junto de `PROJECT_ID`; nesse caso o script solicitará uma chave Gemini sem mostrá-la e a gravará no Secret Manager. Nunca cole chaves em chats nem no GitHub.

7. Abra `https://scriptoriummpie.web.app` (endereço oficial desde 24/11/2026) no Android ou PC. O antigo `https://paperorchestra-mestrado.web.app` só redireciona para ele (`hosting-redirect/`, publicado por `.github/workflows/deploy-hosting.yml`).
8. Faça um primeiro teste com materiais reais, modelo Flash e sem gráficos. Baixe o PDF e confira os logs, referências e resultados.

**Atenção:** deploy inicial normalmente precisa de permissões de Cloud Build, Artifact Registry, Cloud Run Admin, Service Account Admin, Secret Manager e IAM; organização com políticas restritivas pode precisar de ajustes. O script termina se alguma pré-condição falhar. Não foi executado na sua conta.

## Limitações conhecidas

- Entrada de **ideia + log experimental** em texto, mais até 8 fontes da **biblioteca privada** (PDF, DOCX, BIB, RIS ou TXT). O texto extraído é limitado (20 mil caracteres por arquivo, 75 mil por pesquisa) e obras longas são truncadas. Figuras enviadas e revisão com controle editorial são evoluções futuras.
- Normas do modo sem API (MCP): ABNT (artigo, dissertação, TCC) e APA 7 (artigo e revisão, experimental), escolhidas no site em Novo artigo. Cada norma é uma pasta em `formatos/`. No modo antigo com API, os templates são ICLR e CVPR originais, e `abnt-artigo` e `abnt-dissertacao` (abnTeX2, experimentais). Os modelos ABNT são rascunhos: não garantem conformidade com NBR 6022, 10520 ou 6023 nem com manuais da instituição ou da revista.
- Gemini `3.1-pro-preview` e `3-flash-preview` são os nomes presentes na versão do PaperOrchestra aqui fixada; modelos preview podem deixar de existir ou mudar de preço.
- Não há cancelamento de Job pelo navegador, alertas de orçamento no aplicativo nem controle de custo por chamada. Limite: uma pesquisa ativa por conta, garantida por uma trava transacional no Firestore (`research_owner_state/{uid}`), inclusive contra cliques ou requisições simultâneas.
- Se o processo original falhar ao compilar, a pesquisa é marcada como falha. A versão inicial não oferece checkpoints dos agentes nem recomeço de uma etapa isolada.
- Um Job interrompido abruptamente antes de atualizar o Firestore é reconciliado pela API: passados 200 minutos do início (o `task-timeout` do Job é 180 min), a pesquisa é marcada como falha e a conta é liberada. O limite pode ser ajustado pela variável `JOB_STALE_MINUTES` da API; ele deve ficar sempre acima do `task-timeout`. Não há consulta ao Cloud Run Executions, então o motivo exato da interrupção fica só nos logs do Cloud Run.
- Não foi realizada verificação de cobertura dos testes de integração na infraestrutura real. O projeto é um ponto de partida técnico, não uma implantação homologada.

## Segurança e retenção

- A API pública no Cloud Run aceita a conexão HTTP, mas **cada endpoint de pesquisa** verifica o Firebase ID token (inclusive `email_verified`) e a lista de emails autorizados. Não desative essa verificação.
- O Firestore tem regras que negam acesso direto do navegador. O backend, com Admin SDK e IAM, é o único que lê/grava os dados. O bucket impede acesso público.
- Dados **não** devem ser colocados em repositório público, GitHub Issues, Actions logs, variáveis do repositório ou na configuração JavaScript do navegador.
- Cloud Run Jobs executa tarefas longas independente da sessão HTTP; fechar o celular não elimina os arquivos persistentes no Cloud Storage.
- Sem prazo automático de dois anos: você mantém o ambiente enquanto o projeto, a conta de faturamento e as credenciais permanecerem ativos. Faça exportações periódicas dos seus PDFs e fontes.
- Configure limites de gastos apropriados no Cloud Billing. Os alertas simples só avisam; no Google Cloud de 2026 existem *spend caps* para serviços elegíveis, mas nem todos os serviços são abrangidos.

## Organização

```
api/                  # API FastAPI + verificação de Firebase Auth
worker/               # job original PaperOrchestra + salvamento no Storage
formatos/             # normas de formatação (ABNT, APA 7...): uma pasta por norma, ver formatos/README.md
public/               # interface responsiva para celular
scripts/deploy-cloud-shell.sh
firebase.json         # hosting + proxy de /api para Cloud Run
firestore.rules       # nega acesso client-side direto
.github/workflows/    # validação em cada push
```

## Referências técnicas

- PaperOrchestra: https://github.com/google-research/paper-orchestra (commit fixado no Dockerfile do worker)
- Firebase Hosting + Cloud Run: https://firebase.google.com/docs/hosting/cloud-run
- Cloud Run Jobs: https://docs.cloud.google.com/run/docs/create-jobs
- Firebase / contas de faturamento: https://firebase.google.com/docs/projects/billing/firebase-pricing-plans
- GitHub Actions em repositórios públicos: https://docs.github.com/en/billing/concepts/product-billing/github-actions

## Disponibilidade dos modelos

O motor original aceita `VERTEX_AI_PROJECT` e `VERTEX_AI_LOCATION`. Nesta instalação, os jobs executam em `southamerica-east1`, mas as requisições aos modelos Gemini preview usam o endpoint `global`. Alguns modelos podem exigir cota ou acesso específico; os IDs preview podem ser aposentados durante os dois anos do mestrado, exigindo atualização e reteste. O plano Blaze permite cobrança por uso, mas não garante automaticamente acesso a todos os modelos.

## Próxima configuração manual no Firebase

O aplicativo Web `PaperOrchestra Web` já foi registrado; as configurações públicas estão em `public/config.js`. Agora habilite **Authentication → Google** (e-mail de suporte definido) e crie o **Firestore Database padrão `(default)` em modo nativo/Standard**, na região `southamerica-east1` para ficar perto dos serviços. Escolha regras iniciais de produção; nosso `firestore.rules` nega acesso direto do navegador. Depois será necessário executar o deploy a partir do Cloud Shell. `apiKey` do Web App é configuração pública do Firebase e NÃO é uma chave Gemini; não divulgue chaves Gemini, tokens de conta de serviço ou arquivos JSON privados.

## Região de armazenamento e processamento

O Firestore `(default)` foi planejado para `southamerica-east1` (São Paulo), região escolhida pelo usuário no console; a criação do banco ainda precisa ser confirmada. O Cloud Run (API e Jobs), o Artifact Registry e o bucket de pesquisa estão configurados na mesma região. A localização de inferência Vertex AI permanece `global`, por compatibilidade com modelos Gemini preview, de modo que as chamadas ao modelo não devem ser tratadas como uma garantia de processamento exclusivamente no Brasil. Os valores podem diferir dos preços dos serviços nos Estados Unidos.

## Implantação após Firestore criado

No Firebase Console, abra o Cloud Shell integrado (ícone terminal `>_`). Execute, na mesma sessão autenticada:

```bash
git clone https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud.git
cd paper-orchestra-cloud
bash scripts/deploy-cloud-shell.sh
```

O script opera exclusivamente em `paperorchestra-mestrado`. Solicitará o e-mail Google autorizado. Ele cria recursos que podem gerar custos e usa Vertex AI por padrão. Não confirme mensagens ou compartilhe tokens se o terminal indicar outro projeto. Se houver falha de IAM/Cloud Build, não repita o script cegamente: verifique o erro e ajuste as permissões específicas antes de tentar novamente.

## Instalação alternativa sem Cloud Shell (celular)

O GitHub tem o workflow manual [Publicar PaperOrchestra (manual)](https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud/actions/workflows/deploy-manual.yml). Ele **não** está pronto para execução até que o Google Cloud autorize a identidade GitHub.

1. No projeto `paperorchestra-mestrado`, abra Google Cloud Console → IAM e administrador → Contas de serviço. Crie uma conta de serviço com ID `paper-orchestra-deployer`. **Não crie chave JSON.**
2. No Google Cloud Console → IAM e administrador → Federação de identidade da carga de trabalho, crie o pool `github-actions` e o provedor OIDC `github-actions`, com emissor `https://token.actions.githubusercontent.com`. Mapeie `google.subject=assertion.sub` e `attribute.repository=assertion.repository`. Restrinja por condição de atributo ao repositório exato `marceloloiro100cm-netizen/paper-orchestra-cloud` e branch `refs/heads/main`; não permita acesso genérico a todos os repositórios do GitHub.
3. Conceda à identidade federada desse repositório a função **Workload Identity User** na conta de serviço `paper-orchestra-deployer`. Configure as permissões de implantação estritamente necessárias para criar/atualizar Cloud Run, Cloud Build, Artifact Registry, Storage e Firebase no próprio projeto, analisando separadamente operações iniciais de bootstrap que modificam políticas IAM. Não conceda Owner ao workflow de forma permanente.
4. Só depois disso abra Actions → Publicar PaperOrchestra (manual) → Run workflow. Insira o e-mail Google autorizado e acompanhe o log. Esse workflow usa credenciais temporárias sem chaves JSON.
5. O workflow atual é um **ponto de partida não homologado**. A primeira instalação ainda pode revelar ajustes em IAM, Cloud Build e credenciais ADC do Firebase CLI. Não execute repetidamente em caso de falha; avalie os logs e os custos primeiro.

Documentação oficial: https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines

### Cautela de segurança
O registro de `public/config.js` contém somente a configuração pública do Web App Firebase; nunca adicione tokens privados, credenciais JSON, senhas ou chaves Gemini ao repositório. O uso do workflow no GitHub **não libera administração irrestrita** nem dispensa a conexão IAM inicial no Google Cloud.

> Observação (23/11/2026): o ID do provedor exibido no Google Cloud é `github-actions` e o workflow `.github/workflows/deploy-manual.yml` foi alinhado a `projects/201655574048/locations/global/workloadIdentityPools/github-actions/providers/github-actions`. Antes de salvar o provedor, mapear `google.subject` → `assertion.sub`, `attribute.repository` → `assertion.repository` e restringir a condição ao repositório `marceloloiro100cm-netizen/paper-orchestra-cloud` na branch `refs/heads/main`.

## Painel de agentes (segunda fase)

Os cinco módulos do PaperOrchestra original já são orquestrados automaticamente: planejamento, literatura, redação, refinamento e, quando solicitado, gráficos. Em novas pesquisas, o worker registra no Firestore o avanço **a partir dos arquivos efetivamente produzidos**, sem inventar porcentagens. Para acompanhar: **Histórico de pesquisas → Acompanhar agentes**. Trabalhos anteriores à nova versão não possuem histórico retroativo por agente.

A interface permite escolher um modelo Gemini para o rascunho e, opcionalmente, outro para o agente de refinamento. Modelos Pro podem gerar custo superior ao Flash. O gráfico continua opcional.

**Limitação acadêmica importante:** O PDF do teste de infraestrutura exibiu percentuais de "integridade" e descrições de módulos de verificação sem documentação dos respectivos testes. Um arquivo produzido com sucesso não prova validade de afirmações, referências, estatísticas nem conformidade científica. Sempre revisar referências originais e remover ou sinalizar métricas não suportadas.

A busca bibliográfica do PaperOrchestra usa a API pública do Semantic Scholar; uma chave dedicada `SEMANTIC_SCHOLAR_API_KEY` é opcional e não foi configurada neste ambiente. Sem ela, aplicam-se os limites de acesso da API pública. O motor de IA usa Vertex AI, não depende de uma chave Google AI Studio.

Atualização de API/worker: PR revisado → merge em `main` → workflow **Atualizar API e agentes PaperOrchestra** constrói duas imagens e atualiza as revisões do Cloud Run preservando as identidades e os dados. A atualização do Hosting é feita por workflow separado. Não reiniciar geração em andamento durante operações de implantação.


## Triagem científica e idioma (terceira fase, 23/11/2026)

Novas gerações podem escolher `pt-BR` como preferência experimental, sem mudar o template LaTeX original ICLR/CVPR. Isso **não garante** tradução perfeita nem atende automaticamente às normas ABNT. Os arquivos de entrada originais permanecem no Cloud Storage.

Após um manuscrito terminar, o worker produz `scientific_audit.json` no mesmo espaço privado da pesquisa. O relatório usa uma inspeção determinística (não consome Gemini) para sinalizar:
- percentuais quando os dados de entrada declaram não ter ocorrido experimentos;
- alegações específicas de verificação/auditoria que precisam de evidência;
- comandos `\\cite*` cujas chaves não constam do `references.bib`;
- ausência de entradas BibTeX.

No celular, **Histórico de pesquisas → Ver auditoria** aparece apenas para trabalhos novos em que o JSON foi produzido. O relatório é acessado pelo backend com o mesmo token de acesso e autorização por UID que protege os PDFs. Manuscritos anteriores continuam disponíveis, mas sem auditoria retroativa.

**Atenção:** o relatório NÃO valida DOI, títulos, autores, existência real de fontes, percentuais, desenho experimental ou verdade das afirmações. Alertas heurísticos têm falsos positivos e não substituem leitura crítica e busca nas fontes originais. `audit_status=unavailable` explicita qualquer falha na geração do relatório, sem bloquear a entrega do PDF.

O original PaperOrchestra usa Semantic Scholar para busca bibliográfica. Uma chave de acesso dedicada é opcional e ainda não foi cadastrada nesta instalação. Nunca publique chaves no repositório; configurar somente por Secret Manager, após obter uma chave legítima.

## Rastreabilidade de origens e plano V2 (24/11/2026)

Toda origem externa do projeto (bibliotecas, APIs, normas, artigos e ferramentas) está registrada em **`docs/upstreams.json`**, com ID estável (R01 a R29 do plano técnico V2; R30 em diante para dependências que já eram usadas), URL canônica, licença, versão fixada, frequência de revisão e onde é usada. Os arquivos legíveis `docs/UPSTREAMS.md` e `docs/V2-MODULOS.md` (situação dos 27 módulos) são gerados a partir dele:

```bash
python scripts/upstreams.py render   # regenera os .md depois de editar o JSON
python scripts/upstreams.py check    # valida o registro, os pins no código e os .md
```

O CI falha se o commit do PaperOrchestra no `worker/Dockerfile`, a versão do Firebase JS em `public/app.js` ou a versão do OSV-Scanner divergirem do registro, ou se algum código citar `Origem: Rnn` inexistente. Toda segunda-feira o workflow **Vigiar upstreams** consulta GitHub, PyPI e npm e atualiza a issue "Rastreio de upstreams (vigia semanal)" com versões novas, licenças divergentes, repositórios movidos ou arquivados e revisões manuais vencidas. Dependabot (pip e GitHub Actions) e OSV-Scanner rodam em paralelo.

Primeiros módulos do plano V2 aplicados (todos parciais; detalhes em `docs/V2-MODULOS.md`):
- **M13:** o texto de anexos passa por `worker/document_guard.py`, que remove caracteres invisíveis, impede que o documento feche o bloco `<fonte_usuario>` e sinaliza frases típicas de instrução embutida.
- **M14:** cada execução gera `run_manifest.json` (versões, modelos, hashes das entradas, fontes e saídas, eventos), disponível em **Histórico → Manifesto de proveniência**, inclusive em falhas.
- **M11:** cada execução concluída gera `declaracao_uso_ia.md`, um **rascunho** para a IN IFRS nº 16/2026. O texto do Anexo da IN ainda não foi conferido item a item; o rascunho não afirma conformidade e tem campos a preencher pelo autor.
- **M07:** a conferência de referências consulta retratações, retiradas, expressões de preocupação e correções na Crossref (inclui Retraction Watch). Ausência de aviso não prova que a obra nunca foi retratada.
- **M15:** Dependabot, OSV-Scanner e o vigia semanal de upstreams.

### Onda 1 do plano V2: leitura por trechos (desligada por padrão)

Com `SCRIPTORIUM_V2_RETRIEVAL=true` no Cloud Run Job, as fontes da biblioteca deixam de entrar como "primeiros 20 mil caracteres de cada arquivo" e passam a entrar como **trechos selecionados por relevância para a ideia**, cada um com fonte, página e seção (`[trecho id | p. 12-13 | seção: ...]`). O orçamento total continua 75 mil caracteres, então o custo não aumenta. Componentes: `structured_extract.py` (M01/M02, PyMuPDF com bbox por bloco), `chunking.py` (M19), `lexical_index.py` (M03/M04, SQLite FTS5 com BM25), `ocr_router.py` (M23, sinaliza páginas digitalizadas) e `retrieval_context.py` (seleção com rodízio entre fontes e relatório `retrieval_coverage.json`, M09). Os trechos ficam em cache privado em `library/{uid}/derived/`, por hash do arquivo e versão do parser; são dados derivados e descartáveis.

Para ativar, depois que o deploy do worker estiver funcionando (Cloud Shell):

```bash
gcloud run jobs update paper-orchestra-worker --region=southamerica-east1 \
  --project=paperorchestra-mestrado --update-env-vars=SCRIPTORIUM_V2_RETRIEVAL=true
```

**Ligada em produção em 24/11/2026** (decisão do responsável): o valor fica em `V2_FLAGS`, no `.github/workflows/deploy-services.yml`, e é reaplicado a cada deploy. Para voltar ao comportamento anterior, use `SCRIPTORIUM_V2_RETRIEVAL=false` ali. O manifesto de cada execução registra qual estratégia foi usada.

### Onda 2 do plano V2: busca híbrida, citações e evidências (24/11/2026)

Com a Onda 1 ligada (`SCRIPTORIUM_V2_RETRIEVAL=true`), o worker também:

- **busca híbrida (M04):** combina BM25 com embeddings do Gemini (`gemini-embedding-001`, 768 dimensões) por Reciprocal Rank Fusion. Trechos que falam do mesmo assunto com outras palavras passam a ser encontrados. O envio de trechos das fontes ao serviço de embeddings foi autorizado pelo responsável do projeto. O administrador usa o Vertex do projeto; convidados usam a própria chave Gemini. Se o serviço falhar, a busca volta para BM25 e o manifesto registra isso. Para desligar só os embeddings: `SCRIPTORIUM_V2_EMBEDDINGS=false`.
- **citações literais (M05):** cada trecho entre aspas do manuscrito final é procurado nas fontes anexadas (encontrado, aproximado ou não encontrado), e ponteiros `[trecho id]` são resolvidos para fonte e página.
- **matriz de evidências (M08/M10):** cada afirmação com citação ou número recebe até 3 trechos candidatos das fontes, com página; afirmações sem nada parecido nas fontes anexadas são sinalizadas. O sistema não decide se o trecho apoia ou contradiz: isso é revisão humana.

Na interface: **Histórico → Citações e evidências** e **Matriz de evidências (CSV)**. A declaração de uso de IA passa a listar o modelo de embeddings quando ele for usado. Para medir a qualidade da busca no seu corpus, veja `docs/AVALIACAO-RECUPERACAO.md`.

### Onda 3 do plano V2: escudo de auditoria (24/11/2026)

Toda pesquisa nova passa a ter **Histórico → Escudo de auditoria** (M06). Ele junta todas as verificações em uma lista de alertas por gravidade (alta, média, baixa) e mostra o estado dos quatro estágios do plano: ponteiros e citações literais, metadados bibliográficos, retratações e correções, e suporte nas fontes. Não existe nota geral nem selo de "verificado".

Na conferência de referências, cada obra mostra **sinais de contexto separados** (M18): periódico ou preprint, idade, citações no OpenAlex, acesso aberto e sinais de retratação. Nada disso vira nota, porque prestígio não é veracidade. Referências não confirmadas nas bases globais recebem **links de busca no Google Acadêmico, na SciELO e na BRAPCI** (M24), para conferência manual de obras nacionais sem DOI. Com a leitura por trechos ligada, **Histórico → Cobertura das fontes** (M09) mostra quantos trechos de cada fonte os agentes realmente leram.

### Ondas 4 e 5 do plano V2: diagnóstico, aprovação de fontes e Zotero (24/11/2026)

- **Diagnóstico antes de gerar (M16) e aprovação de fontes (M12):** marque "Diagnosticar minhas fontes antes de gerar" na nova pesquisa. O worker lê as fontes e mostra, para cada pergunta ou subtópico da ideia, se a cobertura é boa, parcial ou se há lacuna, com os trechos e as páginas. A redação só começa quando você aprovar no histórico (dá para tirar fontes nesse momento) ou é descartada. A aprovação fica registrada no manifesto e na declaração de uso de IA. O diagnóstico usa a leitura por trechos mesmo com a flag V2 desligada, porque foi pedido por você e não gera texto.
- **Divergências entre fontes (M17, experimental):** com `SCRIPTORIUM_V2_CONTRADICTIONS=true`, até 12 pares de trechos de fontes diferentes sobre o mesmo assunto são classificados pelo modelo (convergente, divergente, contexto diferente, não comparável). Aparecem no escudo de auditoria. Desligado por padrão, porque cada par é uma chamada extra ao modelo.
- **Importação do Zotero (M26):** em Biblioteca → Importar do Zotero, cole uma chave **somente leitura**, escolha a coleção e importe os metadados como um .bib. A chave é usada só nessa requisição e não é guardada. Anexos não são importados.

> **Pendência:** a API e o worker em produção ainda estão na versão de 23/11, até o bootstrap de IAM no Cloud Shell (issue #43). O site já tem a interface nova; os recursos acima passam a funcionar depois desse passo.

### Módulos finais do plano V2: reranking, verificação iterativa e revisões (24/11/2026)

Com isso, os 27 módulos do plano têm ao menos uma parte implementada (situação de cada um em `docs/V2-MODULOS.md`).

- **Reranking (M20):** integração com o FlagEmbedding (`BAAI/bge-reranker-v2-m3`) e o InRanker (UNICAMP) pronta, mas desligada (`SCRIPTORIUM_V2_RERANKER=none`). As bibliotecas não estão na imagem do worker: o plano só as adota se a avaliação no corpus de referência mostrar ganho. Para medir: `scripts/eval_retrieval.py --reranker bge` (ver `docs/AVALIACAO-RECUPERACAO.md`).
- **Verificação iterativa (M22, experimental):** com `SCRIPTORIUM_V2_FIRE=true`, cada afirmação é verificada pelo modelo só com trechos das fontes anexadas. Quando ele não tem certeza, busca mais trechos e tenta de novo, até 3 ciclos e 40 chamadas por pesquisa. Ele só decide com confiança e citando os trechos pelo identificador; atingir o limite nunca conta como "apoiada". Afirmações contrariadas viram alerta alto no escudo.
- **Revisões humanas (M08, M12, M24):** em "Citações e evidências", "Conferir referências" e "Verificação de afirmações", cada item tem um campo para registrar a sua conclusão (por exemplo, "o trecho apoia" ou "referência correta"). Cada registro é novo e o histórico é preservado.

### Onda 6 do plano V2: lacunas de engenharia (24/11/2026)

Sem custo de tokens novo (nenhuma etapa desta onda chama modelo de linguagem, salvo o parecer Neon, que já era opcional):

- **M02** "Ver na página do PDF": a API renderiza a página com o trecho destacado (PyMuPDF, R37; o rodapé do site linka o código-fonte, como pede a AGPL-3.0).
- **M03/M21** busca no conteúdo da biblioteca com índice FTS5 salvo por conta e ficha de leitura sem IA por documento.
- **M07** botão "Reavaliar retratações agora" em pesquisas concluídas (modo `editorial_recheck` do worker, só Crossref).
- **M08** matriz de evidências exportada com a sua revisão mais recente de cada afirmação.
- **M09** cobertura agrupada por autor, época e tema.
- **M13** inspeção estática dos arquivos enviados e quarentena fora da biblioteca (não é antivírus).
- **M15** orçamento de tempo por etapa (registrado no manifesto) e botão "Cancelar pesquisa".
- **M24** a sua conferência manual de uma referência reaparece nas pesquisas seguintes.
- **M25** o parecer Neon vê só um recorte da matriz de evidências.
- **M26** Zotero incremental (guarda só o número de versão) e anexos PDF com consentimento.
- **M27** referências da pesquisa em CSL-JSON e em lista ABNT (NBR 6023:2018).

Situação de cada módulo: `docs/V2-MODULOS.md`. Testes: `tests/test_v2_onda6.py`.

### IN IFRS 16/2026 e fichamento por IA (24/11/2026)

- **Declaração de uso de IA (M11)** alinhada ao texto da IN 16/2026 (conferido no PDF assinado em 26/05/2026): cada etapa da execução aparece com o inciso do Art. 6º correspondente, com as vedações do Art. 7º para confirmar e com a política de dados do Art. 9º. O modelo do Anexo I ainda não foi conferido, então o arquivo continua sendo um rascunho.
- **Autorização do orientador (Art. 6º e 8º)**: registrada em "Minha conta" (somente acréscimo) e copiada para cada pesquisa criada depois. Se for registrada depois, a declaração baixada recebe um adendo datado.
- **Dados inéditos (Art. 9º)**: toda pesquisa pergunta se há dados inéditos ou sensíveis. Se houver, a API exige a confirmação de que a chave Gemini está num projeto com faturamento ativo e de que os dados não identificam participantes. No nível gratuito, os termos da Gemini API (R47) permitem ao Google usar o conteúdo para melhorar produtos.
- **Fichamento por IA (M21)**: na ficha de leitura de cada documento, sob demanda, com o Gemini Flash na chave de quem pede. O resultado fica em cache: pedir de novo não gasta tokens.
- **M17 e M22 ligados em produção** (divergências entre fontes e verificação iterativa), com os tetos fixos de cada módulo.

## Separação de custos: infraestrutura x tokens de IA (24/11/2026)

- **Infraestrutura** (Cloud Run da API e do worker, Cloud Storage, Firestore, Secret Manager, Hosting, Cloud Build): projeto `paperorchestra-mestrado`, pago pela conta de faturamento do administrador.
- **Tokens de IA** (redação pelo PaperOrchestra, embeddings, diagnóstico, verificação de afirmações, comparação de fontes e parecer Neon): **sempre a chave Gemini pessoal de quem gera a pesquisa**, criada pelo pesquisador com a própria conta Google no Google AI Studio. Isso vale também para o administrador.

Como isso é garantido no código:
- a API grava `ai_auth_mode=user_gemini` em toda pesquisa nova e exige chave verificada, inclusive do administrador;
- o worker recusa qualquer pesquisa marcada para usar o Vertex do projeto (`admin_vertex`), a menos que `SCRIPTORIUM_ALLOW_PROJECT_AI=true` esteja definido na API e no worker. Essa exceção existe só para emergência e vem desligada;
- embeddings, verificação iterativa, comparação de fontes e Neon usam o cliente criado com a chave pessoal; o ambiente do motor original recebe só essa chave (as variáveis do Vertex são removidas).

Consequências práticas:
- o administrador precisa cadastrar a própria chave em **Minha conta** antes de gerar;
- Gemini Pro, Neon e limites maiores dependem do nível pago no AI Studio do pesquisador (Set up billing, com pré-pagamento);
- gráficos com IA ficam indisponíveis com chave pessoal, porque o modelo de imagem ainda não é testado na verificação da chave;
- pesquisas antigas continuam no histórico, marcadas como "tokens no projeto (anterior à separação)".
