"""Estado das pesquisas: uma execução ativa por conta e reconciliação de travadas.

1. Trava por conta: o documento research_owner_state/{uid} guarda a pesquisa
   ativa. Ler a trava e criar a pesquisa acontecem na MESMA transação do
   Firestore, então duas requisições simultâneas não iniciam dois Jobs.
2. Reconciliação: se o Cloud Run Job morrer antes de atualizar o Firestore, a
   pesquisa ficaria "running" para sempre e bloquearia a conta. Passado o
   limite (task-timeout de 180 min + margem), ela é marcada como falha.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

ACTIVE_STATUSES = ("queued", "running")
STALE_AFTER = timedelta(minutes=int(os.getenv("JOB_STALE_MINUTES", "200")))
STALE_ERROR = ("A execução na nuvem foi interrompida sem registrar o resultado "
               "(tempo limite excedido). Consulte o log e inicie novamente.")
OWNER_STATE = "research_owner_state"
JOBS = "research_jobs"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_stale(record: dict, now: datetime | None = None) -> bool:
    """Pesquisa ativa há mais tempo do que um Job consegue durar."""
    if record.get("status") not in ACTIVE_STATUSES:
        return False
    began = _parse(record.get("started_at")) or _parse(record.get("created_at"))
    if began is None:
        return False  # Sem data confiável: não marcar falha por suposição.
    return (now or utc_now()) - began > STALE_AFTER


def stale_fields(now: datetime | None = None) -> dict:
    return {"status": "failed", "stage": "Falha", "error": STALE_ERROR,
            "finished_at": (now or utc_now()).isoformat()}


def reconcile(ref, record: dict, now: datetime | None = None) -> dict:
    """Marca uma pesquisa travada como falha e devolve o registro atualizado."""
    if not is_stale(record, now):
        return record
    fields = stale_fields(now)
    ref.update(fields)
    return {**record, **fields}


def claim_in_transaction(transaction, db, owner_uid: str, job_id: str,
                         record: dict, now: datetime | None = None) -> bool:
    """Corpo da transação. Retorna False se já houver pesquisa ativa."""
    now = now or utc_now()
    lock_ref = db.collection(OWNER_STATE).document(owner_uid)
    lock = lock_ref.get(transaction=transaction)
    active_id = (lock.to_dict() or {}).get("active_job_id") if lock.exists else None
    if active_id:
        active_ref = db.collection(JOBS).document(active_id)
        active = active_ref.get(transaction=transaction)
        if active.exists:
            data = active.to_dict() or {}
            if data.get("status") in ACTIVE_STATUSES:
                if not is_stale(data, now):
                    return False
                transaction.update(active_ref, stale_fields(now))
    transaction.set(lock_ref, {"active_job_id": job_id,
                               "updated_at": now.isoformat()})
    transaction.set(db.collection(JOBS).document(job_id), record)
    return True


def claim_active_slot(db, owner_uid: str, job_id: str, record: dict) -> bool:
    """Cria a pesquisa somente se a conta não tiver outra ativa (atômico)."""
    from google.cloud import firestore

    @firestore.transactional
    def run(transaction):
        return claim_in_transaction(transaction, db, owner_uid, job_id, record)

    return run(db.transaction())
