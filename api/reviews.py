"""Revisões humanas registradas sobre os relatórios de uma pesquisa.

Origem: R01. Completa passos do plano Scriptorium V2:
- M08: "aceitar revisão manual sem sobrescrever histórico" na matriz;
- M24: registrar o resultado da conferência manual de referências;
- M12: base do checkpoint de revisão de afirmações (await_claim_review).

Somente acréscimo: cada decisão é um documento novo; nada é editado ou apagado.
A leitura mostra a decisão mais recente por item e o histórico completo.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

COLLECTION = "research_reviews"
DECISIONS = {
    "claim": {"apoia", "contradiz", "apenas_menciona", "nao_sustenta", "pendente"},
    "fire": {"apoia", "contradiz", "apenas_menciona", "nao_sustenta", "pendente"},
    "reference": {"referencia_confirmada", "referencia_incorreta", "pendente"},
    "quote": {"citacao_correta", "citacao_incorreta", "pendente"},
    "contradiction": {"divergencia_confirmada", "nao_e_divergencia", "pendente"},
}
MAX_REVIEWS_PER_JOB = 2000


class ReviewIn(BaseModel):
    target_type: Literal["claim", "fire", "reference", "quote", "contradiction"]
    target_id: str = Field(min_length=1, max_length=160)
    decision: str = Field(min_length=3, max_length=40)
    note: str = Field(default="", max_length=1000)

    @field_validator("target_id")
    @classmethod
    def safe_id(cls, value: str) -> str:
        if not re.fullmatch(r"[\w.:\-/]+", value):
            raise ValueError("Identificador inválido")
        return value


def add_review(db, job_id: str, owner_uid: str, payload: ReviewIn) -> dict:
    if payload.decision not in DECISIONS[payload.target_type]:
        raise HTTPException(422, "Decisão inválida para este tipo de item.")
    existing = list(db.collection(COLLECTION).where("job_id", "==", job_id).limit(MAX_REVIEWS_PER_JOB).stream())
    if len(existing) >= MAX_REVIEWS_PER_JOB:
        raise HTTPException(409, "Limite de revisões desta pesquisa atingido.")
    review = {
        "id": uuid.uuid4().hex, "job_id": job_id, "owner_uid": owner_uid,
        "target_type": payload.target_type, "target_id": payload.target_id,
        "decision": payload.decision, "note": payload.note.strip(),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    db.collection(COLLECTION).document(review["id"]).create(review)
    return review


def list_reviews(db, job_id: str, owner_uid: str) -> dict:
    docs = [s.to_dict() for s in db.collection(COLLECTION).where("job_id", "==", job_id)
            .limit(MAX_REVIEWS_PER_JOB).stream()]
    mine = sorted((d for d in docs if d.get("owner_uid") == owner_uid), key=lambda d: d.get("at", ""))
    latest = {}
    for review in mine:
        latest[f"{review['target_type']}:{review['target_id']}"] = review
    return {"latest": latest, "history": mine}
