#!/usr/bin/env bash
# Auditoria somente leitura; nunca imprime ou busca payload de segredos.
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-paperorchestra-mestrado}"
if [[ "$PROJECT_ID" != "paperorchestra-mestrado" ]]; then
  echo "Projeto não autorizado: $PROJECT_ID" >&2; exit 2
fi
command -v gcloud >/dev/null || { echo "gcloud ausente" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 ausente" >&2; exit 2; }
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --project="$PROJECT_ID" --format='value(projectNumber)')"
if [[ ! "$PROJECT_NUMBER" =~ ^[0-9]+$ ]]; then echo "Número de projeto inválido" >&2; exit 2; fi
API_SA="serviceAccount:paper-orchestra-api@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_SA="serviceAccount:paper-orchestra-worker@${PROJECT_ID}.iam.gserviceaccount.com"
POLICY="$(mktemp)"
trap 'rm -f "$POLICY"' EXIT
gcloud projects get-iam-policy "$PROJECT_ID" --format=json > "$POLICY"
python3 - "$POLICY" "$PROJECT_ID" "$PROJECT_NUMBER" "$API_SA" "$WORKER_SA" <<'PY'
import json
import sys

path, project, number, api, worker = sys.argv[1:]
with open(path, encoding="utf-8") as handle:
    policy = json.load(handle)
bindings = policy.get("bindings", [])
problems = []
expected = {
    api: ("projects/" + project + "/roles/scriptoriumByokWriter", "ScriptoriumBYOKWriter"),
    worker: ("roles/secretmanager.secretAccessor", "ScriptoriumBYOKReader"),
}
prefix = "projects/" + number + "/secrets/scriptorium-byok-"
for member, (role, title) in expected.items():
    matches = [binding for binding in bindings
               if member in binding.get("members", [])
               and binding.get("role") == role
               and binding.get("condition", {}).get("title") == title]
    valid = any(prefix in binding["condition"].get("expression", "")
                and "resource.name.startsWith" in binding["condition"].get("expression", "")
                for binding in matches)
    if not valid:
        problems.append("Ausência de IAM condicionado para " + title)

# Examinar bindings sem condição, ou com condição diferente da configuração BYOK.
high_risk_roles = {
    "roles/owner", "roles/editor", "roles/secretmanager.admin",
    "roles/secretmanager.secretAccessor", "roles/secretmanager.secretVersionManager",
    "roles/secretmanager.secretVersionAdder", "roles/secretmanager.secretVersionManager",
}
for binding in bindings:
    members = set(binding.get("members", []))
    for member in (api, worker):
        if member not in members:
            continue
        role = binding.get("role", "")
        condition = binding.get("condition", {})
        if role in high_risk_roles or role.endswith("/scriptoriumByokWriter"):
            expression = condition.get("expression", "")
            # Project-level unrestricted access is never accepted.
            if not (prefix in expression and "resource.name.startsWith" in expression):
                problems.append("Permissão sensível irrestrita/inesperada para "
                                + ("API" if member == api else "worker") + ": " + role)

if problems:
    print("AUDITORIA BYOK: INCOMPLETA")
    for issue in dict.fromkeys(problems):
        print(" - " + issue)
    sys.exit(1)
print("AUDITORIA BYOK: permissões condicionais esperadas presentes.")
print("AVISO: ainda é necessária a verificação de permissões herdadas e teste real.")
PY
