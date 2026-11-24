"""Detecção de acesso efetivo aos modelos Gemini para chaves individuais BYOK.

A consulta models.list apenas valida a chave; o catálogo NÃO comprova acesso pago.
Uma geração mínima e limitada por modelo comprova o acesso no momento do teste.
Não registrar nem persistir chaves neste módulo. Nenhuma leitura de Secret Manager
é necessária na API, pois a checagem ocorre somente quando o usuário envia a chave.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

FLASH_MODEL = "gemini-3-flash-preview"
PRO_MODEL = "gemini-3.1-pro-preview"
SUPPORTED_MODELS = (FLASH_MODEL, PRO_MODEL)
API_HOST = "https://generativelanguage.googleapis.com/v1beta"
PROBE_TIMEOUT_SECONDS = 12


def _query_google(url: str, api_key: str, payload: dict | None = None) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url, data=body, method="GET" if body is None else "POST",
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
            raw = response.read(2_000_000)
            return response.status, json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as exc:
        # Não incluir resposta/headers/exceções do Google em logs: podem conter
        # informação sensível ou material do usuário.
        return exc.code, {}
    except (URLError, TimeoutError, OSError, ValueError):
        return 0, {}


def classify_probe_status(status_code: int) -> str:
    if status_code == 200:
        return "supported"
    if status_code == 429:
        return "limited"  # Não confundir limite temporário com falta de plano.
    if status_code in (400, 401, 403, 404):
        return "unavailable"
    return "unknown"


def validate_key_and_models(key: str, *, transport=None) -> dict:
    """Confere credencial e ambos os modelos com no máximo três requisições.

    Duas gerações mínimas podem causar consumo pequeno da Gemini API.
    Não determina modalidade de assinatura ou faturamento do usuário.
    """
    query = transport or _query_google
    code, catalog = query(f"{API_HOST}/models?pageSize=1000", key)
    if code in (400, 401, 403):
        raise ValueError("Chave recusada pelo Google. Confira a chave no Google AI Studio.")
    if code != 200 or not isinstance(catalog, dict):
        raise ConnectionError("Não foi possível verificar a chave no Google. Tente novamente.")
    results = {}
    test_payload = {
        "contents": [{"role": "user", "parts": [{"text": "Responda OK."}]}],
        "generationConfig": {"maxOutputTokens": 16},
    }
    for model in SUPPORTED_MODELS:
        status_code, _ = query(
            f"{API_HOST}/models/{model}:generateContent", key, test_payload
        )
        results[model] = classify_probe_status(status_code)
    return {
        "status": "verified" if "supported" in results.values() else "needs_attention",
        "models": results,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "method": "short_generate_content_probe",
    }


def account_model_access(db, uid: str) -> dict:
    """Metadados seguros, sem chave; falha de lookup não vira autorização Pro."""
    snap = db.collection("research_credentials").document(uid).get()
    doc = snap.to_dict() if snap.exists else {}
    if doc.get("status") != "active":
        return {"status": "no_key", "models": {}, "verified_models": []}
    profile = doc.get("model_access")
    if not isinstance(profile, dict):
        # Chaves antigas podem permanecer no Secret Manager, mas não geram
        # permissões até o pesquisador refazer o teste com sua própria chave.
        return {"status": "legacy_unverified", "models": {FLASH_MODEL: "not_verified"},
                "verified_models": []}
    statuses = profile.get("models", {})
    permitted = [m for m in SUPPORTED_MODELS if statuses.get(m) == "supported"]
    return {
        "status": profile.get("status", "needs_attention"),
        "models": {m: statuses.get(m, "unknown") for m in SUPPORTED_MODELS},
        "verified_models": permitted,
        "checked_at": profile.get("checked_at", ""),
    }


def allowed_models(model_access: dict) -> list[str]:
    """Modelo não testado nunca é concedido apenas por haver chave cadastrada."""
    return [m for m in SUPPORTED_MODELS if m in model_access.get("verified_models", ())]
