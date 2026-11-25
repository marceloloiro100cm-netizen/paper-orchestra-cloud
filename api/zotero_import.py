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
- somente leitura; por padrão só metadados (BibTeX). Anexos PDF só com
  consentimento explícito em cada importação (attachments_consent), passam pela
  inspeção de upload (M13) e nunca seguem redirecionamento com a chave;
- importação incremental: guarda só o número de versão da biblioteca Zotero
  (Last-Modified-Version) por conta e coleção, nunca a chave; a próxima
  importação pede apenas o que mudou desde essa versão (parâmetro since);
- o resultado vira um item .bib comum da biblioteca, com a origem registrada,
  sem sobrescrever nada do acervo local.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

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


MAX_ATTACHMENTS = 20
SYNC = "zotero_sync"
USER_AGENT = "Scriptorium/1 (paper-orchestra-cloud)"


class ZoteroImport(ZoteroKey):
    collection_key: str | None = Field(default=None, max_length=8)
    max_items: int = Field(default=MAX_ITEMS, ge=1, le=MAX_ITEMS)
    # Só o que mudou desde a última importação desta coleção (versão guardada, chave não).
    incremental: bool = False
    # Anexos PDF: somente com consentimento explícito nesta importação.
    attachments_consent: bool = False
    max_attachments: int = Field(default=10, ge=0, le=MAX_ATTACHMENTS)


class _NoRedirect(HTTPRedirectHandler):
    """Nunca segue redirecionamento com o cabeçalho da chave (evita vazar para outro host)."""
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = build_opener(_NoRedirect)


def zotero_get(path: str, key: str, *, transport=None, max_bytes: int = MAX_BYTES[".bib"] + 1
               ) -> tuple[int, dict, bytes]:
    """GET na API do Zotero. Nunca inclui a chave em mensagens de erro."""
    if transport is not None:
        return transport(path, key)
    request = Request(API + path, headers={"Zotero-API-Key": key, "Zotero-API-Version": "3",
                                           "User-Agent": USER_AGENT})
    try:
        with _OPENER.open(request, timeout=TIMEOUT) as response:
            return response.status, dict(response.headers), response.read(max_bytes)
    except HTTPError as exc:
        return exc.code, dict(exc.headers or {}), b""
    except (URLError, TimeoutError, OSError):
        return 0, {}, b""


def fetch_public(url: str, *, transport=None, max_bytes: int = MAX_BYTES[".pdf"] + 1) -> bytes | None:
    """Baixa o arquivo do endereço assinado devolvido pelo Zotero, SEM a chave."""
    if not url.startswith("https://"):
        return None
    if transport is not None:
        status, _, body = transport(url, None)
        return body if status == 200 else None
    try:
        with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=TIMEOUT * 2) as response:
            return response.read(max_bytes) if response.status == 200 else None
    except (HTTPError, URLError, TimeoutError, OSError):
        return None


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


def _items_base(user_id: str, collection_key: str | None) -> str:
    if collection_key and not COLLECTION_KEY.fullmatch(collection_key):
        raise HTTPException(422, "Identificador de coleção inválido.")
    return f"/users/{user_id}" + (f"/collections/{collection_key}" if collection_key else "") + "/items/top"


def export_bibtex(key: str, collection_key: str | None, max_items: int,
                  transport=None, since: int | None = None, user_id: str | None = None
                  ) -> tuple[str, str, int, int | None]:
    """BibTeX dos itens (só os alterados depois de `since`) e a versão atual da biblioteca."""
    user_id = user_id or user_id_for(key, transport)
    base = _items_base(user_id, collection_key)
    extra = f"&since={int(since)}" if since is not None else ""
    parts, start, total, version = [], 0, None, None
    while start < max_items:
        limit = min(PAGE, max_items - start)
        status, headers, body = zotero_get(f"{base}?format=bibtex&limit={limit}&start={start}{extra}",
                                           key, transport=transport)
        _check(status)
        if version is None and str(headers.get("Last-Modified-Version", "")).isdigit():
            version = int(headers["Last-Modified-Version"])
        text = body.decode("utf-8", errors="replace").strip()
        if text:
            parts.append(text)
        total = int(headers.get("Total-Results", 0) or 0) if total is None else total
        start += limit
        if not text or start >= total:
            break
    bib = "\n\n".join(parts) + "\n" if parts else ""
    if len(bib.encode("utf-8")) > MAX_BYTES[".bib"]:
        raise HTTPException(413, "A coleção excede o limite de 2 MB para BibTeX. Importe uma coleção menor.")
    count = len(re.findall(r"^@\w+\s*[{(]", bib, re.MULTILINE))
    return bib, user_id, count, version


def deleted_since(key: str, user_id: str, since: int, transport=None) -> int:
    """Quantos itens foram apagados no Zotero desde a versão `since` (só informativo)."""
    import json
    status, _, body = zotero_get(f"/users/{user_id}/deleted?since={int(since)}", key, transport=transport)
    if status != 200:
        return 0
    try:
        return len(json.loads(body.decode("utf-8") or "{}").get("items") or [])
    except (ValueError, AttributeError):
        return 0


def pdf_attachments(key: str, user_id: str, collection_key: str | None, max_items: int,
                    limit: int, transport=None) -> list[dict]:
    """Anexos PDF guardados no Zotero (imported_file/imported_url) dos itens principais."""
    import json
    base = _items_base(user_id, collection_key)
    status, _, body = zotero_get(f"{base}?format=keys&limit={min(max_items, PAGE)}", key, transport=transport)
    _check(status)
    found = []
    for parent in body.decode("utf-8", errors="replace").split():
        if len(found) >= limit:
            break
        if not COLLECTION_KEY.fullmatch(parent):
            continue
        status, _, raw = zotero_get(f"/users/{user_id}/items/{parent}/children", key, transport=transport)
        if status != 200:
            continue
        try:
            children = json.loads(raw.decode("utf-8") or "[]")
        except ValueError:
            continue
        for child in children:
            data = child.get("data") or {}
            if (data.get("itemType") == "attachment" and data.get("contentType") == "application/pdf"
                    and data.get("linkMode") in ("imported_file", "imported_url")
                    and COLLECTION_KEY.fullmatch(str(child.get("key", "")))):
                found.append({"key": child["key"], "parent": parent,
                              "filename": str(data.get("filename") or data.get("title") or "anexo.pdf")[:100]})
                break  # um PDF por item principal
    return found


def download_attachment(key: str, user_id: str, attachment_key: str, transport=None) -> bytes | None:
    status, headers, body = zotero_get(f"/users/{user_id}/items/{attachment_key}/file", key,
                                       transport=transport, max_bytes=MAX_BYTES[".pdf"] + 1)
    if status == 200:
        return body
    location = headers.get("Location") or headers.get("location")
    if status in (301, 302, 303, 307, 308) and location:
        return fetch_public(location, transport=transport)
    return None


def make_zotero_router(db, bucket, verify_user: Callable, transport=None):
    router = APIRouter(prefix="/api/library/zotero", tags=["zotero"])
    dependency = Depends(verify_user)

    @router.post("/collections")
    def collections(payload: ZoteroKey, user: dict = dependency):
        return {"items": list_collections(payload.value(), transport)}

    @router.post("/import", status_code=201)
    def import_collection(payload: ZoteroImport, user: dict = dependency):
        key = payload.value()
        uid = user["uid"]
        user_id = user_id_for(key, transport)
        label = payload.collection_key or "biblioteca inteira"
        sync_ref = db.collection(SYNC).document(f"{uid}_{user_id}_{payload.collection_key or 'all'}")
        sync = sync_ref.get()
        since = None
        if payload.incremental and sync.exists:
            since = (sync.to_dict() or {}).get("last_version")
        bib, user_id, count, version = export_bibtex(key, payload.collection_key, payload.max_items,
                                                     transport, since=since, user_id=user_id)
        deleted = deleted_since(key, user_id, since, transport) if since is not None else 0
        now = datetime.now(timezone.utc)
        result = {"items_imported": count, "incremental": since is not None, "since_version": since,
                  "library_version": version, "deleted_in_zotero": deleted}
        if count == 0 and since is None:
            raise HTTPException(422, "Nenhum item com metadados encontrado nessa coleção.")
        if count:
            suffix = f" desde v{since}" if since is not None else ""
            document = save_library_item(
                db, bucket, uid, f"Zotero {label}{suffix} {now:%Y-%m-%d}.bib", ".bib", bib.encode("utf-8"),
                "Zotero", (f"Importado do Zotero ({count} itens, coleção {label}"
                           + (f", alterados desde a versão {since}" if since is not None else "")
                           + f") em {now:%d/%m/%Y}."),
                origin={"provider": "zotero", "upstream_id": "R21", "zotero_user_id": user_id,
                        "collection_key": payload.collection_key, "items": count,
                        "imported_at": now.isoformat(), "since_version": since,
                        "library_version": version,
                        "attachments": "consented" if payload.attachments_consent else "not_imported"})
            result["item"] = exposed(document)
        else:
            result["up_to_date"] = True
        # Anexos PDF só com consentimento explícito nesta importação.
        attachments = {"imported": 0, "quarantined": 0, "skipped": 0}
        if payload.attachments_consent and payload.max_attachments:
            for att in pdf_attachments(key, user_id, payload.collection_key, payload.max_items,
                                       payload.max_attachments, transport):
                data = download_attachment(key, user_id, att["key"], transport)
                if not data or len(data) > MAX_BYTES[".pdf"]:
                    attachments["skipped"] += 1
                    continue
                name = re.sub(r"[^A-Za-z0-9À-ÿ_.,() \-]", "_", att["filename"])
                name = name if name.lower().endswith(".pdf") else name + ".pdf"
                try:
                    save_library_item(db, bucket, uid, name, ".pdf", data, "Zotero",
                                      f"Anexo PDF do item Zotero {att['parent']} (importado com consentimento).",
                                      origin={"provider": "zotero", "upstream_id": "R21",
                                              "zotero_user_id": user_id, "attachment_key": att["key"],
                                              "parent_item": att["parent"], "imported_at": now.isoformat(),
                                              "consent": True})
                    attachments["imported"] += 1
                except HTTPException as error:
                    # Quarentena (M13), limite da biblioteca ou arquivo inválido.
                    attachments["quarantined" if "quarentena" in str(error.detail) else "skipped"] += 1
        result["attachments"] = attachments
        if version is not None:
            # Só o número da versão; a chave do Zotero nunca é guardada.
            sync_ref.set({"owner_uid": uid, "zotero_user_id": user_id,
                          "collection_key": payload.collection_key, "last_version": version,
                          "updated_at": now.isoformat()})
        return result

    return router
