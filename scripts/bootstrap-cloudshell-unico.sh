#!/usr/bin/env bash
# EXECUÇÃO ÚNICA NO CLOUD SHELL COM CONTA ADMINISTRADORA.
# Reúne os scripts oficiais do repositório no commit desta versão.
# Não contém nem lê nenhuma chave Gemini.
set -euo pipefail
echo "Scriptorium BYOK: bootstrap privilegiado e auditoria segura"
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

gcloud services enable secretmanager.googleapis.com --project="$PROJECT_ID" --quiet
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
echo "Scriptorium BYOK: iniciando auditoria somente leitura"
# Auditoria somente leitura; nunca imprime ou busca payload de segredos.
set -euo pipefail
# Instalação oficial por padrão; numa cópia do Scriptorium, defina SCRIPTORIUM_PROJECT (ver docs/IMPLANTACAO.md).
SCRIPTORIUM_PROJECT="${SCRIPTORIUM_PROJECT:-paperorchestra-mestrado}"
PROJECT_ID="${PROJECT_ID:-$SCRIPTORIUM_PROJECT}"
if [[ "$PROJECT_ID" != "$SCRIPTORIUM_PROJECT" ]]; then
  echo "Projeto não autorizado: $PROJECT_ID" >&2; exit 2
fi
command -v gcloud >/dev/null || { echo "gcloud ausente" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 ausente" >&2; exit 2; }
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --project="$PROJECT_ID" --format='value(projectNumber)')"
if [[ ! "$PROJECT_NUMBER" =~ ^[0-9]+$ ]]; then echo "Número de projeto inválido" >&2; exit 2; fi
API_SA="serviceAccount:paper-orchestra-api@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_SA="serviceAccount:paper-orchestra-worker@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOYER_SA="serviceAccount:paper-orchestra-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
POLICY="$(mktemp)"
trap 'rm -f "$POLICY"' EXIT
gcloud projects get-iam-policy "$PROJECT_ID" --format=json > "$POLICY"
python3 - "$POLICY" "$PROJECT_ID" "$PROJECT_NUMBER" "$API_SA" "$WORKER_SA" "$DEPLOYER_SA" <<'PY'
import json
import sys

path, project, number, api, worker, deployer = sys.argv[1:]
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

# Pipeline automático só pode ler a política IAM, não modificar papéis nem
# conceder acesso a segredos. Exigir o papel personalizado criado no bootstrap.
auditor_role = "projects/" + project + "/roles/scriptoriumByokAuditor"
if not any(binding.get("role") == auditor_role
           and deployer in binding.get("members", [])
           for binding in bindings):
    problems.append("Deployer sem auditoria IAM de leitura. Execute o bootstrap único.")

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
echo "Scriptorium BYOK: bootstrap concluído e auditado"
