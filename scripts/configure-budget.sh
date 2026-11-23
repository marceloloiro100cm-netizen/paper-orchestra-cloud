#!/usr/bin/env bash
# Alertas de orçamento, não bloqueio automático de gastos.
set -euo pipefail
PROJECT="paperorchestra-mestrado"
BUDGET_AMOUNT="50"
BUDGET_NAME="PaperOrchestra Mestrado - alerta mensal"
ACCOUNT="$(gcloud beta billing projects describe "$PROJECT" --format='value(billingAccountName)' 2>/dev/null || true)"
if [[ -z "$ACCOUNT" || "$ACCOUNT" == "None" ]]; then
  echo "::warning::Orçamento pendente: conta de faturamento não pôde ser consultada pela identidade do GitHub."
  exit 0
fi
ACCOUNT_ID="$(basename "$ACCOUNT")"
if ! gcloud beta billing budgets list --billing-account="$ACCOUNT_ID" --format=json > /tmp/paper-budgets.json 2>/dev/null; then
  echo "::warning::Orçamento pendente: faltam permissões de orçamentos na conta de faturamento."
  exit 0
fi
if python - <<'PY'
import json
budgets=json.load(open('/tmp/paper-budgets.json'))
if isinstance(budgets,dict): budgets=budgets.get('budgets',[])
print("Orçamentos visíveis nesta conta:", len(budgets))
raise SystemExit(0 if any(b.get('displayName')=='PaperOrchestra Mestrado - alerta mensal' for b in budgets) else 1)
PY
then
  echo "Orçamento mensal existente; nenhuma alteração realizada."
else
  if ! gcloud beta billing budgets create \
      --billing-account="$ACCOUNT_ID" \
      --display-name="$BUDGET_NAME" \
      --budget-amount="$BUDGET_AMOUNT" \
      --calendar-period=month \
      --filter-projects="projects/$PROJECT" \
      --threshold-rule=percent=0.50 \
      --threshold-rule=percent=0.80 \
      --threshold-rule=percent=1.00 \
      --quiet; then
    echo "::warning::A criação do orçamento requer permissões na conta de faturamento. Configure-o no console."
    exit 0
  fi
  echo "Alertas mensais criados: 50%, 80% e 100% de 50 unidades da moeda da conta."
fi
echo "AVISO: orçamento e alertas não interrompem cobranças. Destinatários padrão são os usuários com IAM de faturamento."
