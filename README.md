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

> **Status (23/11/2026):** código publicado, plano Blaze confirmado, ID Firebase `paperorchestra-mestrado` identificado, aplicativo Web registrado e configuração pública `public/config.js` publicada no GitHub. A autenticação Google e o Firestore `(default)` na região `southamerica-east1` foram confirmados em capturas. A implantação real ainda depende de executar o script no Cloud Shell; nenhum serviço Cloud Run/Hosting em produção foi validado. Esta versão ainda não passou por testes integrados em produção. O PaperOrchestra original não é um produto Google oficialmente suportado.

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

7. Abra `https://paperorchestra-mestrado.web.app` no Android ou PC. Se necessário, autorize esse domínio na tela Authentication > Settings > Authorized domains.
8. Faça um primeiro teste com materiais reais, modelo Flash e sem gráficos. Baixe o PDF e confira os logs, referências e resultados.

**Atenção:** deploy inicial normalmente precisa de permissões de Cloud Build, Artifact Registry, Cloud Run Admin, Service Account Admin, Secret Manager e IAM; organização com políticas restritivas pode precisar de ajustes. O script termina se alguma pré-condição falhar. Não foi executado na sua conta.

## Limitações conhecidas da V1

- Entrada de **ideia + log experimental** em texto. Upload de PDF e figuras, leitura de obras longas, estilos ABNT e revisão com controle editorial são evoluções futuras.
- Templates originais ICLR/CVPR; adequação para revista de Ciências Humanas exige um template específico.
- Gemini `3.1-pro-preview` e `3-flash-preview` são os nomes presentes na versão do PaperOrchestra aqui fixada; modelos preview podem deixar de existir ou mudar de preço.
- Não há cancelamento de Job pelo navegador, alertas de orçamento no aplicativo nem controle de custo por chamada. Limite inicial: uma pesquisa ativa por usuário, com uma verificação não transacional, adequada à utilização pessoal; não usar para vários usuários concorrentes sem endurecer essa regra.
- Se o processo original falhar ao compilar, a pesquisa é marcada como falha. A versão inicial não oferece checkpoints dos agentes nem recomeço de uma etapa isolada.
- O status de um Job interrompido abruptamente antes de atualizar Firestore pode continuar como `running`; a homologação de produção precisa de reconciliação por Cloud Run Executions.
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
