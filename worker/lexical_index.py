"""Índice lexical BM25 com SQLite FTS5 (M03, parte lexical do M04).

Origem: R06 (SQLite FTS5, https://www.sqlite.org/fts5.html). Plano: Scriptorium
V2, módulos M03 e M04. A parte vetorial (R05 FAISS + embeddings) fica para
depois da decisão sobre privacidade de embeddings externos.

Tokenizador unicode61 com remove_diacritics 2: "educacao" encontra "educação".
A consulta é montada só com termos entre aspas, então texto do usuário nunca
vira sintaxe FTS5 (operadores, colunas, NEAR etc.).
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections import Counter

INDEX_VERSION = "fts5-unicode61-bm25-1"
TOKEN = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
STOPWORDS = set("""
a o os as um uma uns umas de do da dos das em no na nos nas por pelo pela pelos pelas para
com sem sob sobre entre ate até que se ao aos à às e ou mas como mais menos muito muita muitos
muitas ser sao são foi era estar esta está estao estão isso isto esse essa este aquele aquela
nao não sim tambem também quando onde qual quais seu sua seus suas nosso nossa ele ela eles elas
pode podem deve devem ter tem têm havia sido assim ainda apenas cada outro outra outros outras
the of and to in for on with by from as at is are was were be been this that these those
it its into than then which who whom what when where how not no yes can could should would
will may might also such use used using our their there here an or but if
""".split())


def _fold(term: str) -> str:
    term = unicodedata.normalize("NFKD", term.lower())
    return "".join(c for c in term if not unicodedata.combining(c))


FOLDED_STOPWORDS = {_fold(s) for s in STOPWORDS}


def query_terms(text: str, max_terms: int = 24) -> list[str]:
    """Termos mais frequentes do texto, sem acento e sem palavras vazias."""
    counts = Counter(_fold(raw) for raw in TOKEN.findall(text or ""))
    return [t for t, _ in counts.most_common() if t not in FOLDED_STOPWORDS][:max_terms]


def fts_query(terms: list[str]) -> str:
    # Cada termo vira string FTS5 entre aspas (aspas internas duplicadas).
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)


class LexicalIndex:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5("
            "chunk_id UNINDEXED, source_id UNINDEXED, heading, body, "
            "tokenize='unicode61 remove_diacritics 2')")

    def add(self, chunks: list[dict]) -> None:
        self.db.executemany(
            "INSERT INTO chunks (chunk_id, source_id, heading, body) VALUES (?, ?, ?, ?)",
            [(c["chunk_id"], c["source_id"], " / ".join(c.get("heading_path") or []), c["text"])
             for c in chunks])
        self.db.commit()

    def search(self, terms: list[str], limit: int = 200) -> list[dict]:
        if not terms:
            return []
        # bm25(): menor é melhor. Títulos de seção pesam o dobro do corpo.
        rows = self.db.execute(
            "SELECT chunk_id, source_id, bm25(chunks, 0.0, 0.0, 2.0, 1.0) AS score "
            "FROM chunks WHERE chunks MATCH ? ORDER BY score LIMIT ?",
            (fts_query(terms), limit)).fetchall()
        return [{"chunk_id": r[0], "source_id": r[1], "score": round(r[2], 6), "method": "bm25"}
                for r in rows]

    def close(self) -> None:
        self.db.close()
