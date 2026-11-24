"""Cofre BYOK por pesquisador no Google Cloud Secret Manager.

Nunca retorna chaves ao cliente, nunca grava o segredo no Firestore e não
permite fallback para credenciais do projeto compartilhado.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException
from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import secretmanager
from pydantic import BaseModel, Field


def secret_id(uid: str) -> str:
    # Firebase UID não pode controlar livremente o caminho do segredo.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", uid):
        raise ValueError("Identidade inválida")
    return "scriptorium-byok-" + uid


def secret_path(project: str, uid: str) -> str:
    return f"projects/{project}/secrets/{secret_id(uid)}"


def credential_state(db, uid: str) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", uid):
        return False
    snap = db.collection("research_credentials").document(uid).get()
    return bool(snap.exists and snap.to_dict().get("status") == "active")


class GeminiCredential(BaseModel):
    key: str = Field(min_length=20, max_length=512)

    @property
    def normalized(self) -> str:
        key = self.key.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,512}", key):
            raise ValueError("Formato de chave inválido")
        return key


def store_credential(db, project: str, uid: str, key: str, *, client=None) -> dict:
    """Armazena nova versão antes de ativar o perfil, sem imprimir o segredo."""
    secret = secret_path(project, uid)
    manager = client or secretmanager.SecretManagerServiceClient()
    try:
        manager.create_secret(request={
            "parent": f"projects/{project}",
            "secret_id": secret_id(uid),
            "secret": {"replication": {"automatic": {}}},
        })
    except AlreadyExists:
        pass
    manager.add_secret_version(request={
        "parent": secret, "payload": {"data": key.encode("utf-8")},
    })
    db.collection("research_credentials").document(uid).set({
        "provider": "gemini_api",
        "status": "active",
        "secret_resource": secret,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"provider": "gemini_api", "configured": True}


def delete_credential(db, project: str, uid: str, *, client=None) -> dict:
    """Revogação fail-closed: desativa metadados ANTES de apagar versões."""
    secret = secret_path(project, uid)
    db.collection("research_credentials").document(uid).set({
        "provider": "gemini_api", "status": "revoked",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    manager = client or secretmanager.SecretManagerServiceClient()
    try:
        manager.delete_secret(request={"name": secret})
    except NotFound:
        pass
    return {"provider": "gemini_api", "configured": False}


def get_worker_credential(db, project: str, uid: str, *, client=None) -> str:
    """Worker lê apenas a credencial própria de um owner_uid já validado."""
    if not credential_state(db, uid):
        raise RuntimeError("Credencial do pesquisador indisponível")
    manager = client or secretmanager.SecretManagerServiceClient()
    response = manager.access_secret_version(request={
        "name": secret_path(project, uid) + "/versions/latest",
    })
    key = response.payload.data.decode("utf-8")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,512}", key):
        raise RuntimeError("Credencial do pesquisador inválida")
    return key
