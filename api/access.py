"""Convites privados para pesquisadores; sem habilitar cobrança compartilhada de IA.

Somente administradores preexistentes em ALLOWED_EMAILS podem convidar.
O identificador do convite é SHA-256 do e-mail normalizado, sem usar e-mail em paths.
"""
import hashlib
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from credentials import credential_state


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
        raise ValueError("Informe um e-mail válido.")
    return normalized


def member_id(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()


def is_admin(user: dict, admin_emails: set[str]) -> bool:
    return user.get("email_verified") is True and (user.get("email") or "").strip().lower() in admin_emails


def get_access(db, user: dict, admin_emails: set[str]) -> dict:
    """Consulta convite apenas depois de validar o e-mail verificado via Firebase."""
    email = (user.get("email") or "").strip().lower()
    if not user.get("email_verified") or not email:
        return {"allowed": False, "admin": False, "byok_ready": False}
    if email in admin_emails:
        # Separação de custos (24/11/2026): o administrador também gera com a
        # própria chave Gemini; o projeto do Scriptorium paga só infraestrutura.
        return {"allowed": True, "admin": True,
                "byok_ready": bool(credential_state(db, user.get("uid", "")))}
    try:
        key = member_id(email)
    except ValueError:
        return {"allowed": False, "admin": False, "byok_ready": False}
    snap = db.collection("research_members").document(key).get()
    invitation = snap.to_dict() if snap.exists else {}
    allowed = invitation.get("status") == "active" and invitation.get("email") == email
    # Nunca permite a credencial padrão do servidor a um convidado.
    ready = bool(allowed and credential_state(db, user.get("uid", "")))
    return {"allowed": allowed, "admin": False, "byok_ready": ready}


class Invitation(BaseModel):
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


def set_invitation(db, email: str, active: bool, invited_by: str, admin_emails: set[str]) -> dict:
    email = normalize_email(email)
    if email in admin_emails:
        raise HTTPException(status_code=409, detail="Administradores são gerenciados pela configuração do servidor.")
    db.collection("research_members").document(member_id(email)).set({
        "email": email,
        "status": "active" if active else "revoked",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by_uid": invited_by,
    })
    return {"email": email, "status": "active" if active else "revoked"}
