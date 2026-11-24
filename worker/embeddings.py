"""Embeddings de trechos e consultas com o Gemini (M04, parte vetorial).

Origem: R44 (Gemini Embedding, modelo gemini-embedding-001) via R35 (SDK
google-genai). Plano: Scriptorium V2, módulo M04 "Recuperação híbrida".
Documentação conferida em 24/11/2026:
- https://ai.google.dev/api/embeddings
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings
  (até 250 textos e 20.000 tokens por requisição no Vertex)

Privacidade (autorizado pelo responsável do projeto em 24/11/2026): trechos
das fontes selecionadas são enviados ao serviço de embeddings do Google.
- Administrador: Vertex AI no projeto do Scriptorium (mesma identidade do motor).
- Pesquisador convidado: a chave Gemini pessoal dele; nunca o projeto do
  administrador (mesma regra do BYOK em byok.py).
Nada disso grava texto em logs; o manifesto registra modelo, quantidade de
textos e caracteres enviados.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os

import numpy as np

EMBEDDING_MODEL = os.getenv("SCRIPTORIUM_EMBEDDING_MODEL", "gemini-embedding-001")
DIMENSIONS = int(os.getenv("SCRIPTORIUM_EMBEDDING_DIMENSIONS", "768"))
BATCH_SIZE = 50          # bem abaixo do limite de 250 textos por requisição
MAX_TEXT_CHARS = 6000    # trechos têm no máximo 2000; margem para consultas
EMBED_SCHEMA = "scriptorium.embeddings/1"
PROVIDERS = {
    "admin_vertex": "Google Vertex AI (conta de serviço do projeto Scriptorium)",
    "user_gemini": "Google Gemini API (chave pessoal do pesquisador)",
}


def normalize(matrix) -> np.ndarray:
    array = np.asarray(matrix, dtype=np.float32)
    if array.ndim == 1:
        array = array[None, :]
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return array / norms


class GeminiEmbedder:
    def __init__(self, client, provider: str, model: str = EMBEDDING_MODEL, dimensions: int = DIMENSIONS):
        self.client, self.provider = client, provider
        self.model, self.dimensions = model, dimensions
        self.usage = {"requests": 0, "texts": 0, "characters": 0}

    def embed(self, texts: list[str], task_type: str) -> np.ndarray:
        from google.genai import types
        vectors = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = [t[:MAX_TEXT_CHARS] for t in texts[start:start + BATCH_SIZE]]
            response = self.client.models.embed_content(
                model=self.model, contents=batch,
                config=types.EmbedContentConfig(task_type=task_type,
                                                output_dimensionality=self.dimensions))
            vectors += [e.values for e in response.embeddings]
            self.usage["requests"] += 1
            self.usage["texts"] += len(batch)
            self.usage["characters"] += sum(len(t) for t in batch)
        if len(vectors) != len(texts):
            raise RuntimeError("Quantidade de embeddings diferente da de textos")
        return normalize(vectors) if vectors else np.zeros((0, self.dimensions), dtype=np.float32)

    def info(self) -> dict:
        return {"model": self.model, "dimensions": self.dimensions, "provider": self.provider,
                "upstream_id": "R44", "usage": dict(self.usage)}

    def cache_namespace(self) -> str:
        safe = "".join(c if c.isalnum() or c == "-" else "-" for c in self.model.lower())
        return f"emb-{safe}-{self.dimensions}"


def make_embedder(auth_mode: str, agent_env: dict, project: str):
    """Cria o embedder com a MESMA identidade de IA da pesquisa; None se indisponível."""
    try:
        from google import genai
    except ImportError:
        return None
    if auth_mode == "user_gemini":
        key = agent_env.get("GEMINI_API_KEY")
        if not key:
            return None
        client = genai.Client(api_key=key)
    elif auth_mode == "admin_vertex":
        client = genai.Client(enterprise=True, project=project, location="global")
    else:
        return None
    return GeminiEmbedder(client, PROVIDERS[auth_mode])


# ---------------------------------------------------------------- cache
def _chunk_fingerprint(chunks: list[dict]) -> str:
    joined = "\n".join(c["text_sha256"] for c in chunks)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def pack_vectors(chunks: list[dict], vectors: np.ndarray, embedder) -> bytes:
    data = np.asarray(vectors, dtype=np.float16)
    return json.dumps({
        "schema": EMBED_SCHEMA, "model": embedder.model, "dimensions": embedder.dimensions,
        "chunks_fingerprint": _chunk_fingerprint(chunks), "shape": list(data.shape),
        "vectors_b64": base64.b64encode(data.tobytes()).decode("ascii"),
    }).encode("utf-8")


def unpack_vectors(raw: bytes, chunks: list[dict], embedder):
    """Vetores do cache, ou None se não corresponderem exatamente aos trechos."""
    payload = json.loads(raw.decode("utf-8"))
    if (payload.get("schema") != EMBED_SCHEMA or payload.get("model") != embedder.model
            or payload.get("dimensions") != embedder.dimensions
            or payload.get("chunks_fingerprint") != _chunk_fingerprint(chunks)
            or payload.get("shape") != [len(chunks), embedder.dimensions]):
        return None
    data = np.frombuffer(base64.b64decode(payload["vectors_b64"]), dtype=np.float16)
    return normalize(data.reshape(len(chunks), embedder.dimensions))
