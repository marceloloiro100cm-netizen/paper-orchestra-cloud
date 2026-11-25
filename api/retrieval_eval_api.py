"""Teste de busca no corpus de referência (gate G2, M04): rotas da API.

Origem: R01 (Scriptorium). Só administrador. Cria um registro em research_jobs
com mode="retrieval_eval" (fora da lista de pesquisas e da trava de "uma
pesquisa por vez") e inicia o worker, que baixa os 30 PDFs de acesso aberto
do corpus de referência e mede a busca lexical, vetorial e híbrida com a chave
Gemini pessoal de quem pediu (worker/retrieval_eval.py).

Custo: embeddings de cerca de 1.700 trechos e 42 consultas na chave pessoal
(gemini-embedding-001; centavos de dólar no nível pago, gratuito no nível
gratuito dentro dos limites). Os documentos são publicados em acesso aberto.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Response

from job_state import ACTIVE_STATUSES, reconcile

MODE = "retrieval_eval"


def make_retrieval_eval_router(db, bucket, verify_user: Callable, is_admin_user: Callable,
                               byok_ready: Callable, start_job: Callable):
    router = APIRouter(prefix="/api/admin/retrieval-eval", tags=["avaliação"])
    dependency = Depends(verify_user)

    def require_admin(user: dict) -> None:
        if not is_admin_user(user):
            raise HTTPException(403, "Apenas administradores podem rodar o teste de busca.")

    def runs(uid: str) -> list[dict]:
        docs = db.collection("research_jobs").where("owner_uid", "==", uid).limit(200).stream()
        out = []
        for snap in docs:
            data = snap.to_dict() or {}
            if data.get("mode") == MODE:
                out.append(reconcile(snap.reference, data) if hasattr(snap, "reference") else data)
        return sorted(out, key=lambda r: r.get("created_at", ""))

    def view(record: dict) -> dict:
        return {"id": record["id"], "status": record.get("status"), "stage": record.get("stage", ""),
                "error": record.get("error", ""), "created_at": record.get("created_at", ""),
                "finished_at": record.get("finished_at", ""),
                "summary": record.get("retrieval_eval_summary")}

    @router.get("")
    def latest(user: dict = dependency):
        require_admin(user)
        items = runs(user["uid"])
        return {"last": view(items[-1]) if items else None}

    @router.post("", status_code=202)
    def start(user: dict = dependency):
        require_admin(user)
        uid = user["uid"]
        if not byok_ready(user):
            raise HTTPException(409, "Cadastre sua chave Gemini antes de rodar o teste de busca.")
        if any(r.get("status") in ACTIVE_STATUSES for r in runs(uid)):
            raise HTTPException(409, "Já há um teste de busca em andamento.")
        job_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        db.collection("research_jobs").document(job_id).create({
            "id": job_id, "owner_uid": uid, "title": "Teste de busca no corpus de referência",
            "status": "queued", "stage": "Teste na fila", "mode": MODE, "ai_auth_mode": "user_gemini",
            "model": "gemini-embedding-001", "sources": [], "created_at": now, "finished_at": "",
            "files": [], "error": "",
        })
        try:
            start_job(job_id, uid, MODE)
        except Exception:
            db.collection("research_jobs").document(job_id).update({
                "status": "failed", "error": "Falha ao iniciar o teste", "finished_at": now})
            raise HTTPException(503, "Não foi possível iniciar o teste de busca.") from None
        return {"status": "queued", "job_id": job_id}

    @router.get("/{job_id}/download")
    def download(job_id: str, user: dict = dependency):
        require_admin(user)
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise HTTPException(404, "Teste não encontrado.")
        snap = db.collection("research_jobs").document(job_id).get()
        record = snap.to_dict() if snap.exists else None
        if not record or record.get("owner_uid") != user["uid"] or record.get("mode") != MODE:
            raise HTTPException(404, "Teste não encontrado.")
        if record.get("status") != "completed":
            raise HTTPException(409, "Teste ainda não concluído.")
        blob = bucket.blob(f"research/{user['uid']}/{job_id}/output/retrieval_eval.json")
        if not blob.exists():
            raise HTTPException(404, "Resultado indisponível.")
        content = blob.download_as_bytes()
        json.loads(content)  # só devolve JSON válido
        return Response(content=content, media_type="application/json", headers={
            "Content-Disposition": 'attachment; filename="teste_busca_corpus.json"',
            "Cache-Control": "no-store"})

    return router
