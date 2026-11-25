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
import sqlite3
import tempfile
from collections import Counter
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query

INDEX_VERSION = "fts-1"
MAX_DOCUMENTS = 200
MAX_RESULTS = 20
STOPWORDS = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem
sobre entre e ou que se sua seu suas seus como mais menos muito ao aos à às é são foi ser ter
the of and to in for on with by an be is are was were this that from as at or not it its""".split())
DERIVED = re.compile(r"library/[^/]+/derived/([a-z0-9-]+)/([a-z0-9-]+)/([0-9a-f]{64})\.json")


def terms(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[a-zà-ÿ]{4,}", (text or "").lower())
    counts = Counter(w for w in words if w not in STOPWORDS)
    return [w for w, _ in counts.most_common(limit)]


def fts_query(text: str) -> str:
    """Consulta FTS5 segura: só palavras, entre aspas, unidas por OR."""
    words = [w for w in re.findall(r"[\wÀ-ÿ]{2,}", text or "") if w.lower() not in STOPWORDS][:12]
    if not words:
        raise HTTPException(422, "Informe ao menos uma palavra para buscar.")
    return " OR ".join('"' + w.replace('"', "") + '"' for w in words)


def _updated(blob) -> float:
    return blob.updated.timestamp() if getattr(blob, "updated", None) else 0.0


def derived_blobs(bucket, owner_uid: str, items: dict[str, dict]) -> dict[str, object]:
    """Arquivo derivado mais recente por item ativo (ignora embeddings e metadados)."""
    by_sha = {i["sha256"]: i for i in items.values() if i.get("sha256")}
    chosen: dict[str, object] = {}
    for blob in bucket.list_blobs(prefix=f"library/{owner_uid}/derived/"):
        match = DERIVED.fullmatch(blob.name)
        if not match or match.group(1).startswith(("emb-", "meta-")):
            continue
        item = by_sha.get(match.group(3))
        if not item:
            continue
        current = chosen.get(item["id"])
        if current is None or _updated(blob) > _updated(current):
            chosen[item["id"]] = blob
    return dict(list(chosen.items())[:MAX_DOCUMENTS])


def signature(blobs: dict[str, object]) -> str:
    parts = sorted(f"{item_id}:{b.name}:{b.generation}" for item_id, b in blobs.items())
    return hashlib.sha256((INDEX_VERSION + "\n" + "\n".join(parts)).encode()).hexdigest()


def build_index(path: str, documents: list[tuple[dict, dict]]) -> int:
    """documents: (item, payload derivado). Devolve o número de trechos indexados."""
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE VIRTUAL TABLE chunks USING fts5(text, heading, item_id UNINDEXED, "
                     "name UNINDEXED, chunk_id UNINDEXED, pages UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
        total = 0
        for item, payload in documents:
            for chunk in payload.get("chunks") or []:
                pages = chunk.get("pages")
                conn.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)", (
                    chunk.get("text", ""), " > ".join(chunk.get("heading_path") or []), item["id"],
                    item.get("name", ""), chunk.get("chunk_id", ""),
                    f"{pages[0]}-{pages[1]}" if pages else ""))
                total += 1
        conn.commit()
        return total
    finally:
        conn.close()


def search_index(path: str, query: str, limit: int = MAX_RESULTS) -> list[dict]:
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT item_id, name, chunk_id, pages, heading, "
            "snippet(chunks, 0, '[', ']', ' … ', 24), bm25(chunks) "
            "FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks) LIMIT ?", (query, limit)).fetchall()
    finally:
        conn.close()
    return [{"item_id": r[0], "name": r[1], "chunk_id": r[2], "pages": r[3], "heading": r[4],
             "snippet": r[5], "score": round(-r[6], 3)} for r in rows]


def reading_card(item: dict, payload: dict, metadata: dict | None = None) -> dict:
    """M21: ficha de leitura sem IA, a partir do documento estruturado em cache."""
    chunks = payload.get("chunks") or []
    document = payload.get("document") or {}
    headings = list(dict.fromkeys(" > ".join(c.get("heading_path") or []) for c in chunks
                                  if c.get("heading_path")))
    return {
        "schema": "scriptorium.reading_card/1",
        "item": {"id": item["id"], "name": item.get("name"), "format": item.get("format"),
                 "sha256": item.get("sha256")},
        "parser": document.get("parser"), "parser_version": document.get("parser_version"),
        "chunk_policy": chunks[0].get("chunk_policy") if chunks else None,
        "pages_total": document.get("pages_total"), "pages_processed": document.get("pages_processed"),
        "chunks": len(chunks), "characters": sum(c.get("char_count", 0) for c in chunks),
        "structure": headings[:40],
        "frequent_terms": terms(" ".join(c.get("text", "") for c in chunks), 20),
        "opening": (chunks[0].get("text", "")[:700] if chunks else ""),
        "ocr_pages_flagged": [p.get("page") for p in (document.get("ocr") or {}).get("pages_flagged", [])],
        "warnings": document.get("warnings", []),
        "metadata": metadata or {},
        "limitations": [
            "Ficha montada sem IA: estrutura, termos e abertura vêm do texto extraído.",
            "Termos frequentes não são palavras-chave do autor.",
        ],
    }


def make_library_index_router(db, bucket, verify_user: Callable):
    router = APIRouter(prefix="/api/library", tags=["biblioteca"])
    dependency = Depends(verify_user)

    def active_items(uid: str) -> dict[str, dict]:
        docs = db.collection("library_items").where("owner_uid", "==", uid).limit(500).stream()
        return {d["id"]: d for d in (s.to_dict() for s in docs) if d.get("status") == "active"}

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
        with tempfile.TemporaryDirectory(prefix="libidx_") as tmp:
            path = os.path.join(tmp, "index.sqlite")
            current = None
            if meta_blob.exists():
                try:
                    current = json.loads(meta_blob.download_as_bytes()).get("signature")
                except ValueError:
                    current = None
            if current == sig and index_blob.exists():
                index_blob.download_to_filename(path)
                chunks = json.loads(meta_blob.download_as_bytes()).get("chunks", 0)
            else:
                documents = []
                for item_id, blob in blobs.items():
                    try:
                        documents.append((items[item_id], json.loads(blob.download_as_bytes())))
                    except ValueError:
                        continue
                chunks = build_index(path, documents)
                index_blob.upload_from_filename(path, content_type="application/vnd.sqlite3")
                meta_blob.upload_from_string(json.dumps({"signature": sig, "chunks": chunks,
                                                         "documents": len(documents)}),
                                             content_type="application/json")
                rebuilt = True
            results = search_index(path, query) if chunks else []
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
