#!/usr/bin/env bash
set -euo pipefail

# EXECUTAR somente no Cloud Shell do NOVO projeto, a partir da raiz do repositório.
# Exemplo: PROJECT_ID=paper-orchestra-mestrado-123 bash scripts/deploy-cloud-shell.sh
PROJECT_ID="${PROJECT_ID:?Informe PROJECT_ID do projeto NOVO, não use cormyr}"
REGION="us-east4"
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

if [[ "$PROJECT_ID" == "cormyr" ]]; then
  echo 'ERRO: não execute dentro do projeto de produção do Cormyr.' >&2; exit 2
fi
if [[ ! -f firebase.json || ! -f worker/runner.py ]]; then
  echo 'Execute da raiz do repositório.' >&2; exit 2
fi
if [[ ! -f public/config.js ]] || grep -q SUBSTITUIR public/config.js; then
  echo 'Configure public/config.js com os dados do aplicativo Web do Firebase antes de implantar.' >&2; exit 2
fi
if ! gcloud firestore databases describe --database='(default)' --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo 'Crie primeiro o Firestore Database (modo nativo) neste projeto, via console Firebase.' >&2; exit 2
fi
if ! gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' | grep -qi true; then
  echo 'Vincule este novo projeto à conta de faturamento já usada no Google Cloud.' >&2; exit 2
fi

read -r -p 'Email Google autorizado para o acesso (ex.: voce@gmail.com): ' ADMIN_EMAIL
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
    --description='PaperOrchestra - imagens do ambiente academico' --project="$PROJECT_ID"
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
for SA in "$API_SA" "$WORKER_SA"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SA" \
    --role="roles/datastore.user" --quiet >/dev/null
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --member="serviceAccount:$SA" --role="roles/storage.objectAdmin" --quiet >/dev/null
done

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
gcloud builds submit api --tag="$API_IMAGE" --project="$PROJECT_ID"
echo 'Construindo motor PaperOrchestra (inclui LaTeX, pode ser um build pesado)...'
gcloud builds submit worker --tag="$WORKER_IMAGE" --project="$PROJECT_ID" --timeout=1800

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
if command -v firebase >/dev/null 2>&1; then
  firebase deploy --only hosting,firestore:rules --project="$PROJECT_ID"
else
  echo 'Firebase CLI não encontrado: os serviços Cloud Run foram implantados, mas o Hosting NÃO está publicado.' >&2
  echo 'Instale: npm install -g firebase-tools; depois execute: firebase deploy --only hosting,firestore:rules --project='"$PROJECT_ID" >&2
  exit 3
fi
cat <<MSG

IMPLANTAÇÃO TERMINADA (se nenhum comando acima falhou).
Abra: https://${PROJECT_ID}.web.app
Faça login com: ${ADMIN_EMAIL}

Importante: habilite Google Sign-In em Firebase > Authentication > Sign-in method,
e registre o domínio ${PROJECT_ID}.web.app como autorizado, se ainda não estiver.
Adicione alerts/spend caps do novo projeto no Cloud Billing.
MSG
