"""Manifesto de proveniência de cada execução (M14).

Origem: R01 (código próprio). Plano: Scriptorium V2, módulo M14 "Proveniência e
rastreabilidade de execução". Upstreams registrados no manifesto: R02
(PaperOrchestra) e os listados em docs/upstreams.json.

O manifesto responde "como este manuscrito foi gerado?" sem expor segredos:
- versões: commit do Scriptorium, commit fixado do PaperOrchestra, hash de cada
  módulo do worker e versão do Python;
- pedido: modelos, template, idioma e modo de autenticação (nunca a chave);
- entradas: SHA-256 dos materiais originais, do texto efetivamente entregue aos
  agentes e das fontes da biblioteca (com sinais do document_guard);
- eventos: mudanças de etapa com horário;
- saídas: SHA-256 e tamanho de cada arquivo entregue.

Não promete reprodução bit a bit: modelos de linguagem não são determinísticos.
"""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

SCHEMA = "scriptorium.run_manifest/1"
PAPER_ORCHESTRA_REPOSITORY = "https://github.com/google-research/paper-orchestra"
SOURCE_FIELDS = ("id", "name", "format", "sha256", "status", "extracted_characters",
                 "truncated", "risk_level", "risk_flags", "neutralized_delimiters",
                 "removed_invisible_characters", "removed_control_characters", "guard_version",
                 "note", "parser_version", "chunk_policy", "pages_total", "pages_processed",
                 "ocr_pages_flagged", "warnings", "chunks_total", "chunks_selected", "cache")
# Campos de pedido copiados do registro da pesquisa. Nada de credenciais.
REQUEST_FIELDS = ("template", "language", "plotting", "model", "reflection_model",
                  "neon_review_requested", "ai_auth_mode")
PROVIDERS = {
    "admin_vertex": "Google Vertex AI (conta de serviço do projeto Scriptorium)",
    "user_gemini": "Google Gemini API (chave pessoal do pesquisador)",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def file_fingerprint(path: Path) -> dict:
    return {"sha256": sha256_file(path), "size": path.stat().st_size}


def canonical_hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RunManifest:
    def __init__(self, run_id: str, owner_uid: str, record: Mapping, env: Mapping,
                 code_dir: Path, clock: Callable[[], str] = utc_now):
        self.clock = clock
        request = {key: record.get(key) for key in REQUEST_FIELDS}
        if record.get("plotting"):
            # Mesmo modelo de texto + modelo de imagem fixo no runner.
            request["plotting_model"] = record.get("model")
            request["image_model"] = "gemini-3-pro-image-preview"
        request["provider"] = PROVIDERS.get(record.get("ai_auth_mode") or "admin_vertex", "desconhecido")
        modules = {
            path.name: sha256_file(path)
            for path in sorted(Path(code_dir).glob("*.py"))
        }
        self.data = {
            "schema": SCHEMA,
            "run_id": run_id,
            "owner_uid": owner_uid,
            "title": record.get("title", ""),
            "created_at": record.get("created_at", ""),
            "started_at": clock(),
            "finished_at": "",
            "final_status": "running",
            "request": request,
            "software": {
                "scriptorium_release_sha": env.get("SCRIPTORIUM_RELEASE_SHA") or "não informado",
                "paper_orchestra": {
                    "upstream_id": "R02",
                    "repository": PAPER_ORCHESTRA_REPOSITORY,
                    "commit": env.get("PAPER_ORCHESTRA_COMMIT") or "não informado",
                },
                "python": platform.python_version(),
                "worker_modules_sha256": modules,
                "upstream_registry": "docs/upstreams.json",
            },
            "inputs": {},
            "context": {"strategy": "sem fontes anexadas"},
            "sources": [],
            "events": [],
            "outputs": {},
            "costs": {
                "status": "not_measured",
                "reason": "O motor original não informa tokens nem custo por chamada.",
            },
            # M12: decisões humanas registradas pela API (quem, quando, o quê).
            "approvals": ({"status": "recorded", "events": list(record.get("approvals") or [])}
                          if record.get("approvals") else
                          {"status": "none_recorded",
                           "reason": "Pesquisa iniciada sem o checkpoint de aprovação de fontes."}),
            "mode": record.get("mode") or "generate",
            "limitations": [
                "Modelos de linguagem não são determinísticos: repetir a execução com o mesmo manifesto pode gerar texto diferente.",
                "O manifesto registra o que foi entregue aos agentes, não comprova a validade científica do manuscrito.",
            ],
        }

    # ------------------------------------------------------------ registro
    def event(self, stage: str, **details) -> None:
        safe = {k: v for k, v in details.items() if isinstance(v, (str, int, float, bool)) or v is None}
        self.data["events"].append({"at": self.clock(), "stage": str(stage)[:200], **safe})

    def add_input(self, name: str, path: Path) -> None:
        self.data["inputs"][name] = file_fingerprint(path)

    def add_agent_input(self, name: str, path: Path) -> None:
        """Texto realmente entregue ao motor (original + fontes + preferências)."""
        self.data["inputs"].setdefault("delivered_to_agents", {})[name] = file_fingerprint(path)

    def add_sources(self, manifest: list[dict]) -> None:
        self.data["sources"] = [
            {key: item.get(key) for key in SOURCE_FIELDS if key in item}
            for item in manifest
        ]

    def add_ai_service(self, name: str, info: dict) -> None:
        """Serviços de IA auxiliares (ex.: embeddings), sem texto enviado."""
        self.data.setdefault("ai_services", {})[name] = info

    def set_context(self, strategy: str, coverage: dict | None = None) -> None:
        """Como o contexto das fontes foi montado (V1 corte ou V2 recuperação)."""
        self.data["context"] = {"strategy": strategy, **({"coverage": coverage} if coverage else {})}

    def add_output(self, kind: str, path: Path) -> None:
        self.data["outputs"][kind] = {"file": path.name, **file_fingerprint(path)}

    # -------------------------------------------------------------- fechamento
    def corpus_snapshot(self) -> str:
        originals = {k: v["sha256"] for k, v in self.data["inputs"].items() if "sha256" in v}
        sources = sorted(str(s.get("sha256", "")) for s in self.data["sources"])
        return "sha256:" + canonical_hash({"inputs": originals, "sources": sources})

    def finish(self, status: str, error: str = "") -> dict:
        self.data["final_status"] = status
        self.data["finished_at"] = self.clock()
        if error:
            self.data["error"] = str(error)[:400]
        self.data["corpus_snapshot"] = self.corpus_snapshot()
        body = {k: v for k, v in self.data.items() if k != "content_sha256"}
        self.data["content_sha256"] = canonical_hash(body)
        return self.data

    def write(self, path: Path) -> Path:
        path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
