#!/usr/bin/env bash
# Execute APENAS após backup agendado e bucket secundário serem verificados.
set -euo pipefail
PROJECT="${SCRIPTORIUM_PROJECT:-paperorchestra-mestrado}"
DEPLOYER="paper-orchestra-deployer@$PROJECT.iam.gserviceaccount.com"
PRINCIPAL="serviceAccount:$DEPLOYER"
BACKUP="$PROJECT-paper-backups"
SOURCE="$PROJECT-paper-storage"
API_SA="paper-orchestra-api@$PROJECT.iam.gserviceaccount.com"
WORKER_SA="paper-orchestra-worker@$PROJECT.iam.gserviceaccount.com"

gcloud firestore backups schedules list --database='(default)' --project="$PROJECT" --format=json >/tmp/paper-verify-schedules.json
python - <<'PY'
import json
data=json.load(open('/tmp/paper-verify-schedules.json'))
if isinstance(data,dict): data=data.get('backupSchedules',[])
assert any('dailyRecurrence' in x or 'daily_recurrence' in x for x in data)
assert any('weeklyRecurrence' in x or 'weekly_recurrence' in x for x in data)
print('Backup agendado verificado.')
PY
gcloud storage buckets describe "gs://$BACKUP" --project="$PROJECT" --format="value(name)" >/dev/null
gcloud storage buckets describe "gs://$SOURCE" --project="$PROJECT" --format="value(name)" >/dev/null

# A publicação Cloud Run ainda precisa de serviceAccountUser nas contas de execução,
# mas NÃO de permissão global para representar qualquer conta do projeto.
for sa in "$API_SA" "$WORKER_SA"; do
  gcloud iam service-accounts add-iam-policy-binding "$sa" \
    --member="$PRINCIPAL" --role="roles/iam.serviceAccountUser" \
    --project="$PROJECT" --quiet >/dev/null
done

# Auditoria somente leitura após revogar o papel de administração global.
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="$PRINCIPAL" --role="roles/iam.securityReviewer" --quiet >/dev/null

# Guardar os próprios privilégios atuais para auditar remoção seletiva.
gcloud projects get-iam-policy "$PROJECT" --format=json >/tmp/paper-iam-before.json

role_assigned() {
  python - "$1" <<'PY'
import json, sys
policy=json.load(open('/tmp/paper-iam-before.json'))
role=sys.argv[1]
principal="serviceAccount:paper-orchestra-deployer@${PROJECT}.iam.gserviceaccount.com"
raise SystemExit(0 if any(
    b.get('role')==role and principal in b.get('members',[]) and 'condition' not in b
    for b in policy.get('bindings',[])
) else 1)
PY
}

# Apenas privilégios TEMPORÁRIOS da instalação. Não remover funções
# indispensáveis à publicação normal (Cloud Run Admin, Cloud Build Editor,
# Firebase Hosting Admin, Firebase Rules Admin).
for role in \
  roles/datastore.backupSchedulesAdmin \
  roles/iam.serviceAccountAdmin \
  roles/serviceusage.serviceUsageAdmin \
  roles/artifactregistry.admin \
  roles/storage.admin \
  roles/iam.serviceAccountUser \
  roles/resourcemanager.projectIamAdmin
do
  if role_assigned "$role"; then
    echo "Revogando função ampla temporária $role"
    gcloud projects remove-iam-policy-binding "$PROJECT" \
      --member="$PRINCIPAL" --role="$role" --quiet >/dev/null
  fi
done

gcloud projects get-iam-policy "$PROJECT" --format=json >/tmp/paper-iam-after.json
python - <<'PY'
import json
policy=json.load(open('/tmp/paper-iam-after.json'))
principal="serviceAccount:paper-orchestra-deployer@${PROJECT}.iam.gserviceaccount.com"
danger=set(['roles/iam.serviceAccountAdmin','roles/serviceusage.serviceUsageAdmin',
'roles/artifactregistry.admin','roles/storage.admin','roles/iam.serviceAccountUser',
'roles/resourcemanager.projectIamAdmin','roles/datastore.backupSchedulesAdmin'])
remaining=[b['role'] for b in policy.get('bindings',[])
           if b['role'] in danger and principal in b.get('members',[]) and not b.get('condition')]
assert not remaining, "Funções temporárias ainda atribuídas: "+", ".join(remaining)
print('IAM mínimo verificado; funções de build, deploy e Hosting permanecem.')
PY
