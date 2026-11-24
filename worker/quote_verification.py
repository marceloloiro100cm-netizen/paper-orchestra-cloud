"""Verificação de citações literais e ponteiros contra as fontes armazenadas (M05).

Origem: R12 (estudo MIT sobre citações por ponteiros: a citação literal deve
vir da fonte armazenada, não do texto digitado pelo modelo) e R01.
Plano: Scriptorium V2, módulo M05 "Citações por ponteiros resolvidos".

O motor original (R02) ainda escreve o texto final; por isso este módulo
CONFERE depois da geração: cada trecho entre aspas do LaTeX final é procurado
nos trechos das fontes anexadas e cada ponteiro [trecho id] é resolvido.
- found: aparece literalmente (ignorando acentos, caixa e pontuação);
- approximate: >= 80% das sequências de 5 palavras aparecem na mesma fonte;
- not_found_in_sources: não está nas fontes anexadas. Pode vir de uma obra da
  bibliografia que não foi anexada, ou ter sido inventada: conferir.
"""
from __future__ import annotations

import re
from collections import defaultdict

from latex_text import body_of, fold, strip_commands

VERSION = "quote-verification-1"
MIN_QUOTE_WORDS = 4
APPROXIMATE_RATIO = 0.8
# Limites de tamanho evitam que um par de aspas solto "engula" parágrafos.
QUOTE_PATTERNS = [
    re.compile(r"``(.{8,1500}?)''", re.S),
    re.compile(r"\\enquote\*?\{((?:[^{}]|\{[^{}]*\}){8,1500})\}", re.S),
    re.compile(r"\\textquotedblleft\s*(.{8,1500}?)\\textquotedblright", re.S),
    re.compile(r"\u201c([^\u201d]{8,1500})\u201d"),
    re.compile(r"(?<![\w\\])\"([^\"\n]{8,600})\"(?!\w)"),
]
POINTER = re.compile(r"trecho\s+([0-9a-f]{12}-\d{4}-[0-9a-f]{8})", re.IGNORECASE)


def extract_quotes(tex: str) -> list[str]:
    body = body_of(tex)
    found, seen = [], set()
    for pattern in QUOTE_PATTERNS:
        for match in pattern.finditer(body):
            text = strip_commands(match.group(1))
            if len(fold(text).split()) >= MIN_QUOTE_WORDS and fold(text) not in seen:
                seen.add(fold(text))
                found.append(text)
    return found


def _shingles(words: list[str], n: int = 5) -> set[tuple]:
    if len(words) < n:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


class SourceText:
    """Texto normalizado de uma fonte, com mapa de posição para trecho."""

    def __init__(self, chunks: list[dict]):
        self.parts, self.spans, offset = [], [], 0
        for chunk in sorted(chunks, key=lambda c: c["index"]):
            folded = fold(chunk["text"])
            self.parts.append(folded)
            self.spans.append((offset, offset + len(folded), chunk))
            offset += len(folded) + 1
        self.text = " ".join(self.parts)
        self.shingles = _shingles(self.text.split())

    def chunk_at(self, position: int) -> dict:
        for start, end, chunk in self.spans:
            if start <= position <= end:
                return chunk
        return self.spans[-1][2]


def verify(tex: str, chunks: list[dict], sources_meta: dict) -> dict:
    by_source = defaultdict(list)
    for chunk in chunks:
        by_source[chunk["source_id"]].append(chunk)
    texts = {sid: SourceText(items) for sid, items in by_source.items()}
    chunk_ids = {c["chunk_id"]: c for c in chunks}
    results = []
    for quote in extract_quotes(tex):
        folded = fold(quote)
        record = {"quote": quote[:300], "status": "no_sources_attached" if not texts else "not_found_in_sources"}
        best = (0.0, None)
        for sid, source in texts.items():
            position = source.text.find(folded)
            if position >= 0:
                chunk = source.chunk_at(position)
                record.update(status="found", overlap=1.0, **_where(chunk, sid, sources_meta))
                break
            shingles = _shingles(folded.split())
            ratio = len(shingles & source.shingles) / len(shingles) if shingles else 0.0
            if ratio > best[0]:
                best = (ratio, sid)
        if record["status"] == "not_found_in_sources" and best[0] >= APPROXIMATE_RATIO:
            sid = best[1]
            first = next(iter(_shingles(folded.split())))
            position = texts[sid].text.find(" ".join(first))
            chunk = texts[sid].chunk_at(max(position, 0))
            record.update(status="approximate", overlap=round(best[0], 3), **_where(chunk, sid, sources_meta))
        elif record["status"] == "not_found_in_sources":
            record["overlap"] = round(best[0], 3)
        results.append(record)
    pointers = []
    for chunk_id in dict.fromkeys(m.group(1).lower() for m in POINTER.finditer(tex)):
        chunk = chunk_ids.get(chunk_id)
        pointers.append({"chunk_id": chunk_id, "status": "valid" if chunk else "unknown",
                         **(_where(chunk, chunk["source_id"], sources_meta) if chunk else {})})
    counts = defaultdict(int)
    for item in results:
        counts[item["status"]] += 1
    return {
        "version": VERSION, "quotes": results, "pointers": pointers,
        "summary": {"quotes": len(results), **counts,
                    "pointers_valid": sum(p["status"] == "valid" for p in pointers),
                    "pointers_unknown": sum(p["status"] == "unknown" for p in pointers)},
        "limitations": [
            "Só confere citações literais entre aspas e ponteiros [trecho id]; paráfrases não são verificadas aqui.",
            "'Não encontrada nas fontes' pode significar obra da bibliografia não anexada: conferir no original.",
        ],
    }


def _where(chunk: dict, source_id: str, meta: dict) -> dict:
    return {"source_id": source_id, "source_name": meta.get(source_id, {}).get("name", ""),
            "chunk_id": chunk["chunk_id"], "pages": chunk.get("pages")}
