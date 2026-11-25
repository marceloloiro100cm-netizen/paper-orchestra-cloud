"""Importação de PDFs de acesso aberto por DOI ou link para a biblioteca.

Origem: R09 (OpenAlex API: localiza a versão aberta e os metadados pelo DOI)
e R01. Usado para trazer o corpus de referência (docs/corpus/selecao.json) e
qualquer artigo aberto sem baixar e reenviar à mão.

Segurança:
- só https; o servidor resolve o nome e recusa endereços privados, locais,
  de loopback ou de metadados da nuvem (evita SSRF), inclusive a cada
  redirecionamento (no máximo 3, conferidos um a um);
- tamanho máximo do PDF da biblioteca (8 MB) e assinatura %PDF;
- cada arquivo passa pela inspeção de upload (M13) em save_library_item;
- a origem (DOI, licença, endereço) fica registrada no item.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from library import MAX_BYTES, exposed, save_library_item

OPENALEX = "https://api.openalex.org/works/"
UA = "Scriptorium/1 (https://github.com/marceloloiro100cm-netizen/paper-orchestra-cloud)"
MAX_ITEMS = 30
TIMEOUT = 30
DOI = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)


class OpenAccessImport(BaseModel):
    items: list[str] = Field(min_length=1, max_length=MAX_ITEMS)
    collection: str = Field(default="Acesso aberto", max_length=60)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = build_opener(_NoRedirect)


def public_host(host: str, resolver=socket.getaddrinfo) -> bool:
    """True só se TODOS os endereços do nome forem públicos."""
    try:
        infos = resolver(host, 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return False
    addresses = {info[4][0] for info in infos}
    if not addresses:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            return False
    return True


def safe_get(url: str, max_bytes: int, accept: str, resolver=socket.getaddrinfo, opener=None) -> bytes:
    opener = opener or _OPENER
    for _ in range(4):
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or not public_host(parsed.hostname, resolver):
            raise ValueError("endereço não permitido")
        try:
            with opener.open(Request(url, headers={"User-Agent": UA, "Accept": accept}), timeout=TIMEOUT) as resp:
                data = resp.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError("arquivo acima do limite")
                return data
        except HTTPError as exc:
            location = exc.headers.get("Location") if exc.headers else None
            if exc.code in (301, 302, 303, 307, 308) and location:
                url = urljoin(url, location)
                continue
            raise ValueError(f"HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError):
            raise ValueError("sem resposta") from None
    raise ValueError("redirecionamentos demais")


def resolve_doi(doi: str, fetch) -> dict:
    work = json.loads(fetch(OPENALEX + "doi:" + quote(doi, safe="/"), 2_000_000, "application/json"))
    urls = []
    for loc in [work.get("best_oa_location") or {}] + list(work.get("locations") or []):
        if loc and loc.get("pdf_url") and loc["pdf_url"] not in urls:
            urls.append(loc["pdf_url"])
    authors = [((a.get("author") or {}).get("display_name") or "") for a in (work.get("authorships") or [])]
    return {"title": work.get("title") or doi, "year": work.get("publication_year"), "authors": authors[:6],
            "license": (work.get("best_oa_location") or {}).get("license"), "openalex": work.get("id"),
            "is_oa": (work.get("open_access") or {}).get("is_oa"), "pdf_urls": urls}


def file_name(meta: dict) -> str:
    first = (meta.get("authors") or ["documento"])[0].split()[-1:] or ["documento"]
    base = f"{first[0]} {meta.get('year') or ''} {meta.get('title') or ''}".strip()
    base = re.sub(r"[^A-Za-z0-9À-ÿ_.,() \-]", " ", base)
    return (re.sub(r"\s+", " ", base)[:100].strip() or "documento") + ".pdf"


def import_one(raw: str, fetch, save) -> dict:
    text = raw.strip()
    doi = DOI.match(text)
    meta, urls = {}, []
    if doi:
        try:
            meta = resolve_doi(doi.group(1), fetch)
        except ValueError as error:
            return {"item": text, "status": "falhou", "reason": f"DOI não encontrado no OpenAlex ({error})"}
        urls = meta["pdf_urls"]
        if not urls:
            return {"item": text, "status": "sem_pdf_aberto",
                    "reason": "O OpenAlex não indica PDF de acesso aberto para este DOI."}
    elif text.lower().startswith("https://"):
        urls = [text]
        meta = {"title": urlparse(text).path.rsplit("/", 1)[-1] or "documento"}
    else:
        return {"item": text, "status": "falhou", "reason": "Use um DOI (10.xxxx/...) ou um link https."}
    last = "sem PDF válido"
    for url in urls[:3]:
        try:
            data = fetch(url, MAX_BYTES[".pdf"], "application/pdf,*/*")
        except ValueError as error:
            last = str(error)
            continue
        if not data[:1024].lstrip().startswith(b"%PDF"):
            last = "o link não entrega um PDF (página de apresentação)"
            continue
        origin = {"provider": "acesso_aberto", "upstream_id": "R09", "doi": doi.group(1) if doi else None,
                  "openalex": meta.get("openalex"), "license": meta.get("license"), "source_url": url,
                  "imported_at": datetime.now(timezone.utc).isoformat()}
        try:
            item = save(file_name(meta) if doi else (meta["title"] if meta["title"].lower().endswith(".pdf")
                                                    else meta["title"] + ".pdf"), data, origin)
        except HTTPException as error:
            status = "retido" if "quarentena" in str(error.detail) else "falhou"
            return {"item": text, "status": status, "reason": str(error.detail)}
        return {"item": text, "status": "importado", "library_item": exposed(item)}
    return {"item": text, "status": "falhou", "reason": last}


def make_oa_import_router(db, bucket, verify_user: Callable, fetch=None):
    router = APIRouter(prefix="/api/library", tags=["biblioteca"])
    dependency = Depends(verify_user)

    @router.post("/import-open-access")
    def import_open_access(payload: OpenAccessImport, user: dict = dependency):
        uid = user["uid"]
        existing = {s.to_dict().get("sha256") for s in db.collection("library_items")
                    .where("owner_uid", "==", uid).limit(600).stream()
                    if (s.to_dict() or {}).get("status") == "active"}
        get = fetch or safe_get
        results = []

        def save(name, data, origin):
            import hashlib
            if hashlib.sha256(data).hexdigest() in existing:
                raise HTTPException(409, "Este PDF já está na sua biblioteca.")
            safe_name = re.sub(r"[^A-Za-z0-9À-ÿ_.,() \-]", "_", name)[:120]
            item = save_library_item(db, bucket, uid, safe_name, ".pdf", data, payload.collection or "Acesso aberto",
                                     f"Importado de acesso aberto{(' (DOI ' + origin['doi'] + ')') if origin.get('doi') else ''}.",
                                     origin=origin)
            existing.add(item["sha256"])
            return item

        for raw in dict.fromkeys(i.strip() for i in payload.items if i.strip()):
            result = import_one(raw, get, save)
            if result["status"] == "falhou" and "já está na sua biblioteca" in result.get("reason", ""):
                result["status"] = "ja_existia"
            results.append(result)
        counts = {}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        return {"results": results, "counts": counts}

    return router
