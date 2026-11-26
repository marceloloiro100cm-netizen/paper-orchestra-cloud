"""Índice persistente da biblioteca de cada conta e ficha de leitura (M03, M21).

Origem: R06 (SQLite FTS5, busca BM25) e R01 (Scriptorium). Plano V2:
- M03 "Fragmentação e indexação persistente": "índice persistente por conta";
- M21 "Fichamentos persistentes e cache": ficha por documento, por parser e
  política de fragmentação.

Como funciona:
- o worker já guarda, por conta e por conteúdo (SHA-256), o documento
  estruturado e os trechos em library/{uid}/derived/{parser}/{política}/{sha}.json;
- esta API junta esses trechos num índice SQLite FTS5 salvo em
  library/{uid}/index/fts-1.sqlite, com uma assinatura dos arquivos usados.
  Enquanto a biblioteca não muda, o índice é só baixado; quando muda, é
  refeito. Um documento entra no índice depois de ser lido uma vez numa
  pesquisa ou diagnóstico;
- a ficha de leitura é montada do mesmo arquivo derivado, sem modelo de
  linguagem: estrutura (títulos), páginas, trechos, termos frequentes, avisos
  de OCR e metadados do PDF. Fichamento por IA continua fora do escopo (custo
  na chave do pesquisador; depende de decisão do responsável).

Busca vetorial na biblioteca inteira exigiria a chave Gemini do pesquisador
na API, o que o desenho do BYOK evita; por isso a busca aqui é lexical (BM25).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query

try:
    from google.api_core.exceptions import NotFound
except Exception:  # pragma: no cover
    NotFound = ()

import library_search
from library_search import (INDEX_VERSION, MAX_DOCUMENTS, MAX_RESULTS, STOPWORDS, DERIVED,  # noqa: F401
                            build_index, derived_blobs, reading_card, search_index, signature, terms)

_CACHE_DIR = Path(tempfile.gettempdir()) / "scriptorium_libidx_cache"
_MAX_CACHED_INDEXES = 24


def _cache_path(bucket_id: int, uid: str, sig: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{bucket_id}:{uid}:{sig}".encode("utf-8")).hexdigest()[:24]
    return _CACHE_DIR / f"{digest}.sqlite"


def _prune_cache() -> None:
    try:
        files = sorted(_CACHE_DIR.glob("*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in files[_MAX_CACHED_INDEXES:]:
            stale.unlink(missing_ok=True)
    except OSError:
        pass


def fts_query(text: str) -> str:
    try:
        return library_search.fts_query(text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


def make_library_index_router(db, bucket, verify_user: Callable):
    router = APIRouter(prefix="/api/library", tags=["biblioteca"])
    dependency = Depends(verify_user)

    def active_items(uid: str) -> dict[str, dict]:
        docs = db.collection("library_items").where("owner_uid", "==", uid).limit(500).stream()
        return {d["id"]: d for d in (s.to_dict() for s in docs) if d.get("status") == "active"}

    def _read_json(blob):
        try:
            return json.loads(blob.download_as_bytes())
        except (NotFound, KeyError, FileNotFoundError, ValueError):
            return None

    @router.get("/search")
    def search(q: str = Query(min_length=2, max_length=200), user: dict = dependency):
        uid = user["uid"]
        query = fts_query(q)
        items = active_items(uid)
        blobs = derived_blobs(bucket, uid, items)
        sig = signature(blobs)
        index_blob = bucket.blob(f"library/{uid}/index/{INDEX_VERSION}.sqlite")
        meta_blob = bucket.blob(f"library/{uid}/index/{INDEX_VERSION}.json")
        rebuilt = False
        # Lê meta_blob uma única vez (antes lia duas vezes por consulta) e mantém cache local em /tmp por assinatura.
        meta_data = _read_json(meta_blob) if meta_blob.exists() else None
        current = meta_data.get("signature") if isinstance(meta_data, dict) else None
        cached = _cache_path(id(bucket), uid, sig)
        if current == sig and cached.exists() and cached.stat().st_size > 0:
            chunks = int((meta_data or {}).get("chunks", 0))
            os.utime(cached, None)
            results = search_index(str(cached), query) if chunks else []
        elif current == sig and index_blob.exists():
            tmp_target = str(cached) + ".tmp"
            index_blob.download_to_filename(tmp_target)
            os.replace(tmp_target, cached)
            _prune_cache()
            chunks = int((meta_data or {}).get("chunks", 0))
            results = search_index(str(cached), query) if chunks else []
        else:
            documents = []
            for item_id, blob in blobs.items():
                parsed = _read_json(blob)
                if parsed is not None:
                    documents.append((items[item_id], parsed))
            tmp_target = str(cached) + ".tmp"
            chunks = build_index(tmp_target, documents)
            os.replace(tmp_target, cached)
            _prune_cache()
            index_blob.upload_from_filename(str(cached), content_type="application/vnd.sqlite3")
            meta_blob.upload_from_string(json.dumps({"signature": sig, "chunks": chunks,
                                                     "documents": len(documents)}),
                                         content_type="application/json")
            rebuilt = True
            results = search_index(str(cached), query) if chunks else []
        return {"results": results, "indexed_documents": len(blobs), "active_documents": len(items),
                "index_rebuilt": rebuilt,
                "note": "Documentos entram no índice depois de lidos uma vez numa pesquisa ou diagnóstico."}

    @router.get("/items/{item_id}/card")
    def card(item_id: str, user: dict = dependency):
        if not re.fullmatch(r"[0-9a-f]{32}", item_id):
            raise HTTPException(404, "Arquivo não encontrado.")
        items = active_items(user["uid"])
        item = items.get(item_id)
        if not item:
            raise HTTPException(404, "Arquivo não encontrado.")
        blob = derived_blobs(bucket, user["uid"], {item_id: item}).get(item_id)
        if blob is None:
            raise HTTPException(404, "Ficha disponível depois que o documento for lido numa pesquisa ou diagnóstico.")
        metadata = None
        meta = bucket.blob(f"library/{user['uid']}/derived/meta-pdf/pymupdf-meta-1/{item['sha256']}.json")
        if meta.exists():
            try:
                metadata = json.loads(meta.download_as_bytes())
            except ValueError:
                metadata = None
        return reading_card(item, json.loads(blob.download_as_bytes()), metadata)

    return router
