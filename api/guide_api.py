"""Guia de escrita: guarda o estado do guia de cada pessoa no bucket.

O guia roda no navegador (public/guia). Estas rotas só guardam e devolvem o JSON
que a pessoa preencheu, sem IA e sem ler o conteúdo além de conferir o formato.
Arquivos: guia/{uid}/estado.json e uma cópia por dia em guia/{uid}/historico/AAAA-MM-DD.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Body, Depends, HTTPException, Query

MAX_BYTES = 3 * 1024 * 1024


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

    def read(uid: str):
        blob = bucket.blob(state_path(uid))
        if not blob.exists():
            return None
        return json.loads(blob.download_as_bytes())

    @router.get("/estado")
    def get_state(user: dict = dependency):
        state = read(user["uid"])
        return {"estado": state, "changedAt": (state or {}).get("changedAt", 0)}

    @router.put("/estado")
    def put_state(state: dict = Body(...), base: float = Query(0, ge=0),
                  forcar: bool = Query(False), user: dict = dependency):
        check_state(state)
        raw = json.dumps(state, ensure_ascii=False).encode("utf-8")
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "O guia passou de 3 MB. Exporte um backup e apague versões antigas.")
        uid = user["uid"]
        current = read(uid)
        stored = (current or {}).get("changedAt", 0)
        if current is not None and not forcar and stored > base:
            raise HTTPException(409, {"mensagem": "O guia foi alterado em outro dispositivo.",
                                      "changedAt": stored})
        bucket.blob(state_path(uid)).upload_from_string(raw, content_type="application/json")
        bucket.blob(history_path(uid, day())).upload_from_string(raw, content_type="application/json")
        return {"salvo": True, "changedAt": state.get("changedAt", 0), "bytes": len(raw)}

    return router
