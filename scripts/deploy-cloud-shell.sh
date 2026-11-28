#!/usr/bin/env bash
set -euo pipefail

# EXECUTAR somente no Cloud Shell do NOVO projeto, a partir da raiz do repositório.
# Projeto padrão: paperorchestra-mestrado. Pode confirmar com PROJECT_ID=paperorchestra-mestrado bash scripts/deploy-cloud-shell.sh
# Instalação oficial por padrão; numa cópia do Scriptorium, defina SCRIPTORIUM_PROJECT (ver docs/IMPLANTACAO.md).
SCRIPTORIUM_PROJECT="${SCRIPTORIUM_PROJECT:-paperorchestra-mestrado}"
PROJECT_ID="${PROJECT_ID:-$SCRIPTORIUM_PROJECT}"
REGION="southamerica-east1"
# Por padrão, o worker usa Vertex AI via identidade Cloud Run (sem chaves persistentes).
# Alternativa: AI_PROVIDER=gemini_api para usar chave Gemini via Secret Manager.
AI_PROVIDER="${AI_PROVIDER:-vertex}"
if [[ "$AI_PROVIDER" != "vertex" && "$AI_PROVIDER" != "gemini_api" ]]; then
  echo 'AI_PROVIDER deve ser vertex ou gemini_api.' >&2; exit 2
fi
BUCKET="${PROJECT_ID}-paper-storage"
REPO="paper-orchestra"
API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:initial"
WORKER_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/worker:initial"
API_SA="paper-orchestra-api@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_SA="paper-orchestra-worker@${PROJECT_ID}.iam.gserviceaccount.com"

if [[ "$PROJECT_ID" != "$SCRIPTORIUM_PROJECT" ]]; then
  echo "ERRO: projeto incorreto: $PROJECT_ID. Este script só implanta em $SCRIPTORIUM_PROJECT (defina SCRIPTORIUM_PROJECT para outra instalação)." >&2; exit 2
fi
if [[ ! -f firebase.json || ! -f worker/runner.py ]]; then
  echo 'Execute da raiz do repositório.' >&2; exit 2
fi
if [[ ! -f public/config.js ]] || grep -q SUBSTITUIR public/config.js; then
  echo 'O arquivo public/config.js precisa estar configurado com os dados públicos do Firebase.' >&2; exit 2
fi
if ! grep -q "projectId: \"$PROJECT_ID\"" public/config.js; then
  echo 'ERRO: app Web aponta para outro projeto Firebase. Não é seguro prosseguir.' >&2; exit 2
fi
if ! command -v gcloud >/dev/null || ! command -v firebase >/dev/null; then
  echo 'Abra o Cloud Shell pelo console Firebase: ele já oferece gcloud e firebase CLI.' >&2; exit 2
fi
# O banco Firestore e o plano Blaze foram confirmados previamente pelo proprietário.
# A identidade CI não precisa de permissões extras de visualizador para inspecionar
# faturamento ou banco. A implantação falhará se algum serviço realmente faltar.
if [[ "${CI:-false}" != "true" ]]; then
  if ! gcloud firestore databases describe --database='(default)' --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo 'AVISO: Firestore (default) não pôde ser verificado pela identidade atual.' >&2
  fi
fi

# Via GitHub Actions, ADMIN_EMAIL chega pelo formulário de execução.
# Via terminal interativo, perguntar somente se a variável estiver vazia.
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
if [[ -z "$ADMIN_EMAIL" ]]; then
  if [[ ! -t 0 ]]; then
    echo 'Informe ADMIN_EMAIL para implantação não interativa (GitHub Actions).' >&2; exit 2
  fi
  read -r -p 'Email Google autorizado para o acesso (ex.: voce@gmail.com): ' ADMIN_EMAIL
fi
if [[ ! "$ADMIN_EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; then
  echo 'Email inválido.' >&2; exit 2
fi

echo "Projeto: $PROJECT_ID | Região: $REGION | Bucket: $BUCKET"
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com firestore.googleapis.com storage.googleapis.com \
  iam.googleapis.com aiplatform.googleapis.com --project="$PROJECT_ID"

if ! gcloud artifacts repositories describe "$REPO" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO" --repository-format=docker --location="$REGION" \
    --description='Scriptorium - imagens da API e do worker' --project="$PROJECT_ID"
fi
if ! gcloud storage buckets describe "gs://${BUCKET}" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention --project="$PROJECT_ID"
fi
for name in paper-orchestra-api paper-orchestra-worker; do
  if ! gcloud iam service-accounts describe "${name}@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --display-name="$name" --project="$PROJECT_ID"
  fi
done
# IAM/Storage propagam contas de serviço de forma eventual: logo após criar uma
# conta, o bucket pode responder "Service account ... does not exist".
# Aguardar exclusivamente esse erro transitório, sem encobrir falhas de permissão.
grant_bucket_access_with_retry() {
  local sa="$1"
  local attempt=1
  local max_attempts=10
  local output=""
  local delay=5
  while (( attempt <= max_attempts )); do
    if output="$(gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
      --member="serviceAccount:${sa}" --role="roles/storage.objectAdmin" \
      --project="$PROJECT_ID" --quiet 2>&1)"; then
      echo "Permissão de armazenamento aplicada: ${sa}"
      return 0
    fi
    if [[ "$output" != *"does not exist"* && "$output" != *"not found"* ]]; then
      echo "Falha não transitória ao autorizar ${sa}: $output" >&2
      return 1
    fi
    if (( attempt == max_attempts )); then
      echo "Conta ${sa} ainda não propagada após ${max_attempts} tentativas: $output" >&2
      return 1
    fi
    echo "Aguardando propagação IAM de ${sa} (tentativa ${attempt}/${max_attempts}; ${delay}s)..."
    sleep "$delay"
    (( attempt += 1 ))
    if (( delay < 30 )); then (( delay += 5 )); fi
  done
}

for SA in "$API_SA" "$WORKER_SA"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" \
    --role="roles/datastore.user" --quiet >/dev/null
  grant_bucket_access_with_retry "$SA"
done

# A verificação de tokens com check_revoked=True consulta o usuário no Firebase Auth.
# A conta da API precisa de leitura em Authentication, nunca de Auth Admin.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$API_SA" --role="roles/firebaseauth.viewer" \
  --quiet >/dev/null

# O motor original aceita credenciais ADC do Vertex via VERTEX_AI_PROJECT/LOCATION.
WORKER_AI_ENV="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},RESEARCH_BUCKET=${BUCKET}"
WORKER_SECRETS_FLAG=()
if [[ "$AI_PROVIDER" == "vertex" ]]; then
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$WORKER_SA" \
    --role="roles/aiplatform.user" --quiet >/dev/null
  WORKER_AI_ENV="${WORKER_AI_ENV},VERTEX_AI_PROJECT=${PROJECT_ID},VERTEX_AI_LOCATION=global"
  echo 'Vertex AI selecionado. Nenhuma chave Gemini API necessária.'
else
  if ! gcloud secrets describe paper-orchestra-gemini --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets create paper-orchestra-gemini --replication-policy=automatic --project="$PROJECT_ID"
  fi
  read -r -s -p 'Cole a chave Gemini (não será mostrada): ' GEMINI_API_KEY; echo
  if [[ -z "$GEMINI_API_KEY" ]]; then echo 'Chave vazia.' >&2; exit 2; fi
  printf '%s' "$GEMINI_API_KEY" | gcloud secrets versions add paper-orchestra-gemini --data-file=- --project="$PROJECT_ID" >/dev/null
  unset GEMINI_API_KEY
  gcloud secrets add-iam-policy-binding paper-orchestra-gemini \
    --member="serviceAccount:$WORKER_SA" --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID" --quiet >/dev/null
  WORKER_SECRETS_FLAG=(--set-secrets="GEMINI_API_KEY=paper-orchestra-gemini:latest")
fi

echo 'Construindo imagem API...'
# As imagens são construídas a partir de api/ e worker/: a pasta única formatos/ vai junto.
rm -rf api/formatos worker/formatos
cp -r formatos api/formatos
cp -r formatos worker/formatos
gcloud builds submit api --tag="$API_IMAGE" --project="$PROJECT_ID"
echo 'Construindo motor PaperOrchestra (inclui LaTeX, pode ser um build pesado)...'
gcloud builds submit worker --tag="$WORKER_IMAGE" --project="$PROJECT_ID" --timeout=1800
rm -rf api/formatos worker/formatos  # cópias temporárias; a fonte é formatos/ na raiz

# Jobs de longa duração sem request HTTP pendente.
gcloud run jobs deploy paper-orchestra-worker \
  --image="$WORKER_IMAGE" --region="$REGION" --project="$PROJECT_ID" \
  --service-account="$WORKER_SA" --memory=4Gi --cpu=2 \
  --tasks=1 --parallelism=1 --max-retries=0 --task-timeout=180m \
  --set-env-vars="$WORKER_AI_ENV" \
  "${WORKER_SECRETS_FLAG[@]}" --quiet

# Permissão restrita a ESTE Job, não aos demais projetos.
gcloud run jobs add-iam-policy-binding paper-orchestra-worker \
  --region="$REGION" --project="$PROJECT_ID" \
  --member="serviceAccount:$API_SA" --role="roles/run.jobsExecutorWithOverrides" --quiet

gcloud run deploy paper-orchestra-api \
  --image="$API_IMAGE" --region="$REGION" --project="$PROJECT_ID" \
  --service-account="$API_SA" --memory=512Mi --cpu=1 \
  --min-instances=0 --max-instances=2 --concurrency=20 \
  --allow-unauthenticated --ingress=all \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},REGION=${REGION},RESEARCH_BUCKET=${BUCKET},ALLOWED_EMAILS=${ADMIN_EMAIL}" \
  --quiet

# As regras nunca permitem ao navegador ler Firestore sem autenticação pelo backend.
firebase deploy --only hosting,firestore:rules --project="$PROJECT_ID"
cat <<MSG

IMPLANTAÇÃO TERMINADA (se nenhum comando acima falhou).
Abra: https://${PROJECT_ID}.web.app
Faça login com: ${ADMIN_EMAIL}

Importante: habilite Google Sign-In em Firebase > Authentication > Sign-in method,
e registre o domínio ${PROJECT_ID}.web.app como autorizado, se ainda não estiver.
Adicione alerts/spend caps do novo projeto no Cloud Billing.
MSG
