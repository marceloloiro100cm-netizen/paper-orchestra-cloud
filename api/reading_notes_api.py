"""Fichamento por IA sob demanda (M21): rotas da API.

Origem: R01 (Scriptorium); modelo Gemini (R35, SDK google-genai) na chave de
quem pede. Plano V2, módulo M21 "Fichamentos persistentes e cache": cache por
modelo e política. IN IFRS 16/2026, Art. 6º, III: "resumo e leitura assistida
de artigos científicos" é uso permitido com declaração e autorização.

Fluxo:
1. POST /api/library/items/{id}/ai-notes: se já existe fichamento em cache para
   o mesmo conteúdo (SHA-256), modelo e política, devolve sem custo; senão cria
   um registro em research_jobs com mode="reading_notes" (fora da lista de
   pesquisas e da trava de "uma pesquisa por vez") e inicia o worker;
2. GET /api/library/items/{id}/ai-notes: devolve o fichamento ou o andamento.

O fichamento é gerado pelo worker (worker/reading_notes.py), com a mesma
identidade de IA da conta: chave Gemini pessoal, nunca o projeto, salvo a
exceção explícita do administrador.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from job_state import ACTIVE_STATUSES, reconcile

NOTES_MODEL = "gemini-3-flash-preview"
NOTES_POLICY = "notes-1"
FORMATS = {"pdf", "docx", "txt"}


def notes_namespace(model: str = NOTES_MODEL) -> str:
    safe = "".join(c if c.isalnum() or c == "-" else "-" for c in model.lower())
    return f"notes-{safe}-{NOTES_POLICY}"


def find_cached(bucket, owner_uid: str, sha: str, model: str = NOTES_MODEL):
    """Fichamento em cache para este conteúdo, modelo e política (qualquer parser)."""
    prefix = f"library/{owner_uid}/derived/{notes_namespace(model)}/"
    for blob in bucket.list_blobs(prefix=prefix):
        if blob.name.endswith(f"/{sha}.json"):
            return blob
    return None


def make_reading_notes_router(db, bucket, verify_user: Callable, get_access_for_notes: Callable,
                              start_job: Callable):
    router = APIRouter(prefix="/api/library/items", tags=["fichamento"])
    dependency = Depends(verify_user)

    def owned_item(item_id: str, uid: str) -> dict:
        if not re.fullmatch(r"[0-9a-f]{32}", item_id):
            raise HTTPException(404, "Arquivo não encontrado.")
        snap = db.collection("library_items").document(item_id).get()
        item = snap.to_dict() if snap.exists else None
        if not item or item.get("owner_uid") != uid or item.get("status") != "active":
            raise HTTPException(404, "Arquivo não encontrado.")
        if item.get("format") not in FORMATS:
            raise HTTPException(422, "Fichamento disponível para PDF, DOCX e TXT.")
        return item

    def pending_job(uid: str, item_id: str):
        docs = db.collection("research_jobs").where("owner_uid", "==", uid).limit(200).stream()
        for snap in docs:
            record = reconcile(snap.reference, snap.to_dict()) if hasattr(snap, "reference") else snap.to_dict()
            if (record.get("mode") == "reading_notes" and record.get("notes_item_id") == item_id):
                yield record

    @router.get("/{item_id}/ai-notes")
    def get_notes(item_id: str, user: dict = dependency):
        item = owned_item(item_id, user["uid"])
        blob = find_cached(bucket, user["uid"], item["sha256"])
        if blob is not None:
            return {"status": "completed", "notes": json.loads(blob.download_as_bytes())}
        jobs = sorted(pending_job(user["uid"], item_id), key=lambda r: r.get("created_at", ""))
        if jobs:
            last = jobs[-1]
            return {"status": last.get("status"), "stage": last.get("stage", ""), "error": last.get("error", "")}
        return {"status": "none"}

    @router.post("/{item_id}/ai-notes", status_code=202)
    def request_notes(item_id: str, user: dict = dependency):
        uid = user["uid"]
        item = owned_item(item_id, uid)
        if find_cached(bucket, uid, item["sha256"]) is not None:
            return {"status": "completed", "cached": True}
        if any(r.get("status") in ACTIVE_STATUSES for r in pending_job(uid, item_id)):
            raise HTTPException(409, "O fichamento deste documento já está em andamento.")
        access = get_access_for_notes(user)
        if NOTES_MODEL not in access["models"]:
            raise HTTPException(403, "O modelo do fichamento não está disponível para a sua chave Gemini.")
        if not str(item.get("object_path", "")).startswith(f"library/{uid}/{item_id}/"):
            raise HTTPException(422, "Caminho da fonte inválido.")
        job_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        db.collection("research_jobs").document(job_id).create({
            "id": job_id, "owner_uid": uid, "title": f"Fichamento: {item.get('name', '')}"[:120],
            "status": "queued", "stage": "Fichamento na fila", "mode": "reading_notes",
            "notes_item_id": item_id, "ai_auth_mode": access["ai_auth_mode"], "model": NOTES_MODEL,
            "sources": [{k: item.get(k) for k in ("id", "name", "format", "sha256", "size", "object_path")}],
            "created_at": now, "finished_at": "", "files": [], "error": "",
        })
        try:
            start_job(job_id, uid, "reading_notes")
        except Exception:
            db.collection("research_jobs").document(job_id).update({
                "status": "failed", "error": "Falha ao iniciar o fichamento", "finished_at": now})
            raise HTTPException(503, "Não foi possível iniciar o fichamento.") from None
        return {"status": "queued", "job_id": job_id}

    return router
