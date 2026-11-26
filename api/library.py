"""Biblioteca acadêmica privada e persistente no Firestore/Cloud Storage.

Arquivos são material de pesquisa NÃO CONFIÁVEL, nunca instruções operacionais.
Somente o backend autenticado pode ler ou alterar metadados e objetos.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from abnt_refs import (
    DOI_RE,
    READING_STATUSES,
    STUDY_ROLES,
    bib_entry_to_bibtex,
    check_citation_coherence,
    export_library_references,
    find_duplicates,
    format_abnt_bundle,
    item_duplicate_keys,
    normalize_doi,
    parse_references_text,
    stable_key,
)
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
# Contexto padrão (8 fontes, 75 mil caracteres) ou ampliado (20 fontes, 300 mil),
# escolhido por pesquisa. Mesma tabela em worker/context_limits.py.
CONTEXT_LIMITS = {
    "padrao": {"max_sources": 8, "per_source_chars": 20_000, "total_chars": 75_000},
    "ampliado": {"max_sources": 20, "per_source_chars": 30_000, "total_chars": 300_000},
}
MAX_SELECTED_SOURCES = max(v["max_sources"] for v in CONTEXT_LIMITS.values())


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
    out = {key: record.get(key) for key in (
        "id", "name", "format", "size", "collection", "description", "sha256",
        "created_at", "archived_at", "status", "origin", "guard", "bib_entry",
    )}
    out["role"] = record.get("role") or ""
    out["reading_status"] = record.get("reading_status") or "a_ler"
    out["exclude_reason"] = record.get("exclude_reason") or ""
    out["study_notes"] = record.get("study_notes") or []
    out["abnt"] = format_abnt_bundle(record.get("bib_entry"), str(record.get("name") or ""))
    return out


def quarantine_message(guard: dict) -> str:
    reasons = "; ".join(f["detail"] for f in guard["findings"] if f["severity"] == "alta")
    return ("Arquivo retido em quarentena e fora da biblioteca: " + reasons +
            " Ele não será usado em pesquisas. Se o arquivo for legítimo, gere um PDF novo"
            " (por exemplo, imprimindo para PDF) e envie de novo.")


def save_library_item(db, bucket, owner_uid: str, name: str, suffix: str, data: bytes,
                      collection_name: str, description: str, origin: dict | None = None,
                      bib_entry: dict | None = None, role: str = "") -> dict:
    """Grava original imutável no GCS e metadados no Firestore (upload, Zotero e referências)."""
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
        "role": role if role in STUDY_ROLES else "",
        "reading_status": "a_ler",
        "exclude_reason": "",
        "study_notes": [],
        "guard": {"version": guard["version"], "verdict": guard["verdict"],
                  "findings": guard["findings"][:12]},
    }
    if origin:
        document["origin"] = origin
    if bib_entry:
        document["bib_entry"] = bib_entry
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


def make_library_router(db, bucket, verify_user: Callable, fetch: Callable | None = None):
    router = APIRouter(prefix="/api/library", tags=["biblioteca"])
    dependencies = Depends(verify_user)
    collection = db.collection("library_items")

    def active_items(uid: str) -> list[dict]:
        docs = collection.where("owner_uid", "==", uid).limit(MAX_ITEMS_PER_OWNER + 50).stream()
        items = [doc.to_dict() for doc in docs if (doc.to_dict() or {}).get("status") == "active"]
        items.sort(key=lambda i: i.get("created_at") or "", reverse=True)
        return items

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

    @router.delete("/items/{item_id}")
    def delete_file(item_id: str, user: dict = dependencies):
        """Apaga de vez uma fonte (a interface pede confirmação antes).

        Remove o original, o registro e os dados derivados (trechos, vetores,
        metadados e fichamentos) quando nenhuma outra fonte da conta tem o mesmo
        conteúdo. Pesquisas antigas continuam no histórico com nome e SHA-256 da
        fonte, mas não conseguem mais abrir a página do PDF original.
        """
        uid = user["uid"]
        item = owned(item_id, user)
        original = bucket.blob(item["object_path"])
        if original.exists():
            original.delete()
        sha = item.get("sha256") or ""
        others = [s.to_dict() for s in collection.where("owner_uid", "==", uid).limit(MAX_ITEMS_PER_OWNER + 50).stream()]
        shared = any(o.get("id") != item_id and o.get("sha256") == sha for o in others)
        derived_removed = 0
        if sha and not shared and re.fullmatch(r"[0-9a-f]{64}", sha):
            for blob in bucket.list_blobs(prefix=f"library/{uid}/derived/"):
                if blob.name.endswith(f"/{sha}.json") or f"/covers/{sha}_p" in blob.name:
                    blob.delete()
                    derived_removed += 1
        collection.document(item_id).delete()
        return {"id": item_id, "deleted": True, "derived_removed": derived_removed}

    @router.get("/items/{item_id}/cover")
    def render_cover(item_id: str, page: int = Query(default=1, ge=1, le=5), user: dict = dependencies):
        """Item 7 + Onda 1 (G3): renderiza e cacheia no GCS a capa (pág. 1..5) do PDF."""
        item = owned(item_id, user)
        if item.get("status") != "active" or item.get("format") != "pdf":
            raise HTTPException(404, "Capa disponível apenas para arquivos PDF ativos.")
        uid = user["uid"]
        sha = item.get("sha256") or ""
        cache_prefix = f"library/{uid}/derived/covers/{sha}_p{page}" if re.fullmatch(r"[0-9a-f]{64}", sha) else ""
        if cache_prefix:
            cached_png = bucket.blob(cache_prefix + ".png")
            if cached_png.exists():
                png = cached_png.download_as_bytes()
                meta_blob = bucket.blob(cache_prefix + ".json")
                meta = {}
                if meta_blob.exists():
                    try:
                        meta = json.loads(meta_blob.download_as_bytes())
                    except ValueError:
                        meta = {}
                return Response(
                    content=png, media_type="image/png",
                    headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff",
                             "X-Scriptorium-Page": str(meta.get("page", page)),
                             "X-Scriptorium-Pages-Total": str(meta.get("total", page))},
                )
        blob = bucket.blob(item["object_path"])
        if not blob.exists():
            raise HTTPException(404, "Arquivo indisponível no armazenamento.")
        from pdf_render import fitz
        with fitz.open(stream=blob.download_as_bytes(), filetype="pdf") as doc:
            if doc.page_count == 0:
                raise HTTPException(404, "PDF sem páginas.")
            target = min(page, doc.page_count)
            png = doc[target - 1].get_pixmap(dpi=115, alpha=False).tobytes("png")
            total = doc.page_count
        if cache_prefix:
            try:
                bucket.blob(cache_prefix + ".png").upload_from_string(png, content_type="image/png")
                bucket.blob(cache_prefix + ".json").upload_from_string(
                    json.dumps({"page": target, "total": total}), content_type="application/json")
            except Exception:
                pass
        return Response(
            content=png, media_type="image/png",
            headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff",
                     "X-Scriptorium-Page": str(target), "X-Scriptorium-Pages-Total": str(total)},
        )

    @router.put("/items/{item_id}/reference")
    async def save_reference(item_id: str, request: Request, user: dict = dependencies):
        """Item 6: confirma/edita a ficha bibliográfica na biblioteca (vale para todos os projetos)."""
        import mcp_flow as flow
        item = owned(item_id, user)
        if item.get("status") != "active":
            raise HTTPException(409, "Apenas fontes ativas podem receber ficha bibliográfica.")
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422, "Dados inválidos.") from None
        fields, errors = flow.check_reference_proposal(body if isinstance(body, dict) else {})
        if errors:
            raise HTTPException(422, " ".join(errors))
        existing_key = ((item.get("bib_entry") or {}).get("key") or "").strip()
        key = existing_key if existing_key and not existing_key.startswith("fonte_") else flow.stable_bib_key(fields)
        bib_entry = {
            "type": (body.get("tipo") or "article"),
            "key": key,
            "fields": fields,
            "how": "confirmada_pelo_pesquisador",
            "updated_at": utc_now(),
        }
        collection.document(item_id).update({"bib_entry": bib_entry})
        return {"id": item_id, "bib_entry": bib_entry}

    @router.post("/items/{item_id}/archive")
    def archive_file(item_id: str, user: dict = dependencies):
        item = owned(item_id, user)
        if item.get("status") in ("active", "quarantined"):
            collection.document(item_id).update({"status": "archived", "archived_at": utc_now()})
        # Arquivar não apaga o original: pesquisas vinculadas continuam reproduzíveis.
        return {"status": "archived", "id": item_id}

    # --- Fase 1: Organização de Estudo, Fichamento por Página, DOI/BibTeX/RIS e ABNT ---

    @router.patch("/items/{item_id}/study")
    async def update_study_meta(item_id: str, request: Request, user: dict = dependencies):
        """Atualiza papel metodológico, status de leitura, coleção ou descrição da fonte."""
        item = owned(item_id, user)
        if item.get("status") != "active":
            raise HTTPException(409, "Apenas fontes ativas podem ser organizadas.")
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422, "Dados inválidos.") from None
        if not isinstance(body, dict):
            raise HTTPException(422, "Dados inválidos.")
        updates: dict = {}
        if "role" in body:
            role = str(body.get("role") or "").strip()
            if role not in STUDY_ROLES:
                raise HTTPException(422, "Papel metodológico inválido.")
            updates["role"] = role
        if "reading_status" in body:
            status = str(body.get("reading_status") or "a_ler").strip()
            if status not in READING_STATUSES:
                raise HTTPException(422, "Status de leitura inválido.")
            updates["reading_status"] = status
        if "exclude_reason" in body:
            updates["exclude_reason"] = str(body.get("exclude_reason") or "").strip()[:240]
        if "collection" in body:
            col = str(body.get("collection") or "").strip()[:60]
            if not col:
                raise HTTPException(422, "Informe uma coleção.")
            updates["collection"] = col
        if "description" in body:
            updates["description"] = str(body.get("description") or "").strip()[:300]
        if not updates:
            raise HTTPException(422, "Nenhum campo para atualizar.")
        collection.document(item_id).update(updates)
        merged = {**item, **updates}
        return {"item": exposed(merged)}

    @router.post("/items/{item_id}/notes", status_code=201)
    async def add_study_note(item_id: str, request: Request, user: dict = dependencies):
        """Salva um fichamento humano vinculado à página da fonte (usado no /citar e no Guia)."""
        item = owned(item_id, user)
        if item.get("status") != "active":
            raise HTTPException(409, "Apenas fontes ativas podem receber fichamentos.")
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422, "Dados inválidos.") from None
        if not isinstance(body, dict):
            raise HTTPException(422, "Dados inválidos.")
        quote = str(body.get("quote") or "").strip()[:1500]
        note = str(body.get("note") or "").strip()[:1500]
        if not quote and not note:
            raise HTTPException(422, "Informe ao menos um trecho da fonte ou uma anotação sua.")
        notes = list(item.get("study_notes") or [])
        if len(notes) >= 50:
            raise HTTPException(409, "Limite de 50 fichamentos por fonte atingido.")
        entry = {
            "id": uuid.uuid4().hex[:12],
            "page": str(body.get("page") or "").strip()[:24],
            "quote": quote,
            "note": note,
            "tag": str(body.get("tag") or "").strip()[:40],
            "support_checked": bool(body.get("support_checked", False)),
            "created_at": utc_now(),
        }
        notes.append(entry)
        collection.document(item_id).update({"study_notes": notes})
        return {"note": entry, "study_notes": notes}

    @router.patch("/items/{item_id}/notes/{note_id}")
    async def edit_study_note(item_id: str, note_id: str, request: Request, user: dict = dependencies):
        item = owned(item_id, user)
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422, "Dados inválidos.") from None
        if not isinstance(body, dict):
            raise HTTPException(422, "Dados inválidos.")
        notes = list(item.get("study_notes") or [])
        target = next((n for n in notes if n.get("id") == note_id), None)
        if target is None:
            raise HTTPException(404, "Fichamento não encontrado.")
        if "page" in body:
            target["page"] = str(body.get("page") or "").strip()[:24]
        if "quote" in body:
            target["quote"] = str(body.get("quote") or "").strip()[:1500]
        if "note" in body:
            target["note"] = str(body.get("note") or "").strip()[:1500]
        if "tag" in body:
            target["tag"] = str(body.get("tag") or "").strip()[:40]
        if "support_checked" in body:
            target["support_checked"] = bool(body.get("support_checked"))
        if not target.get("quote") and not target.get("note"):
            raise HTTPException(422, "O fichamento precisa de trecho ou anotação.")
        target["updated_at"] = utc_now()
        collection.document(item_id).update({"study_notes": notes})
        return {"note": target, "study_notes": notes}

    @router.delete("/items/{item_id}/notes/{note_id}")
    def remove_study_note(item_id: str, note_id: str, user: dict = dependencies):
        item = owned(item_id, user)
        notes = list(item.get("study_notes") or [])
        remaining = [n for n in notes if n.get("id") != note_id]
        if len(remaining) == len(notes):
            raise HTTPException(404, "Fichamento não encontrado.")
        collection.document(item_id).update({"study_notes": remaining})
        return {"deleted": True, "study_notes": remaining}

    @router.post("/import-references", status_code=201)
    async def import_references(request: Request, user: dict = dependencies):
        """Importa referências em 1 clique por BibTeX, RIS ou lista de DOIs (com deduplicação)."""
        from oa_import import meta_to_bib_entry, resolve_doi, safe_get

        uid = user["uid"]
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422, "Dados inválidos.") from None
        if not isinstance(body, dict):
            raise HTTPException(422, "Dados inválidos.")
        raw_text = str(body.get("text") or "").strip()
        if not raw_text:
            raise HTTPException(422, "Cole ao menos um DOI, registro BibTeX ou RIS.")
        if len(raw_text) > 500_000:
            raise HTTPException(413, "Texto muito grande (limite de 500 KB por importação).")
        col_name = str(body.get("collection") or "Referências").strip()[:60] or "Referências"
        role = str(body.get("role") or "").strip()
        if role not in STUDY_ROLES:
            role = ""

        current = active_items(uid)
        seen_keys: set[str] = set()
        for existing in current:
            seen_keys.update(item_duplicate_keys(existing))

        # 1) Tenta BibTeX ou RIS direto
        candidates = parse_references_text(raw_text)
        results = []

        # 2) Se não for BibTeX/RIS, trata como lista de DOIs (até 30 por vez)
        if not candidates:
            lines = [ln.strip() for ln in re.split(r"[\r\n]+", raw_text) if ln.strip()]
            dois = []
            for ln in lines[:30]:
                d = normalize_doi(ln)
                if d:
                    dois.append(d)
                else:
                    results.append({"input": ln[:120], "status": "falhou",
                                    "reason": "Formato não reconhecido. Use DOI (10.xxxx/...), BibTeX (@article{...}) ou RIS (TY  - ...)."})
            fetcher = fetch or safe_get
            for doi in dict.fromkeys(dois):
                if ("doi:" + doi) in seen_keys:
                    results.append({"input": doi, "status": "duplicado", "reason": "Já existe uma fonte com este DOI na biblioteca."})
                    continue
                try:
                    meta = resolve_doi(doi, fetcher)
                    bib = meta_to_bib_entry(meta)
                except ValueError as err:
                    results.append({"input": doi, "status": "falhou", "reason": f"DOI não encontrado no OpenAlex ({err})."})
                    continue
                if not bib:
                    results.append({"input": doi, "status": "falhou", "reason": "Metadados insuficientes para este DOI."})
                    continue
                bib["how"] = "doi"
                candidates.append(bib)

        if len(candidates) > 50:
            raise HTTPException(422, "Importe no máximo 50 referências por vez.")

        for bib in candidates:
            fields = bib.get("fields") or {}
            cand_keys = item_duplicate_keys({"bib_entry": bib})
            if cand_keys & seen_keys:
                results.append({
                    "input": fields.get("title") or fields.get("doi") or bib.get("key"),
                    "status": "duplicado",
                    "reason": "Referência já presente na sua biblioteca (mesmo DOI ou título e ano).",
                })
                continue
            bib_entry = {
                "type": bib.get("type") or "misc",
                "key": bib.get("key") or stable_key(fields),
                "fields": fields,
                "how": bib.get("how") or "confirmada_pelo_pesquisador",
                "updated_at": utc_now(),
            }
            bib_text = bib_entry_to_bibtex(bib_entry) + "\n"
            first_author = str(fields.get("author") or "").split(" and ")[0].split(",")[0].strip()
            year = str(fields.get("year") or "").strip()
            title = str(fields.get("title") or bib_entry["key"]).strip()
            raw_name = f"{first_author} {year} {title}".strip()
            safe_stem = re.sub(r"[^A-Za-z0-9À-ÿ_.,() \-]", " ", raw_name)
            safe_stem = re.sub(r"\s+", " ", safe_stem).strip()[:95] or bib_entry["key"]
            filename = f"{safe_stem}.bib"
            origin = {"provider": "referencia_importada", "doi": fields.get("doi") or None, "imported_at": utc_now()}
            try:
                doc = save_library_item(
                    db, bucket, uid, filename, ".bib", bib_text.encode("utf-8"),
                    col_name, f"Referência bibliográfica ({bib_entry['type']}).",
                    origin=origin, bib_entry=bib_entry, role=role,
                )
            except HTTPException as exc:
                results.append({"input": title[:120], "status": "falhou", "reason": str(exc.detail)})
                continue
            seen_keys.update(item_duplicate_keys(doc))
            results.append({"input": title[:120], "status": "importado", "item": exposed(doc)})

        counts = {"importado": 0, "duplicado": 0, "falhou": 0}
        for r in results:
            st = r.get("status", "falhou")
            counts[st] = counts.get(st, 0) + 1
        return {"results": results, "counts": counts}

    @router.get("/duplicates")
    def list_duplicates(user: dict = dependencies):
        """Lista possíveis duplicatas na biblioteca ativa (mesmo arquivo, DOI ou título+ano)."""
        groups = find_duplicates(active_items(user["uid"]))
        return {"duplicates": groups, "count": len(groups)}

    @router.get("/export")
    def export_references(
        fmt: str = Query(default="abnt", pattern="^(abnt|bib|ris)$"),
        only_included: bool = Query(default=False),
        role: str = Query(default=""),
        user: dict = dependencies,
    ):
        """Exporta referências da Biblioteca em ABNT NBR 6023:2018, BibTeX (.bib) ou RIS (.ris)."""
        items = active_items(user["uid"])
        if only_included:
            items = [i for i in items if i.get("reading_status") == "incluido"]
        if role:
            items = [i for i in items if i.get("role") == role]
        content, media_type, count = export_library_references(items, fmt=fmt)
        if count == 0:
            raise HTTPException(404, "Nenhuma referência bibliográfica encontrada para exportar.")
        ext = "txt" if fmt == "abnt" else fmt
        return Response(
            content=content.encode("utf-8"),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="scriptorium_referencias.{ext}"',
                "Cache-Control": "private, no-store",
                "X-Scriptorium-Count": str(count),
            },
        )

    @router.post("/check-citations")
    async def check_citations(request: Request, user: dict = dependencies):
        """Confere citações ABNT em um texto contra as fontes reais da Biblioteca."""
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422, "Dados inválidos.") from None
        text = str((body or {}).get("text") or "") if isinstance(body, dict) else ""
        if not text.strip():
            raise HTTPException(422, "Informe o texto para conferir citações.")
        return check_citation_coherence(text, active_items(user["uid"]))

    return router
