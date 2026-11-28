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
UA = "Scriptorium/1 (https://github.com/marceloloiro100cm-netizen/scriptorium)"
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
        url = (loc or {}).get("pdf_url")
        # Muitos repositórios (SciELO etc.) aparecem no OpenAlex com http://; tenta a
        # mesma URL em https (o safe_get continua recusando qualquer http).
        if url and url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        if url and url not in urls:
            urls.append(url)
    authors = [((a.get("author") or {}).get("display_name") or "") for a in (work.get("authorships") or [])]
    primary_source = ((work.get("primary_location") or {}).get("source") or {})
    biblio = work.get("biblio") or {}
    pages = ""
    if biblio.get("first_page") and biblio.get("last_page"):
        pages = f"{biblio['first_page']}-{biblio['last_page']}"
    elif biblio.get("first_page"):
        pages = str(biblio["first_page"])
    return {
        "title": work.get("title") or doi,
        "year": work.get("publication_year"),
        "authors": authors[:10],
        "venue": primary_source.get("display_name") or "",
        "volume": str(biblio.get("volume") or ""),
        "number": str(biblio.get("issue") or ""),
        "pages": pages,
        "type": work.get("type") or "article",
        "doi": doi,
        "license": (work.get("best_oa_location") or {}).get("license"),
        "openalex": work.get("id"),
        "is_oa": (work.get("open_access") or {}).get("is_oa"),
        "pdf_urls": urls,
    }


def meta_to_bib_entry(meta: dict) -> dict | None:
    """Converte metadados do OpenAlex para o esquema `bib_entry` da Biblioteca."""
    from abnt_refs import normalize_doi, stable_key
    title = str(meta.get("title") or "").strip()
    authors = [str(a).strip() for a in (meta.get("authors") or []) if str(a).strip()]
    if not title and not authors:
        return None
    kind_map = {
        "article": "article",
        "journal-article": "article",
        "proceedings-article": "inproceedings",
        "book": "book",
        "book-chapter": "incollection",
        "dissertation": "phdthesis",
        "report": "techreport",
    }
    kind = kind_map.get(str(meta.get("type") or "").lower(), "article")
    fields = {
        "title": title,
        "author": " and ".join(authors),
        "year": str(meta.get("year") or ""),
    }
    if meta.get("venue"):
        fields["booktitle" if kind in ("inproceedings", "incollection") else "journal"] = str(meta["venue"]).strip()
    for k in ("volume", "number", "pages"):
        if meta.get(k):
            fields[k] = str(meta[k]).strip()
    doi_norm = normalize_doi(meta.get("doi"))
    if doi_norm:
        fields["doi"] = doi_norm
    return {
        "type": kind,
        "key": stable_key(fields),
        "fields": {k: v for k, v in fields.items() if v},
        "how": "openalex_importado",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


_META_PDF = re.compile(
    r"""<meta[^>]+name=["']citation_pdf_url["'][^>]+content=["']([^"']+)["']"""
    r"""|<meta[^>]+content=["']([^"']+)["'][^>]+name=["']citation_pdf_url["']""", re.IGNORECASE)
# OJS 3: a página do leitor aponta para ".../article/download/<artigo>/<arquivo>[/<id>]".
_OJS_DOWNLOAD = re.compile(r"""href=["'](https://[^"']+/article/download/\d+/\d+(?:/\d+)?)["']""", re.IGNORECASE)


def pdf_links_in_page(html: bytes, base: str) -> list[str]:
    """Links de PDF declarados na página de apresentação (Highwire/OJS/DSpace/SciELO).

    Só https; cada link ainda passa pelo safe_get (mesmas proteções contra SSRF).
    """
    text = html[:400_000].decode("utf-8", errors="replace")
    found = []
    for match in _META_PDF.finditer(text):
        found.append(urljoin(base, (match.group(1) or match.group(2)).replace("&amp;", "&")))
    for match in _OJS_DOWNLOAD.finditer(text):
        found.append(match.group(1).replace("&amp;", "&"))
    out = []
    for url in found:
        if url.startswith("https://") and url != base and url not in out:
            out.append(url)
    return out[:2]


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
    queue, tried, followed = list(urls[:3]), set(), 0
    while queue:
        url = queue.pop(0)
        if url in tried:
            continue
        tried.add(url)
        try:
            data = fetch(url, MAX_BYTES[".pdf"], "application/pdf,*/*")
        except ValueError as error:
            last = str(error)
            continue
        if not data[:1024].lstrip().startswith(b"%PDF"):
            last = "o link não entrega um PDF (página de apresentação)"
            # Página do artigo: segue o PDF que ela mesma declara (no máximo 2 saltos).
            if followed < 2:
                links = [u for u in pdf_links_in_page(data, url) if u not in tried]
                if links:
                    followed += 1
                    queue = links + queue
            continue
        origin = {"provider": "acesso_aberto", "upstream_id": "R09", "doi": doi.group(1) if doi else None,
                  "openalex": meta.get("openalex"), "license": meta.get("license"), "source_url": url,
                  "imported_at": datetime.now(timezone.utc).isoformat()}
        bib_entry = meta_to_bib_entry(meta) if doi else None
        try:
            item = save(file_name(meta) if doi else (meta["title"] if meta["title"].lower().endswith(".pdf")
                                                    else meta["title"] + ".pdf"), data, origin, bib_entry)
        except TypeError:
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
        active_records = [
            s.to_dict() for s in db.collection("library_items")
            .where("owner_uid", "==", uid).limit(600).stream()
            if (s.to_dict() or {}).get("status") == "active"
        ]
        existing = {r.get("sha256") for r in active_records if r.get("sha256")}
        from abnt_refs import normalize_doi
        existing_dois = {
            normalize_doi(((r.get("bib_entry") or {}).get("fields") or {}).get("doi") or (r.get("origin") or {}).get("doi"))
            for r in active_records
        } - {""}
        get = fetch or safe_get
        results = []

        def save(name, data, origin, bib_entry=None):
            import hashlib
            doi_norm = normalize_doi((origin or {}).get("doi"))
            if hashlib.sha256(data).hexdigest() in existing or (doi_norm and doi_norm in existing_dois):
                raise HTTPException(409, "Este PDF já está na sua biblioteca.")
            safe_name = re.sub(r"[^A-Za-z0-9À-ÿ_.,() \-]", "_", name)[:120]
            item = save_library_item(db, bucket, uid, safe_name, ".pdf", data, payload.collection or "Acesso aberto",
                                     f"Importado de acesso aberto{(' (DOI ' + origin['doi'] + ')') if origin.get('doi') else ''}.",
                                     origin=origin, bib_entry=bib_entry)
            existing.add(item["sha256"])
            if doi_norm:
                existing_dois.add(doi_norm)
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
