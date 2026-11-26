"""Guia de escrita: guarda o estado do guia de cada pessoa no bucket.

O guia roda no navegador (public/guia). Estas rotas só guardam e devolvem o JSON
que a pessoa preencheu, sem IA e sem ler o conteúdo além de conferir o formato.
Arquivos: guia/{uid}/estado.json e uma cópia por dia em guia/{uid}/historico/AAAA-MM-DD.json.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Body, Depends, HTTPException, Query

try:
    from google.api_core.exceptions import NotFound, PreconditionFailed
except Exception:  # pragma: no cover - testes sem google-api-core completo
    NotFound = PreconditionFailed = ()

MAX_BYTES = 3 * 1024 * 1024
HISTORY_THROTTLE_SECONDS = 900  # 15 min: evita gravar 2 objetos inteiros a cada tecla


def state_path(uid: str) -> str:
    return f"guia/{uid}/estado.json"


def history_path(uid: str, day: str) -> str:
    return f"guia/{uid}/historico/{day}.json"


def check_state(state) -> dict:
    """Confere o formato mínimo do estado do guia e devolve o próprio estado."""
    if not isinstance(state, dict) or state.get("schema") != 2:
        raise HTTPException(422, "Formato do guia não reconhecido (schema 2 esperado).")
    for key in ("values", "records", "criteria"):
        if key in state and not isinstance(state[key], dict):
            raise HTTPException(422, f"Campo '{key}' do guia em formato inválido.")
    if state.get("tipo", "artigo") not in ("artigo", "projeto"):
        raise HTTPException(422, "Tipo de trabalho inválido.")
    changed = state.get("changedAt", 0)
    if not isinstance(changed, (int, float)) or changed < 0:
        raise HTTPException(422, "Data de alteração inválida.")
    return state


def make_guide_router(bucket, verify_user: Callable, today: Callable[[], str] | None = None):
    router = APIRouter(prefix="/api/guia", tags=["guia"])
    dependency = Depends(verify_user)
    day = today or (lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    last_history: dict[tuple[str, str], float] = {}

    def read_with_generation(uid: str) -> tuple[dict | None, int | None]:
        blob = bucket.blob(state_path(uid))
        try:
            raw = blob.download_as_bytes()
        except (NotFound, KeyError, FileNotFoundError):
            return None, 0
        gen = getattr(blob, "generation", None)
        return json.loads(raw), gen

    @router.get("/estado")
    def get_state(user: dict = dependency):
        state, _ = read_with_generation(user["uid"])
        return {"estado": state, "changedAt": (state or {}).get("changedAt", 0)}

    @router.put("/estado")
    def put_state(state: dict = Body(...), base: float = Query(0, ge=0),
                  forcar: bool = Query(False), user: dict = dependency):
        check_state(state)
        raw = json.dumps(state, ensure_ascii=False).encode("utf-8")
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "O guia passou de 3 MB. Exporte um backup e apague versões antigas.")
        uid = user["uid"]
        current, gen = read_with_generation(uid)
        stored = (current or {}).get("changedAt", 0)
        if current is not None and not forcar and stored > base:
            raise HTTPException(409, {"mensagem": "O guia foi alterado em outro dispositivo.",
                                      "changedAt": stored})
        target = bucket.blob(state_path(uid))
        # Escrita condicional atômica (GCS generation match) evita sobrescrita silenciosa em corrida.
        try:
            if not forcar and gen is not None:
                target.upload_from_string(raw, content_type="application/json", if_generation_match=gen)
            else:
                target.upload_from_string(raw, content_type="application/json")
        except TypeError:
            # Blobs de teste simples que não aceitam if_generation_match.
            target.upload_from_string(raw, content_type="application/json")
        except PreconditionFailed:
            latest, _ = read_with_generation(uid)
            raise HTTPException(409, {
                "mensagem": "O guia foi alterado em outro dispositivo ao mesmo tempo.",
                "changedAt": (latest or {}).get("changedAt", stored),
            }) from None
        today_key = (uid, day())
        now_ts = time.monotonic()
        if now_ts - last_history.get(today_key, 0.0) >= HISTORY_THROTTLE_SECONDS or today_key not in last_history:
            bucket.blob(history_path(uid, today_key[1])).upload_from_string(raw, content_type="application/json")
            if len(last_history) > 512:
                last_history.clear()
            last_history[today_key] = now_ts
        return {"salvo": True, "changedAt": state.get("changedAt", 0), "bytes": len(raw)}

    return router
