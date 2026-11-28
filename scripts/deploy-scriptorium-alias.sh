#!/usr/bin/env bash
# Cria e publica APENAS o site Firebase Hosting "scriptoriummpie" no projeto existente.
# Nunca renomeia, desativa ou publica no site padrão paperorchestra-mestrado.
set -euo pipefail

PROJECT="${SCRIPTORIUM_PROJECT:-paperorchestra-mestrado}"
SITE_ID="${SCRIPTORIUM_SITE:-scriptoriummpie}"
TARGET="scriptoriummpie-alias"

if [[ "${GOOGLE_CLOUD_PROJECT:-$PROJECT}" != "$PROJECT" ]]; then
  echo "Projeto Google Cloud inesperado; operação cancelada." >&2
  exit 2
fi
command -v firebase >/dev/null || { echo "Firebase CLI indisponível." >&2; exit 2; }
command -v python3 >/dev/null || { echo "Python 3 indisponível." >&2; exit 2; }

echo "Consultando sites Firebase Hosting do projeto $PROJECT (sem tocar no site padrão)..."
SITES_JSON="$(mktemp)"
TEMP_CONFIG="$(mktemp --suffix=.json "./firebase-scriptorium.XXXXXX")"
trap 'rm -f "$SITES_JSON" "$TEMP_CONFIG"' EXIT

firebase hosting:sites:list --project "$PROJECT" --json > "$SITES_JSON"
if python3 - "$SITES_JSON" "$SITE_ID" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
if data.get("status") != "success":
    print("Não foi possível confirmar a listagem do Firebase Hosting", file=sys.stderr)
    raise SystemExit(2)
result = data.get("result", [])
if isinstance(result, dict):
    result = result.get("sites", [])
if not isinstance(result, list):
    print("Formato inesperado da listagem Hosting", file=sys.stderr)
    raise SystemExit(2)
site = sys.argv[2]
found = any(isinstance(item, dict) and (
    item.get("name", "").endswith("/sites/" + site)
    or item.get("name") == site
    or item.get("siteId") == site
    or item.get("site_id") == site
) for item in result)
raise SystemExit(0 if found else 1)
PY
then
  echo "O site scriptoriummpie já está registrado neste projeto. Reutilizando."
else
  status=$?
  if [[ "$status" != "1" ]]; then
    echo "Listagem Hosting não confiável: abortando sem criar sites." >&2
    exit "$status"
  fi
  echo "Tentando registrar o nome global scriptoriummpie.web.app..."
  # Se já pertencer a outra pessoa ou faltar IAM, o comando falha.
  # NÃO escolher nome alternativo automaticamente.
  firebase hosting:sites:create "$SITE_ID" --project "$PROJECT" --non-interactive
fi

# Alvo de deploy gerado apenas na execução do CI. Não modifica o alvo padrão.
firebase target:apply hosting "$TARGET" "$SITE_ID" --project "$PROJECT"

python3 - "$TEMP_CONFIG" <<'PY'
import json, sys
with open("firebase.json", encoding="utf-8") as f:
    config = json.load(f)
original = config.get("hosting")
if not isinstance(original, dict):
    raise SystemExit("Configuração Hosting principal inesperada: abortando alias")
if original.get("rewrites", [{}])[0].get("run", {}).get("serviceId") != "paper-orchestra-api":
    raise SystemExit("Rewrite da API não corresponde ao Scriptorium; abortando")
copy = dict(original)
copy["target"] = "scriptoriummpie-alias"
# Configuração temporária do site secundário: preserva headers e /api/**.
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({"hosting": copy}, f, ensure_ascii=False, indent=2)
PY

echo "Publicando somente no site scriptoriummpie; endereço antigo preservado."
firebase deploy --only "hosting:$TARGET" --config "$TEMP_CONFIG" --project "$PROJECT" --non-interactive

echo "Verificando arquivos públicos do novo domínio..."
for attempt in 1 2 3 4 5 6 7 8; do
  curl --fail --silent --show-error --max-time 15 \
    -o /tmp/scriptorium-live-index.html \
    "https://scriptoriummpie.web.app/index.html?revision=${GITHUB_SHA:-manual}" || true
  curl --fail --silent --show-error --max-time 15 \
    -o /tmp/scriptorium-live-app.js \
    "https://scriptoriummpie.web.app/app.js?revision=${GITHUB_SHA:-manual}" || true
  curl --fail --silent --show-error --max-time 15 \
    -o /tmp/scriptorium-live-config.js \
    "https://scriptoriummpie.web.app/config.js?revision=${GITHUB_SHA:-manual}" || true
  if cmp -s public/index.html /tmp/scriptorium-live-index.html \
    && cmp -s public/app.js /tmp/scriptorium-live-app.js \
    && cmp -s public/config.js /tmp/scriptorium-live-config.js; then
    echo "CONFIRMADO: mesmo HTML, JS e Firebase config no novo domínio."
    exit 0
  fi
  sleep 5
done
echo "ERRO: não foi possível confirmar a publicação do alias." >&2
exit 1
