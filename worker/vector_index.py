"""Índice vetorial exato por produto interno (M03/M04, parte vetorial).

Origem: R43 (NumPy). Equivale ao IndexFlatIP do FAISS (R05) para vetores
normalizados (similaridade de cosseno), com resultado exato. Para o volume
atual (até 8 fontes, alguns milhares de trechos) a busca exata em NumPy é
rápida e evita uma dependência nativa a mais; o FAISS fica registrado para
quando o índice persistente por conta passar de dezenas de milhares de vetores.
"""
from __future__ import annotations

import numpy as np

BACKEND = "numpy-flat-ip-1"


class VectorIndex:
    def __init__(self, ids: list[str], vectors: np.ndarray):
        if len(ids) != len(vectors):
            raise ValueError("ids e vetores com tamanhos diferentes")
        self.ids = list(ids)
        self.vectors = np.asarray(vectors, dtype=np.float32)

    def search(self, query: np.ndarray, k: int = 200) -> list[dict]:
        if not self.ids:
            return []
        scores = self.vectors @ np.asarray(query, dtype=np.float32).reshape(-1)
        k = min(k, len(self.ids))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top], kind="stable")]
        return [{"chunk_id": self.ids[i], "similarity": round(float(scores[i]), 6), "method": "vector"}
                for i in top]
