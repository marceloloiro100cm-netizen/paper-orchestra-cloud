"""Cobertura das fontes agrupada por autor, época e tema (M09).

Origem: R13 (GapView, UC Irvine) como referência de desenho, sem código
copiado; R37 (PyMuPDF) para ler os metadados do PDF. Plano: Scriptorium V2,
módulo M09 "Mapa de omissões e cobertura": "agregar por autor, época e tema".

O que entra em cada agrupamento:
- autor: primeiro autor dos metadados do PDF (campo Author). Sem metadado, o
  grupo é "não informado"; o sistema não adivinha autoria pelo texto;
- época: ano encontrado na primeira página (heurística, rotulada como tal) ou,
  na falta dele, o ano de criação do arquivo PDF (rotulado como tal), agrupado
  por década. O ano do arquivo pode ser diferente do ano de publicação;
- tema: as perguntas ou subtópicos da ideia (mesma extração do M16) e quantos
  trechos LIDOS pelos agentes de cada fonte tocam cada tema.

Limitação explícita: é um retrato do que os agentes receberam, não um mapa da
literatura. Baixa cobertura pode ser limitação da busca.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date

from lexical_index import query_terms

VERSION = "coverage-facets-1"
META_POLICY = "pymupdf-meta-1"
MIN_SHARED_TERMS = 2
YEAR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")


def _first_author(raw: str) -> str:
    raw = re.sub(r"\s+", " ", raw or "").strip(" ;,")
    if not raw:
        return ""
    first = re.split(r";| and | e |&|\|", raw)[0].strip(" ,")
    return first[:80]


def _year_from_text(text: str, today: date | None = None) -> int | None:
    limit = (today or date.today()).year
    years = [int(y) for y in YEAR.findall(text or "") if int(y) <= limit]
    if not years:
        return None
    # O ano mais frequente no início do documento (cabeçalho, copyright, citação sugerida).
    return Counter(years).most_common(1)[0][0]


def _pdf_metadata(data: bytes) -> dict:
    from pdf_backend import fitz  # PyMuPDF (R37)
    with fitz.open(stream=data, filetype="pdf") as doc:
        meta = doc.metadata or {}
    created = str(meta.get("creationDate") or "")
    match = re.search(r"(19|20)\d\d", created)
    return {"author": _first_author(str(meta.get("author") or "")),
            "pdf_title": str(meta.get("title") or "")[:200],
            "file_year": int(match.group()) if match else None}


def source_metadata(entry: dict, fetch_bytes, cache=None) -> dict:
    """Metadados mínimos por fonte, com cache privado por SHA-256 (M21)."""
    sha = entry.get("sha256") or ""
    key = f"meta-pdf/{META_POLICY}/{sha}" if re.fullmatch(r"[0-9a-f]{64}", sha) else None
    if cache is not None and key:
        try:
            raw = cache.get(key)
            if raw:
                return json.loads(raw.decode("utf-8"))
        except Exception:
            pass
    meta = {"author": "", "pdf_title": "", "file_year": None}
    if entry.get("format") == "pdf":
        try:
            meta = _pdf_metadata(fetch_bytes(entry["object_path"]))
        except Exception:
            pass
    if cache is not None and key:
        try:
            cache.put(key, json.dumps(meta, ensure_ascii=False).encode("utf-8"))
        except Exception:
            pass
    return meta


def _epoch(meta: dict, first_text: str, today: date | None = None) -> tuple[str, str]:
    year = _year_from_text(first_text[:3000], today)
    origin = "primeira página (heurística)"
    if year is None and meta.get("file_year"):
        year, origin = meta["file_year"], "data do arquivo PDF (pode diferir da publicação)"
    if year is None:
        return "não informada", "sem ano encontrado"
    return f"{year // 10 * 10}s", f"{year} · {origin}"


def build_facets(questions: list[dict], chunks: list[dict], selected_ids: list[str],
                 sources_meta: dict, metadata: dict[str, dict], today: date | None = None) -> dict:
    """Agrupa os trechos lidos pelos agentes por autor, década e tema."""
    selected = set(selected_ids)
    by_source: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        by_source[chunk["source_id"]].append(chunk)
    sources, authors, epochs = [], defaultdict(lambda: {"sources": 0, "chunks_selected": 0}), \
        defaultdict(lambda: {"sources": 0, "chunks_selected": 0})
    for sid, meta in sources_meta.items():
        own = sorted(by_source.get(sid, []), key=lambda c: c.get("index", 0))
        read = [c for c in own if c["chunk_id"] in selected]
        info = metadata.get(sid, {})
        author = info.get("author") or "não informado"
        epoch, year_note = _epoch(info, own[0]["text"] if own else "", today)
        sources.append({"source_id": sid, "name": meta.get("name", ""), "author": author,
                        "epoch": epoch, "year_note": year_note,
                        "chunks_total": len(own), "chunks_selected": len(read)})
        for bucket, label in ((authors, author), (epochs, epoch)):
            bucket[label]["sources"] += 1
            bucket[label]["chunks_selected"] += len(read)
    themes = []
    read_chunks = [c for c in chunks if c["chunk_id"] in selected]
    for question in questions:
        terms = set(query_terms(question["text"]))
        per_source = Counter()
        for chunk in read_chunks:
            if len(terms & set(query_terms(chunk["text"], 400))) >= MIN_SHARED_TERMS:
                per_source[chunk["source_id"]] += 1
        themes.append({
            "kind": question.get("kind"), "text": question["text"],
            "chunks_selected": sum(per_source.values()),
            "sources": {sources_meta.get(s, {}).get("name", s): n for s, n in per_source.most_common()},
            "coverage": ("lacuna" if not per_source else
                         "uma_fonte" if len(per_source) == 1 else "varias_fontes"),
        })
    return {
        "version": VERSION,
        "by_author": dict(sorted(authors.items(), key=lambda kv: -kv[1]["chunks_selected"])),
        "by_epoch": dict(sorted(epochs.items())),
        "by_theme": themes,
        "sources": sources,
        "limitations": [
            "Retrato do que os agentes leram, não da literatura existente.",
            "Autor vem do metadado do PDF; muitos PDFs não o preenchem ('não informado').",
            "A época usa o ano da primeira página (heurística) ou a data do arquivo; confira antes de citar.",
            f"Tema: trecho conta quando divide ao menos {MIN_SHARED_TERMS} termos com a pergunta ou subtópico.",
        ],
    }
