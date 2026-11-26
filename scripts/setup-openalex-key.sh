#!/usr/bin/env bash
# Guarda a chave do OpenAlex no Secret Manager e a entrega ao worker.
#
# Por quê: desde 13/02/2026 o OpenAlex exige chave (gratuita) em todas as chamadas.
# Sem ela o orçamento diário é só de teste e as buscas de metadados das fontes são
# recusadas, o que faz referências caírem em "a conferir".
#
# Como obter a chave: crie uma conta em https://openalex.org e copie a chave em
# https://openalex.org/settings/api
#
# Rodar UMA vez, como administrador, no Cloud Shell do projeto:
#   PROJECT_ID=paperorchestra-mestrado bash scripts/setup-openalex-key.sh
# Para trocar a chave depois, rode de novo: uma nova versão do segredo é criada.
# O deploy automático (deploy-services.yml) só troca a imagem e preserva o segredo.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Defina PROJECT_ID, por exemplo paperorchestra-mestrado}"
REGION="${REGION:-southamerica-east1}"
SECRET="scriptorium-openalex"
WORKER_SA="paper-orchestra-worker@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud secrets describe "$SECRET" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud secrets create "$SECRET" --replication-policy=automatic --project="$PROJECT_ID"
fi
read -r -s -p 'Cole a chave do OpenAlex (não será mostrada): ' OPENALEX_API_KEY; echo
if [[ -z "$OPENALEX_API_KEY" ]]; then echo 'Chave vazia.' >&2; exit 2; fi
printf '%s' "$OPENALEX_API_KEY" | gcloud secrets versions add "$SECRET" --data-file=- --project="$PROJECT_ID" >/dev/null
unset OPENALEX_API_KEY

gcloud secrets add-iam-policy-binding "$SECRET" \
  --member="serviceAccount:${WORKER_SA}" --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" --quiet >/dev/null

gcloud run jobs update paper-orchestra-worker \
  --update-secrets="OPENALEX_API_KEY=${SECRET}:latest" \
  --region="$REGION" --project="$PROJECT_ID" --quiet

echo "Chave do OpenAlex guardada em ${SECRET} e ligada ao worker."
echo "Confira o saldo diário em: https://api.openalex.org/rate-limit?api_key=SUA_CHAVE (no navegador, não no log)."
