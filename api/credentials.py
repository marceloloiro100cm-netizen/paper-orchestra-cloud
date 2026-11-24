"""Cofre BYOK por pesquisador no Google Cloud Secret Manager.

Nunca retorna chaves ao cliente, nunca grava o segredo no Firestore e não
permite fallback para credenciais do projeto compartilhado.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, SecretStr

# Formato aceito para chaves Gemini. Mesmo padrão usado em worker/byok.py;
# tests/test_credentials.py confere que os dois continuam iguais.
KEY_PATTERN = r"[A-Za-z0-9_.-]{20,512}"


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
    # SecretStr mascara o valor em representações e em erros de validação.
    key: SecretStr

    @property
    def normalized(self) -> str:
        key = self.key.get_secret_value().strip()
        if not re.fullmatch(KEY_PATTERN, key):
            raise ValueError("Formato de chave inválido")
        return key


def store_credential(db, project: str, uid: str, key: str, *, client=None, model_access: dict | None = None) -> dict:
    """Armazena nova versão antes de ativar o perfil, sem imprimir o segredo."""
    secret = secret_path(project, uid)
    if client is None:
        from google.cloud import secretmanager
        manager = secretmanager.SecretManagerServiceClient()
    else:
        manager = client
    from google.api_core.exceptions import AlreadyExists
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
        # A permissão verificada é gravada junto com o estado ativo; sem janela
        # em que uma chave antiga pudesse ser confundida com uma chave validada.
        "model_access": model_access or {"status": "not_verified", "models": {}},
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
    if client is None:
        from google.cloud import secretmanager
        manager = secretmanager.SecretManagerServiceClient()
    else:
        manager = client
    from google.api_core.exceptions import NotFound
    try:
        manager.delete_secret(request={"name": secret})
    except NotFound:
        pass
    return {"provider": "gemini_api", "configured": False}


def get_worker_credential(db, project: str, uid: str, *, client=None) -> str:
    """Worker lê apenas a credencial própria de um owner_uid já validado."""
    if not credential_state(db, uid):
        raise RuntimeError("Credencial do pesquisador indisponível")
    if client is None:
        from google.cloud import secretmanager
        manager = secretmanager.SecretManagerServiceClient()
    else:
        manager = client
    response = manager.access_secret_version(request={
        "name": secret_path(project, uid) + "/versions/latest",
    })
    key = response.payload.data.decode("utf-8")
    if not re.fullmatch(KEY_PATTERN, key):
        raise RuntimeError("Credencial do pesquisador inválida")
    return key
