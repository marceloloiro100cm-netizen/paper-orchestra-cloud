"""Reranking opcional dos trechos recuperados (M20).

Origens: R17 (FlagEmbedding, BAAI; licença MIT conferida no LICENSE) e R16
(InRanker, UNICAMP; licença Apache-2.0 conferida no LICENSE do commit e85f2c6).
Plano: Scriptorium V2, módulo M20 "Reranking especializado".

Uso documentado (READMEs conferidos em 24/11/2026):
- FlagEmbedding: FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=...).compute_score(
  [[consulta, trecho], ...], normalize=True) -> notas de 0 a 1.
- InRanker: from inranker import T5Ranker; T5Ranker(model_name_or_path=
  'unicamp-dl/InRanker-small').get_scores(query=..., docs=[...]).

Decisão do plano: só adotar em produção se o ganho medido no corpus de
referência for robusto (scripts/eval_retrieval.py --reranker ...). Por isso as
bibliotecas NÃO estão na imagem do worker; a flag SCRIPTORIUM_V2_RERANKER fica
em "none" e, se ligada sem a biblioteca instalada, a busca segue sem reranking
e a cobertura registra o motivo. Pesos dos modelos têm licença própria (a
conferir no model card antes de adotar).
"""
from __future__ import annotations

import os

VERSION = "reranker-1"
TOP_N = 50
DEFAULT_MODELS = {"bge": "BAAI/bge-reranker-v2-m3", "inranker": "unicamp-dl/InRanker-small"}


class Reranker:
    def __init__(self, name: str, model: str, score_fn):
        self.name, self.model, self._score = name, model, score_fn

    def scores(self, query: str, texts: list[str]) -> list[float]:
        values = self._score(query, texts)
        if isinstance(values, (int, float)):
            values = [values]
        values = [float(v) for v in values]
        if len(values) != len(texts):
            raise RuntimeError("Reranker devolveu quantidade de notas diferente")
        return values

    def info(self) -> dict:
        return {"name": self.name, "model": self.model, "version": VERSION,
                "upstream_id": "R17" if self.name == "bge" else "R16"}


def make_reranker(name: str | None = None, model: str | None = None):
    """Reranker configurado ou None. Biblioteca ausente nunca derruba a pesquisa."""
    name = (name or os.getenv("SCRIPTORIUM_V2_RERANKER", "none")).lower()
    model = model or os.getenv("SCRIPTORIUM_V2_RERANKER_MODEL") or DEFAULT_MODELS.get(name)
    if name == "bge":
        from FlagEmbedding import FlagReranker
        backend = FlagReranker(model, use_fp16=False)
        return Reranker("bge", model,
                        lambda q, docs: backend.compute_score([[q, d] for d in docs], normalize=True))
    if name == "inranker":
        from inranker import T5Ranker
        backend = T5Ranker(model_name_or_path=model)
        return Reranker("inranker", model, lambda q, docs: backend.get_scores(query=q, docs=docs))
    return None


def rerank_hits(hits: list[dict], by_id: dict, query: str, reranker, top_n: int = TOP_N) -> list[dict]:
    """Reordena os top_n primeiros resultados; o restante mantém a ordem original."""
    head, tail = hits[:top_n], hits[top_n:]
    if not head:
        return hits
    scores = reranker.scores(query, [by_id[h["chunk_id"]]["text"] for h in head])
    order = sorted(range(len(head)), key=lambda i: (-scores[i], i))
    reranked = []
    for new_rank, i in enumerate(order, start=1):
        reranked.append({**head[i], "rerank_score": round(scores[i], 6), "rerank_rank": new_rank,
                         "pre_rerank_rank": i + 1})
    return reranked + tail
