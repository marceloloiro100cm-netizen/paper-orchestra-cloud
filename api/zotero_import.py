"""Importação somente leitura do Zotero para a biblioteca privada (M26).

Origem: R21 (Zotero Web API v3, https://www.zotero.org/support/dev/web_api/v3/basics).
Plano: Scriptorium V2, módulo M26 "Importação Zotero somente leitura".

Documentação conferida em 24/11/2026: base https://api.zotero.org (só HTTPS),
chave no cabeçalho Zotero-API-Key, paginação por limit (máx. 100) e start,
total no cabeçalho Total-Results, itens principais em /items/top,
exportação com format=bibtex, e /keys/<chave> informa o userID da chave.

Decisões de segurança:
- a chave Zotero é usada só durante a requisição e NUNCA é guardada (nem no
  Firestore, nem no Secret Manager, nem em logs); cada importação a pede de novo;
- somente leitura e somente metadados (BibTeX); anexos não são baixados;
- o resultado vira um item .bib comum da biblioteca, com a origem registrada,
  sem sobrescrever nada do acervo local.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr

from library import MAX_BYTES, exposed, save_library_item

API = "https://api.zotero.org"
PAGE = 100
MAX_ITEMS = 500
TIMEOUT = 15
KEY_FORMAT = re.compile(r"[A-Za-z0-9]{10,64}")
COLLECTION_KEY = re.compile(r"[A-Z0-9]{8}")


class ZoteroKey(BaseModel):
    api_key: SecretStr

    def value(self) -> str:
        key = self.api_key.get_secret_value().strip()
        if not KEY_FORMAT.fullmatch(key):
            raise HTTPException(422, "Formato de chave do Zotero inválido.")
        return key


class ZoteroImport(ZoteroKey):
    collection_key: str | None = Field(default=None, max_length=8)
    max_items: int = Field(default=MAX_ITEMS, ge=1, le=MAX_ITEMS)


def zotero_get(path: str, key: str, *, transport=None) -> tuple[int, dict, bytes]:
    """GET na API do Zotero. Nunca inclui a chave em mensagens de erro."""
    if transport is not None:
        return transport(path, key)
    request = Request(API + path, headers={"Zotero-API-Key": key, "Zotero-API-Version": "3",
                                           "User-Agent": "Scriptorium/1 (paper-orchestra-cloud)"})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return response.status, dict(response.headers), response.read(MAX_BYTES[".bib"] + 1)
    except HTTPError as exc:
        return exc.code, {}, b""
    except (URLError, TimeoutError, OSError):
        return 0, {}, b""


def _check(status: int) -> None:
    if status in (401, 403):
        raise HTTPException(403, "O Zotero recusou a chave ou ela não dá acesso a esta biblioteca.")
    if status == 404:
        raise HTTPException(404, "Biblioteca ou coleção não encontrada no Zotero.")
    if status == 429:
        raise HTTPException(429, "O Zotero limitou as requisições. Tente de novo em alguns minutos.")
    if status != 200:
        raise HTTPException(503, "O Zotero não respondeu. Tente novamente.")


def user_id_for(key: str, transport=None) -> str:
    status, _, body = zotero_get(f"/keys/{quote(key, safe='')}", key, transport=transport)
    _check(status)
    import json
    try:
        user_id = str(json.loads(body.decode("utf-8"))["userID"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, "Resposta inesperada do Zotero.") from None
    if not user_id.isdigit():
        raise HTTPException(503, "Resposta inesperada do Zotero.")
    return user_id


def list_collections(key: str, transport=None) -> list[dict]:
    import json
    user_id = user_id_for(key, transport)
    items, start = [], 0
    while start < 1000:
        status, headers, body = zotero_get(
            f"/users/{user_id}/collections?limit={PAGE}&start={start}", key, transport=transport)
        _check(status)
        page = json.loads(body.decode("utf-8") or "[]")
        for entry in page:
            data = entry.get("data") or {}
            items.append({"key": entry.get("key"), "name": str(data.get("name", ""))[:120],
                          "parent": data.get("parentCollection") or None,
                          "items": (entry.get("meta") or {}).get("numItems")})
        total = int(headers.get("Total-Results", len(items)) or 0)
        start += PAGE
        if not page or start >= total:
            break
    return items


def export_bibtex(key: str, collection_key: str | None, max_items: int,
                  transport=None) -> tuple[str, str, int]:
    user_id = user_id_for(key, transport)
    if collection_key and not COLLECTION_KEY.fullmatch(collection_key):
        raise HTTPException(422, "Identificador de coleção inválido.")
    base = f"/users/{user_id}" + (f"/collections/{collection_key}" if collection_key else "") + "/items/top"
    parts, start, total = [], 0, None
    while start < max_items:
        limit = min(PAGE, max_items - start)
        status, headers, body = zotero_get(f"{base}?format=bibtex&limit={limit}&start={start}",
                                           key, transport=transport)
        _check(status)
        text = body.decode("utf-8", errors="replace").strip()
        if text:
            parts.append(text)
        total = int(headers.get("Total-Results", 0) or 0) if total is None else total
        start += limit
        if not text or start >= total:
            break
    bib = "\n\n".join(parts) + "\n"
    if len(bib.encode("utf-8")) > MAX_BYTES[".bib"]:
        raise HTTPException(413, "A coleção excede o limite de 2 MB para BibTeX. Importe uma coleção menor.")
    count = len(re.findall(r"^@\w+\s*[{(]", bib, re.MULTILINE))
    return bib, user_id, count


def make_zotero_router(db, bucket, verify_user: Callable, transport=None):
    router = APIRouter(prefix="/api/library/zotero", tags=["zotero"])
    dependency = Depends(verify_user)

    @router.post("/collections")
    def collections(payload: ZoteroKey, user: dict = dependency):
        return {"items": list_collections(payload.value(), transport)}

    @router.post("/import", status_code=201)
    def import_collection(payload: ZoteroImport, user: dict = dependency):
        key = payload.value()
        bib, user_id, count = export_bibtex(key, payload.collection_key, payload.max_items, transport)
        if count == 0:
            raise HTTPException(422, "Nenhum item com metadados encontrado nessa coleção.")
        now = datetime.now(timezone.utc)
        label = payload.collection_key or "biblioteca inteira"
        document = save_library_item(
            db, bucket, user["uid"], f"Zotero {label} {now:%Y-%m-%d}.bib", ".bib", bib.encode("utf-8"),
            "Zotero", f"Importado do Zotero ({count} itens, coleção {label}) em {now:%d/%m/%Y}. Somente metadados.",
            origin={"provider": "zotero", "upstream_id": "R21", "zotero_user_id": user_id,
                    "collection_key": payload.collection_key, "items": count,
                    "imported_at": now.isoformat(), "attachments": "not_imported"})
        return {"item": exposed(document), "items_imported": count}

    return router
