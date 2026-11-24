"""Pedidos de acesso criados somente após login Google com e-mail verificado.

Um pedido não concede acesso, não libera funções de biblioteca e não concede uso de IA.
A aprovação continua exclusiva de administradores de ALLOWED_EMAILS.
"""
from datetime import datetime, timezone
import re

from fastapi import HTTPException
from access import member_id, normalize_email, set_invitation

COLLECTION = "research_access_requests"


def request_access(db, identity: dict) -> dict:
    email = identity.get("email") or ""
    if identity.get("email_verified") is not True:
        raise HTTPException(status_code=403, detail="Confirme seu e-mail Google antes de solicitar acesso.")
    try:
        email = normalize_email(email)
    except ValueError:
        raise HTTPException(status_code=422, detail="E-mail inválido.")
    uid = str(identity.get("uid") or "")
    if not uid or len(uid) > 128:
        raise HTTPException(status_code=422, detail="Identidade inválida.")
    ref = db.collection(COLLECTION).document(member_id(email))
    existing = ref.get()
    if existing.exists and existing.to_dict().get("status") == "pending":
        return {"status": "pending", "email": email}
    now = datetime.now(timezone.utc).isoformat()
    ref.set({"uid": uid, "email": email, "status": "pending",
             "requested_at": now, "updated_at": now})
    return {"status": "pending", "email": email}


def pending_access_requests(db) -> dict:
    docs = db.collection(COLLECTION).where("status", "==", "pending").limit(100).stream()
    entries = []
    for snap in docs:
        data = snap.to_dict() or {}
        entries.append({"id": snap.id, "email": data.get("email", ""),
                        "requested_at": data.get("requested_at", "")})
    entries.sort(key=lambda x: x["requested_at"])
    return {"items": entries}


def approve_access_request(db, request_id: str, admin_uid: str,
                           admin_emails: set[str]) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", request_id):
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    ref = db.collection(COLLECTION).document(request_id)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("status") != "pending":
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    email = snap.to_dict().get("email", "")
    if member_id(email) != request_id:
        raise HTTPException(status_code=422, detail="Pedido inconsistente.")
    invitation = set_invitation(db, email, True, admin_uid, admin_emails)
    ref.update({"status": "approved", "updated_at": datetime.now(timezone.utc).isoformat(),
                "approved_by_uid": admin_uid})
    return invitation
