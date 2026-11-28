#!/usr/bin/env bash
# Provisionamento IAM BYOK (operação explícita, separada do deploy automático).
# Uso após revisão: bash scripts/setup-byok-iam.sh
# Não cria, lê ou imprime nenhuma chave Gemini.
set -euo pipefail
# Instalação oficial por padrão; numa cópia do Scriptorium, defina SCRIPTORIUM_PROJECT (ver docs/IMPLANTACAO.md).
SCRIPTORIUM_PROJECT="${SCRIPTORIUM_PROJECT:-paperorchestra-mestrado}"
PROJECT_ID="${PROJECT_ID:-$SCRIPTORIUM_PROJECT}"
EXPECTED_PROJECT="$SCRIPTORIUM_PROJECT"
if [[ "$PROJECT_ID" != "$EXPECTED_PROJECT" ]]; then
  echo "Projeto recusado: $PROJECT_ID" >&2; exit 2
fi
command -v gcloud >/dev/null || { echo "gcloud ausente" >&2; exit 2; }
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' --project="$PROJECT_ID")"
if [[ ! "$PROJECT_NUMBER" =~ ^[0-9]+$ ]]; then
  echo "Número do projeto inválido" >&2; exit 2
fi
API_SA="paper-orchestra-api@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_SA="paper-orchestra-worker@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOYER_SA="paper-orchestra-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
ROLE_ID="scriptoriumByokWriter"
AUDIT_ROLE_ID="scriptoriumByokAuditor"
ROLE="projects/${PROJECT_ID}/roles/${ROLE_ID}"
PERMISSIONS="secretmanager.secrets.create,secretmanager.secrets.get,secretmanager.secrets.delete,secretmanager.versions.add"

# API pode criar e atualizar SOMENTE segredos do prefixo BYOK.
# Criação é autorizada no recurso Project; demais operações no Secret.
API_CONDITION="resource.type == 'cloudresourcemanager.googleapis.com/Project' || resource.name.startsWith('projects/${PROJECT_NUMBER}/secrets/scriptorium-byok-')"
# Worker lê apenas versões dos segredos BYOK, NUNCA o segredo central.
WORKER_CONDITION="resource.name.startsWith('projects/${PROJECT_NUMBER}/secrets/scriptorium-byok-')"

# O Secret Manager já está ativo no projeto (modo legado usa). Quem roda o
# script pode não ter serviceusage.services.enable; nesse caso apenas avisa.
gcloud services enable secretmanager.googleapis.com --project="$PROJECT_ID" --quiet \
  || echo "Aviso: não foi possível (re)ativar secretmanager.googleapis.com; seguindo, pois a API já é usada."
if ! gcloud iam roles describe "$ROLE_ID" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam roles create "$ROLE_ID" --project="$PROJECT_ID" \
    --title="Scriptorium BYOK credential writer" \
    --description="Gerencia apenas o cofre de credenciais individuais; sem acesso a valores" \
    --permissions="$PERMISSIONS" --stage=GA --quiet
else
  gcloud iam roles update "$ROLE_ID" --project="$PROJECT_ID" \
    --permissions="$PERMISSIONS" --stage=GA --quiet
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${API_SA}" --role="$ROLE" \
  --condition="title=ScriptoriumBYOKWriter,description=Somente segredos por pesquisador,expression=${API_CONDITION}" \
  --quiet >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${WORKER_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition="title=ScriptoriumBYOKReader,description=Leitura somente das chaves individuais,expression=${WORKER_CONDITION}" \
  --quiet >/dev/null

# O publicador automático NÃO pode criar papéis ou modificar IAM.
# Recebe somente a permissão de LER a política do projeto e conferir
# condições de segurança antes do Cloud Run receber a próxima versão.
if ! gcloud iam roles describe "$AUDIT_ROLE_ID" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam roles create "$AUDIT_ROLE_ID" --project="$PROJECT_ID" \
    --title="Scriptorium BYOK audit (read-only)" \
    --description="Permite somente inspecionar o IAM do projeto antes de publicar" \
    --permissions="resourcemanager.projects.getIamPolicy" --stage=GA --quiet
else
  gcloud iam roles update "$AUDIT_ROLE_ID" --project="$PROJECT_ID" \
    --permissions="resourcemanager.projects.getIamPolicy" --stage=GA --quiet
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="projects/${PROJECT_ID}/roles/${AUDIT_ROLE_ID}" \
  --condition=None --quiet >/dev/null

echo "Concessões BYOK condicionais e leitura IAM configuradas para projeto ${PROJECT_ID}."
echo "Este é um bootstrap privilegiado único, NÃO deve ser executado no pipeline de deploy."
echo "Verifique o IAM efetivo das duas contas antes de habilitar novos pesquisadores."
echo "ATENÇÃO: uma concessão prévia de secretAccessor no nível de projeto deve ser analisada separadamente."
