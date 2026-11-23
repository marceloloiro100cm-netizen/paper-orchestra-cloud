#!/usr/bin/env bash
set -euo pipefail
PROJECT="paperorchestra-mestrado"
REGION="southamerica-east1"
SOURCE="$PROJECT-paper-storage"
DEST="$PROJECT-paper-backups"
DEPLOYER="paper-orchestra-deployer@$PROJECT.iam.gserviceaccount.com"
PRINCIPAL="serviceAccount:$DEPLOYER"

if [[ "$(gcloud config get-value project 2>/dev/null)" != "$PROJECT" ]]; then
  gcloud config set project "$PROJECT" --quiet >/dev/null
fi
gcloud storage buckets describe "gs://$SOURCE" --project="$PROJECT" --format="value(name)" >/dev/null
echo "Configurando proteção exclusivamente para $PROJECT."

gcloud storage buckets describe "gs://$SOURCE" --format=json > /tmp/paper-source-bucket.json
if python - <<'PY'
import json, re
bucket=json.load(open('/tmp/paper-source-bucket.json'))
soft=bucket.get('softDeletePolicy') or bucket.get('soft_delete_policy') or {}
period=str(soft.get('retentionDuration') or soft.get('retention_duration') or '0s')
match=re.match(r'\d+', period)
seconds=int(match.group(0)) if match else 0
raise SystemExit(0 if seconds < 14*86400 else 1)
PY
then
  gcloud storage buckets update "gs://$SOURCE" --soft-delete-duration=1209600s --project="$PROJECT" --quiet
fi
echo "Proteção contra exclusão acidental no bucket principal verificada."

if ! gcloud storage buckets describe "gs://$DEST" --project="$PROJECT" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$DEST" \
    --location="$REGION" --uniform-bucket-level-access \
    --public-access-prevention --soft-delete-duration=1209600s \
    --project="$PROJECT" --quiet
fi
gcloud storage buckets describe "gs://$DEST" --project="$PROJECT" --format="value(name)" >/dev/null
echo "Bucket privado de backup disponível: gs://$DEST"

gcloud storage buckets add-iam-policy-binding "gs://$SOURCE" \
  --member="$PRINCIPAL" --role="roles/storage.objectViewer" --quiet >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$DEST" \
  --member="$PRINCIPAL" --role="roles/storage.objectAdmin" --quiet >/dev/null

# Permite ler metadados dos buckets após remover Storage Admin global.
for storage_bucket in "$SOURCE" "$DEST"; do
  gcloud storage buckets add-iam-policy-binding "gs://$storage_bucket" \
    --member="$PRINCIPAL" --role="roles/storage.legacyBucketReader" --quiet >/dev/null
done

# Concessão de backup agendado, temporária até a redução final de IAM.
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="$PRINCIPAL" --role="roles/datastore.backupSchedulesAdmin" --quiet >/dev/null

gcloud firestore backups schedules list --database='(default)' \
  --project="$PROJECT" --format=json > /tmp/paper-firestore-schedules.json
read -r DAILY WEEKLY < <(python - <<'PY'
import json
items=json.load(open('/tmp/paper-firestore-schedules.json'))
if isinstance(items, dict): items=items.get('backupSchedules', [])
daily=any('dailyRecurrence' in item or 'daily_recurrence' in item for item in items)
weekly=any('weeklyRecurrence' in item or 'weekly_recurrence' in item for item in items)
print(int(daily), int(weekly))
PY
)
if [[ "$DAILY" != 1 ]]; then
  gcloud firestore backups schedules create --database='(default)' \
    --recurrence=daily --retention=7d --project="$PROJECT" --quiet
fi
if [[ "$WEEKLY" != 1 ]]; then
  gcloud firestore backups schedules create --database='(default)' \
    --recurrence=weekly --day-of-week=SUN --retention=12w --project="$PROJECT" --quiet
fi
gcloud firestore backups schedules list --database='(default)' \
  --project="$PROJECT" --format=json > /tmp/paper-firestore-schedules-after.json
python - <<'PY'
import json
items=json.load(open('/tmp/paper-firestore-schedules-after.json'))
if isinstance(items, dict): items=items.get('backupSchedules', [])
assert any('dailyRecurrence' in i or 'daily_recurrence' in i for i in items), "Backup diário ausente"
assert any('weeklyRecurrence' in i or 'weekly_recurrence' in i for i in items), "Backup semanal ausente"
print("Firestore: cronogramas diário e semanal confirmados.")
PY

# Cópia ADITIVA ao segundo bucket: nunca utilizar --delete.
gcloud storage rsync --recursive "gs://$SOURCE" "gs://$DEST"
echo "Cópia inicial dos documentos concluída."
