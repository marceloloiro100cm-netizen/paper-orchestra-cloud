# Implantação

Como colocar uma cópia do Scriptorium no ar num projeto Google Cloud próprio. É o caminho de quem quer **replicar** o produto (por exemplo, outra instituição). Para só contribuir com código, os testes bastam ([CONTRIBUTING.md](../CONTRIBUTING.md)).

> Os serviços abaixo cobram por uso (Cloud Run, Cloud Build, Storage, Firestore). Configure um alerta de orçamento antes de começar. O Scriptorium não usa modelo pago no modo MCP; no modo com API, os tokens saem da chave Gemini de cada pesquisador.

## 1. Pré-requisitos

- Conta Google com um **projeto Firebase** novo, no plano **Blaze**.
- **Firestore** `(default)` em modo nativo, criado na região desejada (o Scriptorium usa `southamerica-east1`).
- **Authentication → Google** ativado, com e-mail de suporte.
- Um **Web App** registrado nas configurações do projeto.
- Acesso ao **Cloud Shell** do projeto, com uma conta que possa criar contas de serviço, habilitar APIs e alterar IAM.

## 2. Trocar os identificadores do projeto

O repositório traz os valores da instalação oficial (`paperorchestra-mestrado`). Numa cópia, troque:

| Arquivo | O que trocar |
|---|---|
| `.firebaserc` | ID do projeto (modelo em `.firebaserc.example`) |
| `public/config.js` | configuração pública do Web App (modelo em `public/config.js.example`). **Nunca** ponha chaves privadas aqui. |
| `.github/workflows/*.yml` | `workload_identity_provider`, `service_account` e `project_id` (só se for usar o deploy pelo GitHub) |
| `api/main.py` | `PUBLIC_URL` padrão, ou defina a variável no Cloud Run |
| `scripts/*.sh` | alguns scripts (`configure-guardrails.sh`, `configure-budget.sh` e outros) fixam `PROJECT="paperorchestra-mestrado"` no topo |
| `hosting-redirect/` e `deploy-hosting.yml` | só existem para o endereço antigo da instalação oficial; podem ser apagados numa cópia |

## 3. Primeira implantação (Cloud Shell)

```bash
git clone https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud.git
cd paper-orchestra-cloud
PROJECT_ID=<seu-projeto> bash scripts/deploy-cloud-shell.sh
```

O script pede o e-mail Google do administrador e então:

1. habilita as APIs e cria as contas de serviço da API e do worker, com permissões mínimas;
2. cria o bucket privado `<projeto>-paper-storage`;
3. constrói as imagens de `api/` e `worker/` (o worker inclui LaTeX; o build demora);
4. publica o Cloud Run Job `paper-orchestra-worker` e o serviço `paper-orchestra-api`;
5. publica as regras do Firestore e o Hosting.

Se o script parar por falta de permissão, **não** o repita às cegas: leia o erro e ajuste só a permissão que falta.

Depois:

- **OpenAlex** (referências): `PROJECT_ID=<seu-projeto> bash scripts/setup-openalex-key.sh`.
- **Proteções:** `bash scripts/configure-guardrails.sh` (backups do Firestore) e `bash scripts/configure-budget.sh` (alerta de orçamento).
- **Modo com API (opcional):** `bash scripts/setup-byok-iam.sh`; ver [operacao/BYOK-BOOTSTRAP-PRODUCAO.md](operacao/BYOK-BOOTSTRAP-PRODUCAO.md).

## 4. Deploy contínuo pelo GitHub (opcional)

Para que cada merge em `main` publique sozinho ([WORKFLOWS.md](WORKFLOWS.md)):

1. Crie a conta de serviço `paper-orchestra-deployer`, **sem chave JSON**.
2. Em **IAM → Federação de identidade da carga de trabalho**, crie o pool e o provedor OIDC `github-actions`, com emissor `https://token.actions.githubusercontent.com`. Mapeie `google.subject=assertion.sub` e `attribute.repository=assertion.repository`, e **restrinja a condição ao seu repositório exato**.
3. Dê à identidade federada a função **Workload Identity User** na conta `paper-orchestra-deployer`, e à conta só as permissões de deploy (Cloud Run, Cloud Build, Artifact Registry, Storage, Firebase Hosting). Nunca Owner.
4. Atualize o provedor e a conta de serviço nos arquivos `.github/workflows/*.yml`.

> Renomear o repositório muda o valor de `assertion.repository`: atualize a condição do provedor no mesmo momento, senão o deploy para.

Guia oficial: https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines

## 5. Conferir

- `https://<seu-projeto>.web.app/api/health` responde `{"ok": true, …}`.
- O login com o e-mail do administrador funciona; outros e-mails precisam de convite (**Minha conta → Convidar pesquisador**).
- Um projeto de teste com duas ou três fontes chega ao PDF (rascunho já basta).

O registro detalhado da implantação oficial, com os problemas encontrados no caminho, está em [historico/IMPLANTACAO-2026-11.md](historico/IMPLANTACAO-2026-11.md).
