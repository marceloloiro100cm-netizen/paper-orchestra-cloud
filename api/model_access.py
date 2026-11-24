"""Verificação conservadora da chave Gemini BYOK por pesquisador.

O catálogo /models não comprova direito de executar: somente um generateContent
mínimo bem-sucedido concede permissão a um modelo. Nunca armazenar ou registrar
chaves ou respostas de erro da API externa.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib import error, parse, request

SUPPORTED_MODELS = ("gemini-3-flash-preview", "gemini-3.1-pro-preview")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
HTTP_TIMEOUT_SECONDS = 8


def _request(method: str, path: str, key: str, payload: dict | None = None) -> tuple[int, dict]:
    url = BASE_URL + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"x-goog-api-key": key, "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
            raw = response.read(512_000)
            try:
                return response.status, json.loads(raw) if raw else {}
            except (ValueError, UnicodeDecodeError):
                return response.status, {}
    except error.HTTPError as exc:
        # Os detalhes de erros externos podem conter dados; não repassá-los a logs/UI.
        return exc.code, {}
    except (error.URLError, TimeoutError, OSError):
        return 503, {}


def verify_key_models(key: str, *, transport=None) -> dict:
    """Prova individualmente cada modelo; 429 NÃO equivale a modalidade gratuita.

    Pode fazer até duas chamadas pequenas de geração (potencialmente cobradas).
    Execução somente ao salvar a chave, não a cada carregamento da página.
    """
    call = transport or _request
    found = set()
    page_token = ""
    list_status = 200
    for _ in range(5):
        qs = "?pageSize=100"
        if page_token:
            qs += "&" + parse.urlencode({"pageToken": page_token})
        code, response = call("GET", "/models" + qs, key, None)
        if code != 200:
            list_status = code
            break
        if not isinstance(response, dict):
            list_status = 503
            break
        for item in response.get("models", []):
            if not isinstance(item, dict):
                continue
            name = item.get("name", "")
            methods = item.get("supportedGenerationMethods", [])
            if name.startswith("models/") and "generateContent" in methods:
                found.add(name.partition("/")[2])
        page_token = response.get("nextPageToken", "")
        if not page_token:
            break
    elif page_token:
        # Não inferir indisponibilidade com listagem incompleta.
        list_status = 503

    states = {}
    verified = []
    if list_status != 200:
        overall = "invalid_key" if list_status in (400, 401, 403) else "verification_unavailable"
        for model in SUPPORTED_MODELS:
            states[model] = "not_verified"
    else:
        overall = "verified"
        for model in SUPPORTED_MODELS:
            if model not in found:
                states[model] = "not_listed"
                continue
            payload = {
                "contents": [{"parts": [{"text": "Responda apenas OK."}]}],
                "generationConfig": {"maxOutputTokens": 8},
            }
            code, _ = call("POST", "/models/" + model + ":generateContent", key, payload)
            if code == 200:
                states[model] = "available"
                verified.append(model)
            elif code == 429:
                states[model] = "quota_limited"
            elif code in (400, 401, 403, 404):
                states[model] = "not_authorized"
            else:
                states[model] = "verification_unavailable"
        if not verified:
            overall = "no_models_verified"

    return {
        "status": overall,
        "allowed_models": verified,
        "model_status": states,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_model_capabilities(db, uid: str) -> dict:
    """Retorna exclusivamente metadados vinculados ao UID, jamais o segredo."""
    empty = {"status": "not_connected", "allowed_models": [], "model_status": {}, "checked_at": ""}
    if not isinstance(uid, str) or not uid:
        return empty
    snap = db.collection("research_credentials").document(uid).get()
    if not snap.exists:
        return empty
    record = snap.to_dict() or {}
    if record.get("status") != "active":
        return empty
    reported = record.get("model_access") or {}
    allowed = [model for model in SUPPORTED_MODELS if model in reported.get("allowed_models", [])]
    return {
        "status": reported.get("status", "not_verified"),
        "allowed_models": allowed,
        "model_status": {
            model: reported.get("model_status", {}).get(model, "not_verified")
            for model in SUPPORTED_MODELS
        },
        "checked_at": reported.get("checked_at", ""),
    }
