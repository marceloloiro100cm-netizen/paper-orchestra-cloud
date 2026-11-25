"""Busca BM25 (SQLite FTS5) e ficha de leitura sem IA, sem dependência de FastAPI.

Usado pela busca da biblioteca no site (library_index.py) e pelo servidor MCP
(mcp_server.py). A documentação do índice está em library_index.py.
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
        raise ValueError("Informe ao menos uma palavra para buscar.")
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
