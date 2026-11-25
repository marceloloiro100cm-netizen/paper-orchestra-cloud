"""Biblioteca acadêmica privada e persistente no Firestore/Cloud Storage.

Arquivos são material de pesquisa NÃO CONFIÁVEL, nunca instruções operacionais.
Somente o backend autenticado pode ler ou alterar metadados e objetos.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from upload_guard import inspect as inspect_upload

MAX_BYTES = {
    ".pdf": 8 * 1024 * 1024,
    ".docx": 8 * 1024 * 1024,
    ".bib": 2 * 1024 * 1024,
    ".ris": 2 * 1024 * 1024,
    ".txt": 2 * 1024 * 1024,
}
MIMES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".bib": "application/x-bibtex",
    ".ris": "application/x-research-info-systems",
    ".txt": "text/plain; charset=utf-8",
}
MAX_ITEMS_PER_OWNER = 500
MAX_SELECTED_SOURCES = 8


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_filename(value: str) -> tuple[str, str]:
    value = value.strip().replace("\\", "/").split("/")[-1]
    value = re.sub(r"[^A-Za-z0-9À-ÿ_.,() \-]", "_", value)[:120]
    suffix = Path(value).suffix.lower()
    if not value or value.startswith(".") or suffix not in MAX_BYTES:
        raise HTTPException(422, "Use um arquivo PDF, DOCX, BIB, RIS ou TXT válido.")
    return value, suffix


def validate_signature(data: bytes, suffix: str) -> None:
    if suffix == ".pdf" and not data[:1024].lstrip().startswith(b"%PDF-"):
        raise HTTPException(422, "O arquivo não parece ser um PDF válido.")
    if suffix == ".docx":
        from io import BytesIO
        from zipfile import BadZipFile, ZipFile
        try:
            with ZipFile(BytesIO(data)) as z:
                if "[Content_Types].xml" not in z.namelist() or "word/document.xml" not in z.namelist():
                    raise ValueError("DOCX inválido.")
                # Proteção contra um arquivo ZIP decompresso excessivamente.
                if sum(x.file_size for x in z.infolist()) > 30 * 1024 * 1024:
                    raise ValueError("DOCX descompactado muito grande.")
        except (BadZipFile, ValueError):
            raise HTTPException(422, "O arquivo DOCX não é válido ou excede o limite seguro.") from None
    if suffix in {".bib", ".ris", ".txt"}:
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422, "Arquivos de texto precisam estar codificados em UTF-8.") from None


def exposed(record: dict) -> dict:
    return {key: record.get(key) for key in (
        "id", "name", "format", "size", "collection", "description", "sha256",
        "created_at", "archived_at", "status", "origin", "guard",
    )}


def quarantine_message(guard: dict) -> str:
    reasons = "; ".join(f["detail"] for f in guard["findings"] if f["severity"] == "alta")
    return ("Arquivo retido em quarentena e fora da biblioteca: " + reasons +
            " Ele não será usado em pesquisas. Se o arquivo for legítimo, gere um PDF novo"
            " (por exemplo, imprimindo para PDF) e envie de novo.")


def save_library_item(db, bucket, owner_uid: str, name: str, suffix: str, data: bytes,
                      collection_name: str, description: str, origin: dict | None = None) -> dict:
    """Grava original imutável no GCS e metadados no Firestore (upload e Zotero)."""
    collection = db.collection("library_items")
    existing = list(collection.where("owner_uid", "==", owner_uid).limit(MAX_ITEMS_PER_OWNER + 1).stream())
    if sum(s.to_dict().get("status") == "active" for s in existing) >= MAX_ITEMS_PER_OWNER:
        raise HTTPException(409, "Limite de 500 arquivos ativos atingido.")
    if not data:
        raise HTTPException(422, "Arquivo vazio.")
    if len(data) > MAX_BYTES[suffix]:
        raise HTTPException(413, "Arquivo acima do limite permitido.")
    validate_signature(data, suffix)
    # M13: inspeção estática antes de aceitar; risco alto vai para quarentena.
    guard = inspect_upload(data, suffix)
    quarantined = guard["verdict"] == "quarantine"
    item_id = uuid.uuid4().hex
    # ID e UID são controlados pelo backend; o nome do usuário nunca vira caminho.
    # Em quarentena, o original fica fora de library/ (o worker só lê library/{uid}/).
    path = (f"quarantine/{owner_uid}/{item_id}/original{suffix}" if quarantined
            else f"library/{owner_uid}/{item_id}/original{suffix}")
    document = {
        "id": item_id, "owner_uid": owner_uid,
        "name": name, "format": suffix[1:], "size": len(data),
        "description": description.strip(), "collection": collection_name.strip(),
        "sha256": hashlib.sha256(data).hexdigest(), "object_path": path, "created_at": utc_now(),
        "archived_at": "", "status": "quarantined" if quarantined else "active",
        "guard": {"version": guard["version"], "verdict": guard["verdict"],
                  "findings": guard["findings"][:12]},
    }
    if origin:
        document["origin"] = origin
    blob = bucket.blob(path)
    # Em quarentena, gravado como binário genérico: nunca servido como PDF/DOCX.
    blob.upload_from_string(data, content_type="application/octet-stream" if quarantined else MIMES[suffix],
                            if_generation_match=0)
    try:
        collection.document(item_id).create(document)
    except Exception:
        # Não deixar arquivo órfão se a criação no Firestore falhar.
        blob.delete()
        raise
    if quarantined:
        raise HTTPException(422, quarantine_message(guard))
    return document


def make_library_router(db, bucket, verify_user: Callable):
    router = APIRouter(prefix="/api/library", tags=["biblioteca"])
    dependencies = Depends(verify_user)
    collection = db.collection("library_items")

    def owned(item_id: str, user: dict):
        if not re.fullmatch(r"[0-9a-f]{32}", item_id):
            raise HTTPException(404, "Arquivo não encontrado.")
        snap = collection.document(item_id).get()
        if not snap.exists:
            raise HTTPException(404, "Arquivo não encontrado.")
        item = snap.to_dict()
        if item.get("owner_uid") != user["uid"]:
            raise HTTPException(404, "Arquivo não encontrado.")
        return item

    @router.get("/items")
    def list_items(user: dict = dependencies):
        docs = collection.where("owner_uid", "==", user["uid"]).limit(500).stream()
        records = [doc.to_dict() for doc in docs]
        items = [exposed(r) for r in records if r.get("status") == "active"]
        items.sort(key=lambda i: i.get("created_at") or "", reverse=True)
        # M13: arquivos retidos aparecem para o dono, com o motivo, mas não são selecionáveis.
        held = [exposed(r) for r in records if r.get("status") == "quarantined"]
        held.sort(key=lambda i: i.get("created_at") or "", reverse=True)
        return {"items": items, "quarantined": held[:50], "max_items": MAX_ITEMS_PER_OWNER}

    @router.post("/items", status_code=201)
    async def upload_file(
        request: Request,
        filename: str = Query(min_length=4, max_length=200),
        collection_name: str = Query(default="Geral", max_length=60, alias="collection"),
        description: str = Query(default="", max_length=300),
        user: dict = dependencies,
    ):
        name, suffix = safe_filename(filename)
        if not collection_name.strip():
            raise HTTPException(422, "Informe uma coleção.")
        chunks = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_BYTES[suffix]:
                raise HTTPException(413, "Arquivo acima do limite permitido.")
            chunks.append(chunk)
        data = b"".join(chunks)
        document = save_library_item(db, bucket, user["uid"], name, suffix, data,
                                     collection_name, description)
        return {"item": exposed(document)}

    @router.get("/items/{item_id}/download")
    def download_file(item_id: str, user: dict = dependencies):
        item = owned(item_id, user)
        if item.get("status") != "active":
            raise HTTPException(404, "Arquivo arquivado.")
        blob = bucket.blob(item["object_path"])
        if not blob.exists():
            raise HTTPException(404, "Arquivo indisponível no armazenamento.")
        suffix = "." + item["format"]
        return Response(
            content=blob.download_as_bytes(),
            media_type=MIMES[suffix],
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{__import__('urllib.parse', fromlist=['quote']).quote(item['name'])}",
                     "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.post("/items/{item_id}/archive")
    def archive_file(item_id: str, user: dict = dependencies):
        item = owned(item_id, user)
        if item.get("status") in ("active", "quarantined"):
            collection.document(item_id).update({"status": "archived", "archived_at": utc_now()})
        # Arquivar não apaga o original: pesquisas vinculadas continuam reproduzíveis.
        return {"status": "archived", "id": item_id}

    return router
