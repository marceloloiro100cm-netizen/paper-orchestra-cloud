"""Aviso de saldo pré-pago esgotado na chave Gemini pessoal (BYOK).

Origem: R01 (Scriptorium). Documentação conferida em 25/11/2026
(https://ai.google.dev/gemini-api/docs/billing): no plano pré-pago, a API só
atende com saldo positivo; com saldo zerado, todas as chaves da conta de
faturamento recebem HTTP 402 RESOURCE_EXHAUSTED ("Your prepayment credits are
depleted"). Créditos do Google Cloud só são usados com a carteira pré-paga
acima de zero.

O teste da chave no cadastro (api/model_access.py) é um retrato daquele
momento. Quando uma execução esbarra no saldo, o worker:
- troca o erro em inglês por uma mensagem em português;
- marca research_credentials/{uid}.billing_alert, que a tela mostra no selo
  da conta. Cadastrar a chave de novo ou concluir uma execução com IA limpa a
  marca. Nada aqui lê ou grava a chave.
"""
from __future__ import annotations

import re

PATTERN = re.compile(r"prepay(?:ment)?\s+credits\s+are\s+depleted", re.IGNORECASE)
STATE = "prepay_depleted"
MESSAGE = ("Sua chave Gemini está sem saldo de créditos pré-pagos no Google AI Studio "
           "(erro 402 do Google). Adicione créditos em https://aistudio.google.com, "
           "em Faturamento, e tente de novo. Créditos do Google Cloud só são usados "
           "quando a carteira pré-paga está acima de zero.")


def prepay_depleted(text: str | None) -> bool:
    return bool(text and PATTERN.search(text))


def log_mentions_depleted(path, tail_bytes: int = 200_000) -> bool:
    """Procura o erro no fim do log do motor (o motor roda em outro processo)."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - tail_bytes))
            return prepay_depleted(handle.read().decode("utf-8", errors="replace"))
    except OSError:
        return False


def mark(db, uid: str, when: str) -> None:
    ref = db.collection("research_credentials").document(uid)
    snap = ref.get()
    if snap.exists and (snap.to_dict() or {}).get("status") == "active":
        ref.update({"billing_alert": {"state": STATE, "detected_at": when}})


def clear(db, uid: str, delete_field) -> None:
    ref = db.collection("research_credentials").document(uid)
    snap = ref.get()
    if snap.exists and (snap.to_dict() or {}).get("billing_alert"):
        ref.update({"billing_alert": delete_field})
