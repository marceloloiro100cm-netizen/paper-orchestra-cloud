# 🎻 PaperOrchestra Cloud — laboratório permanente de pesquisa

**Arquitetura Firebase/Google Cloud independente do Cormyr**, projetada para ser usada durante um mestrado de dois anos, pelo navegador do celular ou PC.

- **Firebase Hosting:** site responsivo em português, sempre disponível na URL `https://SEU-PROJETO.web.app`.
- **Firebase Authentication:** login com Google autorizado por lista de emails no backend.
- **Cloud Run (API):** endpoints para criar pesquisas, listar histórico, consultar progresso e baixar arquivos. Escala a zero para reduzir custos.
- **Cloud Run Jobs (worker):** motor original PaperOrchestra em Python 3.11 com LaTeX, executado como tarefa independente do navegador, com timeout de até 180 minutos.
- **Cloud Firestore:** histórico/status das pesquisas.
- **Cloud Storage:** ideias, registros experimentais, PDFs, fontes LaTeX e logs persistentes.
- **Secret Manager:** chave Gemini nunca entra no GitHub nem no navegador.
- **GitHub público:** somente código. Manuscritos, dados e credenciais nunca são commitados.

A conta de faturamento Google Cloud que você já usa pode pagar **outro projeto Firebase**, separado do Cormyr. Isso NÃO significa uso ilimitado gratuito: consumo do Gemini, Cloud Run Jobs, Storage, Build e demais APIs pode ser cobrado.

> **Status:** código preparado para o repositório criado; o deploy real depende de identificar o ID do novo projeto Firebase, vinculá-lo ao plano Blaze e configurar credenciais. Esta versão ainda não passou por testes integrados em produção. O PaperOrchestra original não é um produto Google oficialmente suportado.

## Como colocar no ar — primeira implantação

1. O repositório GitHub público destinado ao código é `marceloloiro100cm-netizen/paper-orchestra-cloud`. O projeto é independente do Cormyr.
2. Em [Firebase Console](https://console.firebase.google.com/), selecione o projeto **PaperOrchestra Mestrado** recém-criado. Copie o **ID do projeto**, que é diferente do nome exibido. O screenshot mostra o plano **Spark**; antes de usar Cloud Run, faça **Fazer upgrade → Blaze**, escolhendo a mesma conta Cloud Billing já usada. Não altere o projeto `cormyr`.
3. Ative Firestore (database padrão, modo nativo), Firebase Authentication > Google, e registre um **Web App** nas configurações do projeto.
4. Copie `public/config.js.example` para `public/config.js`, preenchendo `apiKey`, `authDomain`, `projectId` e `appId` da configuração **pública do Web App Firebase**. Estes dados não são a chave Gemini e podem estar no repositório (mas o exemplo ignora o arquivo por padrão).
5. Entre no [Google Cloud Shell](https://shell.cloud.google.com/) com o novo projeto e clone o novo repositório: `git clone https://github.com/SEU_USUARIO/paper-orchestra-cloud.git && cd paper-orchestra-cloud`.
6. Crie `public/config.js` no Cloud Shell (ex.: `nano public/config.js`) com o conteúdo configurado, e rode:

   ```bash
   PROJECT_ID=SEU_NOVO_PROJETO bash scripts/deploy-cloud-shell.sh
   ```

   O script solicita seu email Google autorizado e a chave Gemini **sem mostrá-la na tela**, cria os recursos de Cloud Run/Storage/Secret Manager, constrói duas imagens e publica o Hosting. Para usar a API Gemini, obtenha uma chave no [Google AI Studio](https://aistudio.google.com/apikey). Não cole sua chave em chats nem em arquivos do Git.

7. Abra `https://SEU_NOVO_PROJETO.web.app` no Android ou PC. Se necessário, autorize esse domínio na tela Authentication > Settings > Authorized domains.
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
