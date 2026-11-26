"""Servidor MCP do Scriptorium: a IA do pesquisador escreve; o Scriptorium guarda e confere.

Endereço: https://<site>/api/mcp (Streamable HTTP, sem estado, respostas JSON).
Autenticação nesta fase: token pessoal gerado no site (Minha conta), enviado como
"Authorization: Bearer scr_..." ou, para clientes que não aceitam cabeçalho, no
caminho /api/mcp/t/<token>. O token só dá acesso às ferramentas abaixo: ler a
própria biblioteca e escrever no quadro dos próprios projetos. Não roda IA, não
apaga nada e não usa a chave Gemini.

Nenhuma ferramenta chama modelo de linguagem. Os dois trabalhos pesados (ler as
fontes e compilar o PDF) rodam no worker, também sem IA.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Callable, Literal

import anyio
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

import library_search as search
import mcp_flow as flow
import mcp_review as review

try:
    from google.api_core.exceptions import NotFound as _GcsNotFound
except Exception:  # pragma: no cover
    _GcsNotFound = ()

MCP_PATH = "/api/mcp"
MAX_ACTIVE_TOKENS = 5
MAX_PROJECT_SOURCES = 20
MAX_ACTIVE_JOBS = 2
BUSY = ("preparando", "compilando", "refazendo_referencias")
FORMATS = {"pdf", "docx", "txt"}
ID = re.compile(r"[0-9a-f]{32}")
INSTRUCTIONS = (
    "Scriptorium: escrita acadêmica com as fontes do pesquisador, sem API paga. Você (a IA) lê e "
    "escreve; o Scriptorium guarda as fontes, entrega trechos e confere cada entrega. Fluxo: "
    "listar_fontes -> criar_projeto -> proxima_etapa (repetir) -> compilar. Referências com confiança "
    "sugerida ou a_conferir, ou com título, autor ou ano errados, se confirmam ou corrigem com "
    "corrigir_referencia antes de compilar: sem isso o PDF só sai como rascunho. Guarde o identificador de "
    "cabeça que proxima_etapa devolver e use-o em todas as chamadas desta conversa. Quando uma etapa "
    "pedir conversa nova, entregue o PASSE ao pesquisador e pare: a etapa será feita em outra conversa."
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Falha(ToolError):
    """Erro previsto: a mensagem vai inteira para a IA, que pode corrigir e tentar de novo."""


# ====================================================================== dados
class Store:
    """Acesso a Firestore e Cloud Storage, sempre restrito ao dono (uid)."""

    def __init__(self, db, bucket, start_job: Callable[[str, str, str], None],
                 is_allowed: Callable[[dict], bool]):
        self.db, self.bucket, self.start_job, self.is_allowed = db, bucket, start_job, is_allowed
        self._payloads: dict[str, dict] = {}
        self._refs_cache: dict[str, tuple[str, float, list[dict]]] = {}
        self._on_revoke: list[Callable[[str], None]] = []

    # ---------------------------------------------------------------- tokens
    def token_owner(self, token: str) -> dict | None:
        if not flow.looks_like_token(token):
            return None
        snap = self.db.collection("mcp_tokens").document(flow.token_hash(token)).get()
        record = snap.to_dict() if snap.exists else None
        if not record or record.get("revoked"):
            return None
        identity = {"uid": record["owner_uid"], "email": record.get("email", ""),
                    "email_verified": True}
        if not self.is_allowed(identity):
            return None
        return identity

    def create_token(self, uid: str, email: str, label: str) -> dict:
        active = [d.to_dict() for d in self.db.collection("mcp_tokens").where("owner_uid", "==", uid).stream()]
        if sum(1 for t in active if not t.get("revoked")) >= MAX_ACTIVE_TOKENS:
            raise ValueError(f"Limite de {MAX_ACTIVE_TOKENS} tokens ativos. Revogue um antes de criar outro.")
        token, digest = flow.new_token()
        record = {"id": digest[:16], "hash": digest, "owner_uid": uid, "email": email,
                  "label": (label or "Minha IA").strip()[:60], "created_at": now(), "revoked": False}
        self.db.collection("mcp_tokens").document(digest).set(record)
        return {**self.public_token(record), "token": token}

    @staticmethod
    def public_token(record: dict) -> dict:
        return {k: record.get(k) for k in ("id", "label", "created_at", "revoked", "revoked_at")}

    def list_tokens(self, uid: str) -> list[dict]:
        docs = [d.to_dict() for d in self.db.collection("mcp_tokens").where("owner_uid", "==", uid).stream()]
        return sorted((self.public_token(d) for d in docs), key=lambda d: d.get("created_at") or "", reverse=True)

    def revoke_token(self, uid: str, token_id: str) -> bool:
        for snap in self.db.collection("mcp_tokens").where("owner_uid", "==", uid).stream():
            record = snap.to_dict()
            if record.get("id") == token_id and not record.get("revoked"):
                digest = record["hash"]
                self.db.collection("mcp_tokens").document(digest).update(
                    {"revoked": True, "revoked_at": now()})
                for cb in self._on_revoke:
                    cb(digest)
                return True
        return False

    # ------------------------------------------------------------- biblioteca
    def library(self, uid: str) -> list[dict]:
        docs = self.db.collection("library_items").where("owner_uid", "==", uid).limit(500).stream()
        items = [d.to_dict() for d in docs]
        return [{"id": i["id"], "nome": i.get("name", ""), "formato": i.get("format", ""),
                 "doi": (i.get("origin") or {}).get("doi", "")}
                for i in items if i.get("status") == "active" and i.get("format") in FORMATS]

    def _source(self, uid: str, item_id: str) -> dict:
        if not ID.fullmatch(item_id or ""):
            raise Falha(f"Identificador de fonte inválido: {item_id}")
        snap = self.db.collection("library_items").document(item_id).get()
        record = snap.to_dict() if snap.exists else None
        if not record or record.get("owner_uid") != uid or record.get("status") != "active":
            raise Falha(f"Fonte {item_id} não encontrada na sua biblioteca.")
        if record.get("format") not in FORMATS:
            raise Falha(f"A fonte {record.get('name')} não é PDF, DOCX ou TXT.")
        if not str(record.get("object_path", "")).startswith(f"library/{uid}/{item_id}/"):
            raise Falha("Caminho da fonte inválido.")
        return {k: record.get(k) for k in ("id", "name", "format", "sha256", "size", "object_path", "origin")}

    # --------------------------------------------------------------- projetos
    def _active_jobs(self, uid: str) -> int:
        docs = self.db.collection("mcp_projects").where("owner_uid", "==", uid).stream()
        return sum(1 for d in docs if d.to_dict().get("status") in BUSY)

    def _launch(self, uid: str, pid: str, mode: str, sources: list[dict], title: str) -> str:
        job_id = uuid.uuid4().hex
        self.db.collection("research_jobs").document(job_id).create({
            "id": job_id, "owner_uid": uid, "title": title[:120], "status": "queued",
            "stage": "Na fila", "mode": mode, "mcp_project_id": pid, "sources": sources,
            "created_at": now(), "finished_at": "", "files": [], "error": ""})
        try:
            self.start_job(job_id, uid, mode)
        except Exception:
            self.db.collection("research_jobs").document(job_id).update(
                {"status": "failed", "error": "Falha ao iniciar", "finished_at": now()})
            raise Falha("Não foi possível iniciar o trabalho no servidor. Tente de novo em instantes.") from None
        return job_id

    def create_project(self, uid: str, title: str, question: str, ids: list[str], language: str,
                       template: str, tipo: str = "artigo") -> dict:
        ids = list(dict.fromkeys(ids or []))
        if not 3 <= len((title or "").strip()) <= 120:
            raise Falha("O título deve ter de 3 a 120 caracteres.")
        if not 20 <= len((question or "").strip()) <= 4000:
            raise Falha("Descreva a pergunta ou objetivo do texto em 20 a 4000 caracteres.")
        if not 1 <= len(ids) <= MAX_PROJECT_SOURCES:
            raise Falha(f"Escolha de 1 a {MAX_PROJECT_SOURCES} fontes (use listar_fontes).")
        if template not in flow.TEMPLATES or language not in ("pt-BR", "en") or tipo not in flow.MODES:
            raise Falha("Modelo, idioma ou tipo inválido.")
        if self._active_jobs(uid) >= MAX_ACTIVE_JOBS:
            raise Falha("Já há trabalhos em andamento no servidor. Aguarde terminarem.")
        sources = [self._source(uid, i) for i in ids]
        pid = uuid.uuid4().hex
        record = {"id": pid, "owner_uid": uid, "title": title.strip(), "question": question.strip(),
                  "language": language, "template": template, "tipo": tipo, "sources": sources,
                  "status": "preparando", "flow_version": flow.FLOW_VERSION, "stages": {}, "heads": {},
                  "created_at": now(), "updated_at": now(), "files": []}
        self.db.collection("mcp_projects").document(pid).create(record)
        job = self._launch(uid, pid, "mcp_prepare", sources, f"Preparo MCP: {title}")
        self.db.collection("mcp_projects").document(pid).update({"prepare_job": job})
        return record

    def project(self, uid: str, pid: str) -> dict:
        if not ID.fullmatch(pid or ""):
            raise Falha("Projeto não encontrado.")
        snap = self.db.collection("mcp_projects").document(pid).get()
        record = snap.to_dict() if snap.exists else None
        if not record or record.get("owner_uid") != uid:
            raise Falha("Projeto não encontrado.")
        return self._reconcile(record)

    def _reconcile(self, record: dict) -> dict:
        """Trabalho do worker que morreu sem atualizar o projeto não fica preso."""
        job_key = {"preparando": "prepare_job", "compilando": "compile_job",
                   "refazendo_referencias": "refs_job"}.get(record.get("status"))
        if not job_key or not record.get(job_key):
            return record
        snap = self.db.collection("research_jobs").document(record[job_key]).get()
        job = snap.to_dict() if snap.exists else {}
        if job.get("status") == "failed":
            status = {"prepare_job": "falhou_preparo", "compile_job": "pronto"}.get(
                job_key, record.get("status_antes") or "pronto")
            fields = {"status": status, "error": job.get("error", "Falha no servidor"), "updated_at": now()}
            self.db.collection("mcp_projects").document(record["id"]).update(fields)
            return {**record, **fields}
        return record

    def projects(self, uid: str, limit: int = 50) -> list[dict]:
        query = self.db.collection("mcp_projects").where("owner_uid", "==", uid)
        if hasattr(query, "limit"):
            query = query.limit(limit)
        docs = [d.to_dict() for d in query.stream()]
        return sorted(docs, key=lambda d: d.get("created_at", ""), reverse=True)

    def update_project(self, pid: str, **fields) -> None:
        self._refs_cache.pop(pid, None)
        self.db.collection("mcp_projects").document(pid).update({**fields, "updated_at": now()})

    # ------------------------------------------------------ link de orientação
    def create_advisor_share(self, uid: str, pid: str, days: int = 14, note: str = "") -> dict:
        """Onda 3: cria link temporário e revogável somente leitura para o(a) orientador(a)."""
        project = self.project(uid, pid)
        days = max(1, min(30, int(days or 14)))
        self.revoke_advisor_share(uid, pid)
        token = "adv_" + secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        record = {
            "id": digest[:16], "hash": digest, "owner_uid": uid, "project_id": project["id"],
            "created_at": now(), "expires_at": expires, "revoked": False,
            "note": str(note or "").strip()[:600],
        }
        self.db.collection("advisor_shares").document(digest).set(record)
        self.update_project(project["id"], advisor_share_id=digest[:16], advisor_share_expires=expires)
        return {"id": digest[:16], "token": token, "expires_at": expires}

    def revoke_advisor_share(self, uid: str, pid: str) -> bool:
        """Revoga imediatamente qualquer link de orientação ativo deste projeto."""
        project = self.project(uid, pid)
        revoked_any = False
        try:
            col = self.db.collection("advisor_shares")
            for snap in col.where("owner_uid", "==", uid).stream():
                rec = snap.to_dict() or {}
                if rec.get("project_id") == project["id"] and not rec.get("revoked"):
                    col.document(rec["hash"]).update({"revoked": True, "revoked_at": now()})
                    revoked_any = True
        except Exception:
            pass
        if project.get("advisor_share_id"):
            self.update_project(project["id"], advisor_share_id="", advisor_share_expires="")
        return revoked_any

    def read_advisor_share(self, token: str) -> dict | None:
        """Lê um link de orientação válido (sem expor e-mail, UID, biblioteca ou tokens)."""
        if not re.fullmatch(r"adv_[A-Za-z0-9_-]{40,60}", token or ""):
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        snap = self.db.collection("advisor_shares").document(digest).get()
        share = snap.to_dict() if snap.exists else None
        if not share or share.get("revoked"):
            return None
        if str(share.get("expires_at") or "") < now():
            return None
        try:
            project = self.project(share["owner_uid"], share["project_id"])
        except Falha:
            return None
        refs = self.references(project)
        return {"share": share, "project": project, "refs": refs}

    @staticmethod
    def prefix(project: dict) -> str:
        return f"mcp/{project['owner_uid']}/{project['id']}"

    def _json(self, path: str, default=None):
        blob = self.bucket.blob(path)
        try:
            raw = blob.download_as_bytes()
        except (_GcsNotFound, KeyError, FileNotFoundError):
            return default
        try:
            return json.loads(raw)
        except ValueError:
            return default

    def ready(self, project: dict) -> None:
        status = project.get("status")
        if status == "preparando":
            raise Falha("O Scriptorium ainda está lendo as fontes do projeto (alguns minutos). "
                        "Tente de novo daqui a pouco com estado_do_projeto.")
        if status == "falhou_preparo":
            raise Falha("A leitura das fontes falhou: " + str(project.get("error", "")) +
                        ". Crie o projeto de novo ou troque as fontes.")
        if status == "refazendo_referencias":
            raise Falha("O Scriptorium está refazendo as referências do projeto (um ou dois minutos). "
                        "Tente de novo daqui a pouco com estado_do_projeto.")

    def references(self, project: dict) -> list[dict]:
        pid = project.get("id") or ""
        stamp = str(project.get("updated_at") or "")
        cached = self._refs_cache.get(pid)
        if cached and cached[0] == stamp and time.monotonic() - cached[1] < 60:
            return json.loads(json.dumps(cached[2]))
        data = self._json(self.prefix(project) + "/references.json", []) or []
        if pid and stamp and data:
            if len(self._refs_cache) > 128:
                self._refs_cache.clear()
            self._refs_cache[pid] = (stamp, time.monotonic(), json.loads(json.dumps(data)))
        return data

    def manifest(self, project: dict) -> list[dict]:
        return self._json(self.prefix(project) + "/sources.json", []) or []

    def payload(self, project: dict, entry: dict) -> dict:
        path = entry.get("derived") or ""
        if not path.startswith(f"library/{project['owner_uid']}/derived/"):
            return {}
        if path not in self._payloads:
            if len(self._payloads) > 64:
                self._payloads.clear()
            self._payloads[path] = self._json(path, {}) or {}
        return self._payloads[path]

    def chunks_for_key(self, project: dict) -> Callable[[str], list[dict]]:
        by_key = {e.get("key"): e for e in self.manifest(project)}

        def get(key: str) -> list[dict]:
            entry = by_key.get(key)
            return (self.payload(project, entry).get("chunks") or []) if entry else []
        return get

    def search(self, project: dict, query: str, limit: int, zone: str = "") -> dict:
        try:
            fts = search.fts_query(query)
        except ValueError as exc:
            raise Falha(str(exc)) from None
        manifest = [e for e in self.manifest(project) if e.get("derived")]
        sig = hashlib.sha256(("mcp-" + search.INDEX_VERSION + "\n" + "\n".join(
            sorted(f"{e['id']}:{e['derived']}" for e in manifest))).encode()).hexdigest()
        prefix = self.prefix(project)
        index_blob, meta_blob = self.bucket.blob(prefix + "/index.sqlite"), prefix + "/index.json"
        key_of = {e["id"]: e.get("key") for e in manifest}
        with tempfile.TemporaryDirectory(prefix="mcpidx_") as tmp:
            path = os.path.join(tmp, "index.sqlite")
            meta = self._json(meta_blob, {}) or {}
            if meta.get("signature") == sig and index_blob.exists():
                index_blob.download_to_filename(path)
            else:
                docs = [({"id": e["id"], "name": e.get("name", "")}, self.payload(project, e)) for e in manifest]
                count = search.build_index(path, docs)
                index_blob.upload_from_filename(path, content_type="application/vnd.sqlite3")
                self.bucket.blob(meta_blob).upload_from_string(
                    json.dumps({"signature": sig, "chunks": count}), content_type="application/json")
            rows = search.search_index(path, fts, limit * 4 if zone else limit)
        if zone:
            rows = [r for r in rows if review.zone_of(r["heading"]) == zone][:limit]
        return {"resultados": [{"chave": key_of.get(r["item_id"]), "fonte": r["name"], "chunk_id": r["chunk_id"],
                                "paginas": r["pages"], "secao": r["heading"], "zona": review.zone_of(r["heading"]),
                                "trecho": r["snippet"]} for r in rows],
                "dica": "Use ler_trecho com o chunk_id para ler o texto inteiro antes de citar."}

    def read_chunk(self, project: dict, chunk_id: str, neighbors: int) -> dict:
        for entry in self.manifest(project):
            chunks = self.payload(project, entry).get("chunks") or []
            for n, chunk in enumerate(chunks):
                if chunk.get("chunk_id") == chunk_id:
                    window = chunks[max(0, n - neighbors): n + neighbors + 1]
                    pages = chunk.get("pages")
                    return {"chave": entry.get("key"), "fonte": entry.get("name"), "chunk_id": chunk_id,
                            "paginas": f"{pages[0]}-{pages[1]}" if pages else "",
                            "secao": " > ".join(chunk.get("heading_path") or []),
                            "zona": review.zone_of(" > ".join(chunk.get("heading_path") or [])),
                            "texto": chunk.get("text", ""),
                            "vizinhos": [{"chunk_id": c.get("chunk_id"), "texto": c.get("text", "")}
                                         for c in window if c is not chunk]}
        raise Falha("Trecho não encontrado nas fontes deste projeto. Use buscar_trechos.")

    def card(self, project: dict, key: str) -> dict:
        entry = next((e for e in self.manifest(project) if e.get("key") == key), None)
        if not entry:
            raise Falha(f"Chave '{key}' não está neste projeto. Veja referencias_do_projeto.")
        item = {"id": entry["id"], "name": entry.get("name"), "format": entry.get("format"),
                "sha256": entry.get("sha256")}
        card = search.reading_card(item, self.payload(project, entry))
        card["chave"] = key
        ref = next((r for r in self.references(project) if r.get("key") == key), None)
        if ref:
            fields = ref.get("fields") or {}
            card["referencia_atual"] = {
                "tipo": ref.get("type"), "titulo": fields.get("title", ""),
                "autores": fields.get("author", ""), "ano": fields.get("year", ""),
                "confianca": flow.ref_level(ref), "origem": ref.get("how", ""),
            }
        return card

    def _save_library_bib(self, uid: str, source_id: str, entry: dict) -> None:
        """Item 6: salva ficha confirmada na biblioteca para herança em projetos futuros."""
        if not source_id:
            return
        try:
            doc_ref = self.db.collection("library_items").document(source_id)
            snap = doc_ref.get()
            rec = snap.to_dict() if snap.exists else None
            if not rec or rec.get("owner_uid") != uid:
                return
            fields = dict(entry.get("fields") or {})
            existing_key = ((rec.get("bib_entry") or {}).get("key") or "").strip()
            stable_key = (existing_key if existing_key and not existing_key.startswith("fonte_")
                          else flow.stable_bib_key(fields))
            doc_ref.update({"bib_entry": {
                "type": entry.get("type") or "misc",
                "key": stable_key,
                "fields": fields,
                "how": entry.get("how") or "confirmada_pelo_pesquisador",
                "updated_at": now(),
            }})
        except Exception:
            pass

    def confirm_reference_human(self, uid: str, pid: str, key: str, payload: dict) -> dict:
        """Itens 6 e 7: pesquisador confirma em 1 clique no site (aceita proposta da IA ou edita)."""
        project = self.project(uid, pid)
        if project.get("status") in BUSY:
            raise Falha("Aguarde o trabalho em andamento terminar para confirmar referências.")
        refs = self.references(project)
        entry = next((r for r in refs if r.get("key") == key), None)
        if not entry:
            raise Falha(f"Chave '{key}' não está neste projeto.")
        if payload.get("aceitar_proposta"):
            prop = entry.get("proposta_pendente")
            if not isinstance(prop, dict) or not prop.get("fields"):
                raise Falha("Não há proposta pendente para esta referência.")
            kind = prop.get("type") or "misc"
            fields = dict(prop["fields"])
        else:
            fields, errors = flow.check_reference_proposal(payload)
            if errors:
                raise Falha(" ".join(errors))
            kind = payload.get("tipo") or "misc"
        before = dict(entry.get("fields") or {})
        entry.update(type=kind, fields=fields, how="confirmada_pelo_pesquisador")
        entry.pop("proposta_pendente", None)
        prefix = self.prefix(project)
        self.bucket.blob(prefix + "/references.json").upload_from_string(
            json.dumps(refs, ensure_ascii=False), content_type="application/json")
        self.bucket.blob(prefix + "/references.bib").upload_from_string(
            "".join(flow.render_reference(r) for r in refs), content_type="text/plain; charset=utf-8")
        self._save_library_bib(uid, entry.get("source_id") or "", entry)
        history = list(project.get("reference_fixes") or [])[-80:]
        history.append({"chave": key, "em": now(), "cabeca": "pesquisador", "ia": "confirmacao_humana",
                        "antes": {k: before.get(k, "") for k in ("author", "title", "year")}})
        fields_update = {"reference_fixes": history}
        if project.get("status") in ("concluido", "rascunho"):
            fields_update.update(status="pronto", error="Referências confirmadas depois do PDF: compile de novo.")
        self.update_project(project["id"], **fields_update)
        return {"chave": key, "confirmada": True, "tipo": entry["type"], **fields, "confianca": "confirmada"}

    def correct_reference(self, project: dict, key: str, head_id: str, fix: dict) -> dict:
        if project.get("status") in BUSY:
            raise Falha("Aguarde o trabalho em andamento terminar para corrigir referências.")
        head = (project.get("heads") or {}).get(head_id or "")
        if not head:
            raise Falha("Cabeça desconhecida. Use o identificador recebido em proxima_etapa ou abrir_passe.")
        refs = self.references(project)
        entry = next((r for r in refs if r.get("key") == key), None)
        source = next((m for m in self.manifest(project) if m.get("key") == key), None)
        if not entry or not source:
            raise Falha(f"Chave '{key}' não está neste projeto. Veja referencias_do_projeto.")
        chunks = self.payload(project, source).get("chunks") or []
        early = [c for c in chunks if (c.get("pages") or [1])[0] <= 4] or chunks[:15]
        # O título da capa costuma virar título de seção no parser: entra junto do texto.
        first = "\n".join("\n".join(list(c.get("heading_path") or []) + [c.get("text", "")]) for c in early)
        full = "\n".join(c.get("text", "") for c in chunks)
        fields, errors = flow.check_reference_fix(fix, first, full)
        if errors:
            # Item 7: se a capa não tiver texto extraível, guarda proposta válida para confirmação em 1 clique.
            prop_fields, prop_errors = flow.check_reference_proposal(fix)
            if not prop_errors:
                entry["proposta_pendente"] = {
                    "type": fix.get("tipo") or "misc", "fields": prop_fields,
                    "motivo": errors[:3], "ia": head.get("model") or head.get("client", ""), "em": now(),
                }
                self.bucket.blob(self.prefix(project) + "/references.json").upload_from_string(
                    json.dumps(refs, ensure_ascii=False), content_type="application/json")
                raise Falha("Correção automática recusada: " + " ".join(errors) +
                            " A proposta ficou salva no site para o pesquisador confirmar em 1 clique ao lado da capa do PDF.")
            raise Falha("Correção recusada: " + " ".join(errors))
        before = dict(entry.get("fields") or {})
        entry.update(type=fix.get("tipo") or "misc", fields=fields, how="corrigida_pelo_texto")
        entry.pop("proposta_pendente", None)
        prefix = self.prefix(project)
        self.bucket.blob(prefix + "/references.json").upload_from_string(
            json.dumps(refs, ensure_ascii=False), content_type="application/json")
        self.bucket.blob(prefix + "/references.bib").upload_from_string(
            "".join(flow.render_reference(r) for r in refs), content_type="text/plain; charset=utf-8")
        self._save_library_bib(project["owner_uid"], entry.get("source_id") or source.get("id") or "", entry)
        history = list(project.get("reference_fixes") or [])[-80:]
        history.append({"chave": key, "em": now(), "cabeca": head.get("id"),
                        "ia": head.get("model") or head.get("client", ""),
                        "antes": {k: before.get(k, "") for k in ("author", "title", "year")}})
        fields_update = {"reference_fixes": history}
        if project.get("status") in ("concluido", "rascunho"):
            # O PDF já gerado não tem a correção: volta a "pronto" (os arquivos continuam lá).
            fields_update.update(status="pronto", error="Referências corrigidas depois do PDF: chame compilar de novo.")
        self.update_project(project["id"], **fields_update)
        return {"chave": key, "corrigida": True, "tipo": entry["type"], **fields, "confianca": "confirmada",
                "aviso": "Chave mantida e ficha salva na biblioteca: vale para os próximos projetos."}

    def rebuild_references(self, uid: str, pid: str) -> dict:
        """Refaz só a bibliografia (worker, sem IA), mantendo as chaves já citadas no texto."""
        project = self.project(uid, pid)
        if project.get("status") in BUSY or project.get("status") == "falhou_preparo":
            raise Falha("Este projeto não está pronto para refazer as referências agora.")
        if self._active_jobs(uid) >= MAX_ACTIVE_JOBS:
            raise Falha("Já há trabalhos em andamento no servidor. Aguarde terminarem.")
        job = self._launch(uid, pid, "mcp_refs", [], f"Referências MCP: {project.get('title', '')}")
        self.update_project(pid, status="refazendo_referencias", status_antes=project.get("status"),
                            refs_job=job, error="")
        return {"status": "refazendo_referencias",
                "instrucao": "Consulte estado_do_projeto em um ou dois minutos. As chaves já usadas no texto "
                             "continuam as mesmas, e as correções feitas com corrigir_referencia são mantidas."}

    # ------------------------------------------------------------------ quadro
    def stage_content(self, project: dict, key: str, version: int) -> tuple[str, dict]:
        base = f"{self.prefix(project)}/etapas/{key}-v{version}"
        blob = self.bucket.blob(base + ".txt")
        content = blob.download_as_bytes().decode("utf-8") if blob.exists() else ""
        return content, self._json(base + ".json", {}) or {}

    def board(self, project: dict) -> dict:
        out = {}
        for key, state in (project.get("stages") or {}).items():
            if state.get("status") == "aceita":
                content, validation = self.stage_content(project, key, state["version"])
                out[key] = {"content": content, "validation": validation}
        return out

    def save_stage(self, project: dict, key: str, version: int, content: str, validation: dict) -> None:
        base = f"{self.prefix(project)}/etapas/{key}-v{version}"
        self.bucket.blob(base + ".txt").upload_from_string(content, content_type="text/plain; charset=utf-8")
        self.bucket.blob(base + ".json").upload_from_string(
            json.dumps(validation, ensure_ascii=False), content_type="application/json")

    # ------------------------------------------------------------------ passes
    def pass_for(self, project: dict, stage_def: dict) -> str:
        state = (project.get("stages") or {}).get(stage_def["key"]) or {}
        if state.get("passe"):
            return state["passe"]
        code = flow.new_pass_code()
        self.db.collection("mcp_passes").document(code).set(
            {"code": code, "owner_uid": project["owner_uid"], "project": project["id"],
             "stage": stage_def["key"], "created_at": now()})
        stages = dict(project.get("stages") or {})
        stages[stage_def["key"]] = {**state, "status": state.get("status", "pendente"), "passe": code}
        self.update_project(project["id"], stages=stages)
        project["stages"] = stages
        return code

    def open_pass(self, uid: str, code: str) -> tuple[dict, dict]:
        code = (code or "").strip().upper()
        if not re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", code):
            raise Falha("Passe inválido. Ele tem o formato XXXX-XXXX-XXXX.")
        snap = self.db.collection("mcp_passes").document(code).get()
        record = snap.to_dict() if snap.exists else None
        if not record or record.get("owner_uid") != uid:
            raise Falha("Passe não encontrado nesta conta.")
        project = self.project(uid, record["project"])
        return project, flow.stage(record["stage"])

    def new_head(self, project: dict, kind: str, stage_key: str | None, client: str, model: str) -> dict:
        head = {"id": flow.new_head_id(), "kind": kind, "stage": stage_key, "client": client[:80],
                "model": (model or "").strip()[:80], "created_at": now()}
        heads = dict(project.get("heads") or {})
        if len(heads) >= 60:
            raise Falha("Limite de cabeças deste projeto atingido.")
        heads[head["id"]] = head
        self.update_project(project["id"], heads=heads)
        project["heads"] = heads
        return head


# ================================================================== lógica
def mode(project: dict) -> str:
    return project.get("tipo") or "artigo"


def review_context(store: Store, project: dict, board: dict | None = None) -> dict:
    if mode(project) != review.MODE:
        return {}
    board = store.board(project) if board is None else board
    keys = [m.get("key") for m in store.manifest(project) if m.get("key")]
    return review.context(project, board, keys)


def stage_material(store: Store, project: dict, stage_key: str) -> dict:
    board = store.board(project)
    refs = store.references(project)
    if mode(project) == review.MODE:
        out = review.material(stage_key, project, board, refs, review_context(store, project, board))
    else:
        out = flow.material(stage_key, project, board, refs)
    state = (project.get("stages") or {}).get(stage_key) or {}
    if stage_key == "reescrita" and state.get("versao_anterior"):
        # Reescrita reaberta: a IA parte do texto que já tinha sido aceito.
        previous, _ = store.stage_content(project, "reescrita", state["versao_anterior"])
        report = project.get("compile_report") or {}
        out = {**out, "texto_anterior": flow._clip(previous, 70_000),
               "problemas_da_compilacao": {"motivos": report.get("motivos", []),
                                           "erros_latex": report.get("erros_detalhe", [])},
               "dica": "Corrija só o necessário no texto_anterior; a verificação será refeita."}
    return out


def _state_summary(project: dict) -> list[dict]:
    stages = project.get("stages") or {}
    out = []
    for s in flow.stages_for(mode(project)):
        st = stages.get(s["key"]) or {}
        head = st.get("head") or {}
        out.append({"etapa": s["key"], "titulo": s["titulo"], "status": st.get("status", "pendente"),
                    "tentativas": st.get("attempts", 0), "nova_conversa": s["nova_conversa"],
                    "ia": head.get("model") or head.get("client") or "",
                    "independencia": (st.get("independencia") or {}).get("nivel")})
    return out


def project_state(store: Store, project: dict) -> dict:
    nxt = flow.next_stage(project.get("stages") or {}, mode(project))
    status = project.get("status")
    if status == "preparando":
        action = "Aguarde: o Scriptorium está lendo as fontes."
    elif status == "falhou_preparo":
        action = "A leitura das fontes falhou: " + str(project.get("error", ""))
    elif status == "compilando":
        action = "Compilando o PDF. Consulte de novo em um ou dois minutos."
    elif status == "refazendo_referencias":
        action = "Refazendo as referências. Consulte de novo em um ou dois minutos."
    elif status == "concluido" and (project.get("compile_report") or {}).get("versao") != "final":
        action = ("PDF compilado antes das travas da versão final: as referências podem estar erradas. Chame "
                  "refazer_referencias, confirme as pendentes com corrigir_referencia e chame compilar de novo.")
    elif status == "concluido":
        action = "PDF final pronto: baixe no site, na etapa Seus artigos."
    elif status == "rascunho" and not nxt:
        action = ("Saiu só um RASCUNHO: " + str(project.get("error", "")) + " Corrija as referências com "
                  "corrigir_referencia (ou reabra a reescrita com reabrir_reescrita) e chame compilar de novo.")
    elif nxt:
        action = f"Próxima etapa: {nxt['titulo']} (chame proxima_etapa)."
    else:
        action = "Todas as etapas aceitas: chame compilar."
    return {"projeto": project["id"], "titulo": project.get("title"), "status": status,
            "tipo": mode(project), "etapas": _state_summary(project), "proxima_acao": action,
            "arquivos": project.get("files", []), "erro": project.get("error", "")}


def next_step(store: Store, uid: str, pid: str, head_id: str | None, model: str, client: str) -> dict:
    project = store.project(uid, pid)
    store.ready(project)
    if project.get("status") in ("compilando", "concluido"):
        return project_state(store, project)
    stage_def = flow.next_stage(project.get("stages") or {}, mode(project))
    if stage_def is None:
        return {**project_state(store, project), "instrucao": "Todas as etapas foram aceitas. Chame compilar."}
    if stage_def["nova_conversa"]:
        code = store.pass_for(project, stage_def)
        writer_head = next((((project.get("stages") or {}).get(k) or {}).get("head")
                            for k in ("reescrita", "redacao", "triagem")
                            if ((project.get("stages") or {}).get(k) or {}).get("head")), None)
        suggested_ai = flow.recommend_other_family((writer_head or {}).get("model", ""))
        return {
            "etapa": stage_def["key"], "titulo": stage_def["titulo"], "precisa_de_conversa_nova": True,
            "passe": code, "ia_recomendada": suggested_ai,
            "instrucao": (
                "PARE AQUI nesta conversa. Mostre ao pesquisador o passe abaixo e explique: abra uma "
                f"conversa NOVA — de preferência em outra família de IA ({suggested_ai}) conectada ao "
                "Scriptorium, para evitar autoverificação — e peça: "
                f"\"Use o Scriptorium: abrir_passe com o código {code}\". Depois que essa etapa for "
                "aceita, volte a esta conversa e chame proxima_etapa."),
        }
    head = (project.get("heads") or {}).get(head_id or "")
    issued = None
    if head is None or head.get("kind") != "redatora":
        head = issued = store.new_head(project, "redatora", None, client, model)
    state = (project.get("stages") or {}).get(stage_def["key"]) or {}
    out = {"etapa": stage_def["key"], "titulo": stage_def["titulo"], "cabeca": head["id"],
           "instrucoes": flow.brief(stage_def, project.get("language", "pt-BR")),
           "material": stage_material(store, project, stage_def["key"])}
    if issued:
        out["aviso"] = (f"Esta conversa é a cabeça {head['id']}. Use cabeca=\"{head['id']}\" em todas as "
                        "chamadas seguintes desta conversa.")
    if state.get("status") == "recusada":
        out["ultima_recusa"] = state.get("errors", [])
    return out


def open_pass(store: Store, uid: str, code: str, model: str, client: str) -> dict:
    project, stage_def = store.open_pass(uid, code)
    store.ready(project)
    state = (project.get("stages") or {}).get(stage_def["key"]) or {}
    if state.get("status") == "aceita":
        raise Falha("Esta etapa já foi aceita; o passe não vale mais.")
    current = flow.next_stage(project.get("stages") or {}, mode(project))
    if not current or current["key"] != stage_def["key"]:
        raise Falha("Este passe ainda não está liberado: a etapa anterior não terminou.")
    head = store.new_head(project, stage_def["cabeca"], stage_def["key"], client, model)
    return {"projeto": project["id"], "etapa": stage_def["key"], "titulo": stage_def["titulo"],
            "cabeca": head["id"],
            "aviso": (f"Esta conversa é a cabeça {head['id']} ({stage_def['cabeca']}). Use "
                      f"cabeca=\"{head['id']}\" e projeto=\"{project['id']}\" nas chamadas seguintes."),
            "instrucoes": flow.brief(stage_def, project.get("language", "pt-BR")),
            "material": stage_material(store, project, stage_def["key"])}


def deliver(store: Store, uid: str, pid: str, stage_key: str, content: str, head_id: str, model: str,
            client: str, respostas_revisao: str = "") -> dict:
    project = store.project(uid, pid)
    store.ready(project)
    if project.get("status") in ("compilando", "concluido"):
        raise Falha("O projeto já está em compilação ou concluído.")
    keys = [s["key"] for s in flow.stages_for(mode(project))]
    if stage_key not in keys:
        raise Falha("Etapa desconhecida. Etapas: " + ", ".join(keys))
    stage_def = flow.stage(stage_key)
    current = flow.next_stage(project.get("stages") or {}, mode(project))
    if not current or current["key"] != stage_key:
        raise Falha(f"A etapa atual é {current['titulo'] if current else 'nenhuma (tudo aceito)'}; "
                    f"não é possível entregar {stage_def['titulo']} agora.")
    stages = dict(project.get("stages") or {})
    head = dict((project.get("heads") or {}).get(head_id or "") or {})
    problem = flow.check_head(stage_def, head, stages)
    if problem:
        raise Falha(problem)
    if model and not head.get("model"):
        head["model"] = model.strip()[:80]
    if client and not head.get("client"):
        head["client"] = client[:80]
    refs = store.references(project)
    bib_keys = {r["key"] for r in refs}
    if stage_key in review.BY_KEY:
        ctx = review_context(store, project)
        report = review.validate(stage_key, content or "", ctx, store.chunks_for_key(project))
    else:
        review_problems, assigned_claims = None, None
        if stage_key == "reescrita":
            rev_state = stages.get("revisao") or {}
            if rev_state.get("status") == "aceita":
                rev_text, _ = store.stage_content(project, "revisao", rev_state["version"])
                review_problems = flow.numbered_review_problems(rev_text)
        elif stage_key == "verificacao":
            final_key = "reescrita" if (stages.get("reescrita") or {}).get("status") == "aceita" else "redacao"
            final_state = stages.get(final_key) or {}
            if final_state.get("status") == "aceita":
                final_text, _ = store.stage_content(project, final_key, final_state["version"])
                assigned_claims = flow.extract_claims_to_verify(final_text, bib_keys)
        report = flow.validate(stage_key, content or "", bib_keys=bib_keys,
                               chunks_for_key=store.chunks_for_key(project), template=project.get("template"),
                               review_problems=review_problems, review_responses=respostas_revisao or None,
                               assigned_claims=assigned_claims)
    state = dict(stages.get(stage_key) or {})
    version = int(state.get("attempts", 0)) + 1
    store.save_stage(project, stage_key, version, content or "", report)
    summary = {k: v for k, v in report.items() if k not in ("itens", "erros")}
    state.update(attempts=version, last_delivery=now())
    if not report["ok"]:
        state.update(status="recusada", errors=report["erros"])
        stages[stage_key] = state
        store.update_project(pid, stages=stages)
        return {"aceita": False, "etapa": stage_key, "erros": report["erros"], "resumo": summary,
                "instrucao": "Corrija os pontos acima e chame entregar_etapa de novo."}
    state.update(status="aceita", version=version, head=head, summary=summary, accepted_at=now(),
                 errors=[])
    if stage_def["cabeca"] != "redatora":
        compare = stage_def.get("compara_com") or ("reescrita", "redacao")
        writer = next(((stages.get(k) or {}).get("head") for k in compare if (stages.get(k) or {}).get("head")), None)
        state["independencia"] = flow.independence(writer, head)
    stages[stage_key] = state
    extra = {}
    if stage_key == "triagem_independente":
        # Concordância entre as duas triagens; sem divergências, o consenso não é preciso.
        project["stages"] = stages
        kappa = review_context(store, project).get("kappa") or {}
        state["concordancia"] = kappa
        extra["concordancia"] = kappa
        if not kappa.get("divergencias"):
            store.save_stage(project, "consenso", 1, "[]", {"ok": True, "erros": [], "resolvidas": 0})
            stages["consenso"] = {"status": "aceita", "version": 1, "attempts": 1, "head": head,
                                  "summary": {"ok": True, "resolvidas": 0, "automatico": "sem divergências"},
                                  "accepted_at": now()}
    store.update_project(pid, stages=stages, **({"concordancia": extra["concordancia"]} if extra else {}))
    project["stages"] = stages
    nxt = flow.next_stage(stages, mode(project))
    if stage_def["nova_conversa"]:
        after = "Etapa aceita. Avise o pesquisador para voltar à conversa da redação e chamar proxima_etapa."
    elif nxt:
        after = "Etapa aceita. Chame proxima_etapa para seguir."
    else:
        after = "Todas as etapas aceitas. Chame compilar."
    return {"aceita": True, "etapa": stage_key, "resumo": summary, **extra,
            "independencia": state.get("independencia"), "instrucao": after}


def compile_project(store: Store, uid: str, pid: str, draft: bool = False) -> dict:
    project = store.project(uid, pid)
    store.ready(project)
    if project.get("status") == "compilando":
        raise Falha("A compilação já está em andamento.")
    if flow.next_stage(project.get("stages") or {}, mode(project)) is not None:
        raise Falha("Ainda há etapas por aceitar. Veja estado_do_projeto.")
    pending = flow.pending_refs(store.references(project))
    if pending and not draft:
        # Trava da versão final (achado do teste de 25/11/2026: o PDF saiu "pronto" com 7
        # referências erradas). O rascunho continua possível, com marca d'água.
        listed = "; ".join(f"{r['key']} ({flow.REF_LEVEL_LABELS[flow.ref_level(r)]})" for r in pending[:12])
        raise Falha(f"{len(pending)} referência(s) ainda não confirmada(s): {listed}. Leia a capa de cada "
                    "fonte (ficha_da_fonte, ler_trecho) e confirme ou corrija com corrigir_referencia; depois "
                    "chame compilar de novo. Para ver o texto agora, chame compilar com rascunho=true: o PDF sai "
                    "marcado como RASCUNHO.")
    if store._active_jobs(uid) >= MAX_ACTIVE_JOBS:
        raise Falha("Já há trabalhos em andamento no servidor. Aguarde terminarem.")
    snapshot = {}
    if mode(project) == review.MODE:
        # O worker desenha o PRISMA com estes números e os grava na proveniência.
        ctx = review_context(store, project)
        snapshot = {"prisma": ctx.get("prisma"), "concordancia": ctx.get("kappa")}
    job = store._launch(uid, pid, "mcp_compile", [], f"Compilação MCP: {project.get('title', '')}")
    store.update_project(pid, status="compilando", compile_job=job, error="", compile_rascunho=bool(draft),
                         **snapshot)
    return {"status": "compilando", "versao": "rascunho" if draft else "final",
            "instrucao": "Consulte estado_do_projeto em um ou dois minutos."}


def reopen_rewrite(store: Store, uid: str, pid: str, head_id: str) -> dict:
    project = store.project(uid, pid)
    store.ready(project)
    if project.get("status") in BUSY:
        raise Falha("Aguarde o trabalho em andamento terminar.")
    head = (project.get("heads") or {}).get(head_id or "") or {}
    if head.get("kind") != "redatora":
        raise Falha("Só a cabeça redatora reabre a reescrita. Use o identificador recebido em proxima_etapa.")
    try:
        stages = flow.reopen_rewrite(project.get("stages") or {})
    except ValueError as exc:
        raise Falha(str(exc)) from None
    store.update_project(pid, stages=stages, status="pronto", error="")
    return {"reaberta": True, "instrucao": "Chame proxima_etapa: a reescrita volta com o texto anterior e os "
                                           "problemas da compilação. Depois, a verificação será refeita."}


# ================================================================== servidor
def client_name(ctx: Context | None) -> str:
    try:
        params = ctx.request_context.connection.client_params
        if params and params.client_info:
            return f"{params.client_info.name} {params.client_info.version or ''}".strip()
    except Exception:
        pass
    try:
        return str((ctx.headers or {}).get("user-agent", ""))[:80]
    except Exception:
        return ""


class TokenVerifier:
    """Tokens pessoais do Scriptorium (scr_...), com cache por hash SHA-256 e invalidação imediata."""

    def __init__(self, store: Store, ttl: float = 60.0):
        self.store, self.ttl, self.cache = store, ttl, {}
        store._on_revoke.append(self.invalidate)

    def invalidate(self, digest: str) -> None:
        self.cache.pop(digest, None)

    async def verify_token(self, token: str) -> AccessToken | None:
        digest = flow.token_hash(token)
        hit = self.cache.get(digest)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        identity = await anyio.to_thread.run_sync(self.store.token_owner, token)
        if not identity:
            self.cache.pop(digest, None)
            return None
        access = AccessToken(token=token, client_id="scriptorium-token-pessoal", scopes=["scriptorium"],
                             subject=identity["uid"], claims={"email": identity.get("email", "")})
        if len(self.cache) > 500:
            self.cache.clear()
        self.cache[digest] = (time.monotonic() + self.ttl, access)
        return access


def _uid() -> str:
    token = get_access_token()
    if not token or not token.subject:
        raise Falha("Conecte o Scriptorium com a sua chave de conexão (Minha conta > Conectar sua IA).")
    return token.subject


def build_server(store: Store, public_url: str) -> MCPServer:
    base = public_url.rstrip("/")
    server = MCPServer(
        name="scriptorium", title="Scriptorium", version=flow.FLOW_VERSION, instructions=INSTRUCTIONS,
        website_url=base, token_verifier=TokenVerifier(store),
        auth=AuthSettings(issuer_url=base, resource_server_url=base + MCP_PATH, required_scopes=["scriptorium"],
                          validate_token_resource=False),
    )
    run = anyio.to_thread.run_sync

    @server.tool()
    async def listar_fontes() -> dict:
        """Lista as fontes (PDF, DOCX, TXT) da biblioteca do pesquisador no Scriptorium, com os ids para criar_projeto."""
        uid = _uid()
        return {"fontes": await run(store.library, uid)}

    @server.tool()
    async def criar_projeto(titulo: str, pergunta: str, ids_das_fontes: list[str],
                            idioma: Literal["pt-BR", "en"] = "pt-BR",
                            modelo: Literal["abnt-artigo", "abnt-dissertacao", "abnt-tcc", "artigo-simples"] = "abnt-artigo",
                            tipo: Literal["artigo", "dissertacao", "tcc", "revisao_sistematica"] = "artigo") -> dict:
        """Cria um projeto (artigo, dissertação de mestrado, TCC ou revisão sistemática) com até 20 fontes da biblioteca.
        tipo="dissertacao" ou "tcc" usa capítulos ABNT (abntex2); tipo="revisao_sistematica" segue protocolo,
        triagem dupla às cegas (kappa), consenso, qualidade e extração, síntese por QP e PRISMA 2020 antes
        da redação. O Scriptorium lê as fontes e monta as referências oficiais (alguns minutos, sem IA);
        depois use proxima_etapa."""
        uid = _uid()
        if tipo == "dissertacao" and modelo == "abnt-artigo":
            modelo = "abnt-dissertacao"
        elif tipo == "tcc" and modelo == "abnt-artigo":
            modelo = "abnt-tcc"
        record = await run(partial(store.create_project, uid, titulo, pergunta, ids_das_fontes, idioma, modelo, tipo))
        return {"projeto": record["id"], "status": record["status"],
                "instrucao": "Fontes em leitura. Chame estado_do_projeto em um ou dois minutos e depois proxima_etapa."}

    @server.tool()
    async def listar_projetos() -> dict:
        """Lista os projetos de escrita do pesquisador neste modo (sem API)."""
        uid = _uid()
        items = await run(store.projects, uid)
        return {"projetos": [{"projeto": p["id"], "titulo": p.get("title"), "status": p.get("status"),
                              "criado_em": p.get("created_at")} for p in items]}

    @server.tool()
    async def estado_do_projeto(projeto: str) -> dict:
        """Mostra o status do projeto, cada etapa (quem entregou, independência) e a próxima ação."""
        uid = _uid()
        project = await run(store.project, uid, projeto)
        return project_state(store, project)

    @server.tool()
    async def proxima_etapa(projeto: str, ctx: Context, cabeca: str = "", modelo_declarado: str = "") -> dict:
        """Entrega a etapa atual: papel, instruções e o material necessário. Na primeira chamada da
        conversa, deixe cabeca vazio e informe seu modelo em modelo_declarado (ex.: "Claude Opus 5.5");
        guarde o identificador de cabeça devolvido. Se a etapa pedir conversa nova, devolve um passe."""
        uid = _uid()
        return await run(partial(next_step, store, uid, projeto, cabeca or None, modelo_declarado, client_name(ctx)))

    @server.tool()
    async def abrir_passe(codigo: str, ctx: Context, modelo_declarado: str = "") -> dict:
        """Abre, numa conversa nova, a etapa independente (revisão ou verificação) indicada pelo passe
        XXXX-XXXX-XXXX. Informe seu modelo em modelo_declarado."""
        uid = _uid()
        return await run(partial(open_pass, store, uid, codigo, modelo_declarado, client_name(ctx)))

    @server.tool()
    async def referencias_do_projeto(projeto: str) -> dict:
        """Chaves e dados oficiais (BibTeX) das fontes do projeto. Cite somente com estas chaves."""
        uid = _uid()
        project = await run(store.project, uid, projeto)
        store.ready(project)
        refs = await run(store.references, project)
        return {"referencias": [{"chave": r["key"], "tipo": r.get("type"), **(r.get("fields") or {})} for r in refs]}

    @server.tool()
    async def ficha_da_fonte(projeto: str, chave: str) -> dict:
        """Ficha de leitura sem IA de uma fonte do projeto: estrutura, páginas, termos frequentes e abertura."""
        uid = _uid()
        project = await run(store.project, uid, projeto)
        store.ready(project)
        return await run(store.card, project, chave)

    @server.tool()
    async def buscar_trechos(projeto: str, consulta: str, limite: int = 8,
                             zona: Literal["", "resumo", "introducao", "metodo", "resultados", "discussao",
                                           "limitacoes", "referencias"] = "") -> dict:
        """Busca (BM25) nos trechos das fontes do projeto. Devolve chave, chunk_id, páginas, zona do artigo
        (método, resultados, limitações...) e um recorte. Use zona para procurar só numa parte."""
        uid = _uid()
        project = await run(store.project, uid, projeto)
        store.ready(project)
        return await run(store.search, project, consulta, max(1, min(int(limite), 20)), zona)

    @server.tool()
    async def ler_trecho(projeto: str, chunk_id: str, vizinhos: int = 0) -> dict:
        """Texto integral de um trecho (e, opcionalmente, dos vizinhos). Copie daqui as citações literais."""
        uid = _uid()
        project = await run(store.project, uid, projeto)
        store.ready(project)
        return await run(store.read_chunk, project, chunk_id, max(0, min(int(vizinhos), 2)))

    @server.tool()
    async def entregar_etapa(projeto: str, etapa: str, conteudo: str, cabeca: str, ctx: Context,
                             modelo_declarado: str = "", respostas_revisao: str = "") -> dict:
        """Entrega o resultado da etapa atual. O Scriptorium confere formato, chaves e citações literais;
        na reescrita, aceita respostas_revisao (lista JSON [{id, acao, justificativa}]) ou comentários '% [P1] ...'.
        Se recusar, devolve os erros para corrigir e entregar de novo."""
        uid = _uid()
        return await run(partial(deliver, store, uid, projeto, etapa, conteudo, cabeca, modelo_declarado,
                                 client_name(ctx), respostas_revisao))

    @server.tool()
    async def corrigir_referencia(projeto: str, chave: str, cabeca: str, autores: list[str], titulo: str,
                                  ano: str, tipo: Literal["article", "inproceedings", "incollection",
                                                          "phdthesis", "mastersthesis", "book",
                                                          "techreport", "misc"] = "article",
                                  veiculo: str = "", doi: str = "") -> dict:
        """Corrige autor, título, ano, tipo, veículo e DOI de uma referência do projeto, mantendo a chave.
        Leia antes a capa ou a primeira página da fonte (ficha_da_fonte, buscar_trechos, ler_trecho).
        O Scriptorium só aceita o que aparece no próprio documento: título e sobrenomes nas primeiras
        páginas; ano, veículo e DOI em algum lugar do texto. Autores no formato 'Sobrenome, Nome'."""
        uid = _uid()
        project = await run(store.project, uid, projeto)
        store.ready(project)
        fix = {"autores": autores, "titulo": titulo, "ano": ano, "tipo": tipo, "veiculo": veiculo, "doi": doi}
        return await run(partial(store.correct_reference, project, chave, cabeca, fix))

    @server.tool()
    async def compilar(projeto: str, rascunho: bool = False) -> dict:
        """Depois de todas as etapas aceitas, monta o LaTeX com a bibliografia oficial e gera o PDF (sem IA).
        A versão final exige todas as referências confirmadas (corrigir_referencia) e sai sem erro de
        LaTeX; com rascunho=true, ou se algo faltar, o PDF sai marcado como RASCUNHO."""
        uid = _uid()
        return await run(partial(compile_project, store, uid, projeto, rascunho))

    @server.tool()
    async def refazer_referencias(projeto: str) -> dict:
        """Refaz a bibliografia oficial do projeto com as regras atuais (DOI, OpenAlex, texto da fonte), sem IA.
        Mantém as chaves já citadas e as correções feitas com corrigir_referencia."""
        uid = _uid()
        return await run(partial(store.rebuild_references, uid, projeto))

    @server.tool()
    async def reabrir_reescrita(projeto: str, cabeca: str) -> dict:
        """Reabre a reescrita (e a verificação) de um projeto já aceito, para corrigir um problema que só
        apareceu na compilação, como um erro de LaTeX. Só a cabeça redatora pode reabrir."""
        uid = _uid()
        return await run(partial(reopen_rewrite, store, uid, projeto, cabeca))

    return server


def build_app(store: Store, public_url: str):
    """App Starlette do MCP (sem estado e com respostas JSON, por causa do Firebase Hosting)."""
    server = build_server(store, public_url)
    return server.streamable_http_app(
        streamable_http_path=MCP_PATH, json_response=True, stateless_http=True,
        # Atrás do Firebase Hosting o Host varia; a proteção vem do token.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))


class Dispatcher:
    """Encaminha /api/mcp para o app MCP e o resto para a API FastAPI.

    /api/mcp/t/<token> vira /api/mcp com o token no cabeçalho, para clientes que
    só aceitam um endereço (o token fica no log de acesso do Cloud Run: por isso
    ele é revogável e só dá acesso às ferramentas do MCP).
    """

    def __init__(self, api_app, mcp_app):
        self.api_app, self.mcp_app = api_app, mcp_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.mcp_app(scope, receive, send)
        path = scope.get("path", "")
        if scope["type"] == "http" and (path.rstrip("/") == MCP_PATH or path.startswith(MCP_PATH + "/t/")
                                        or path.startswith("/.well-known/oauth-protected-resource")):
            if path.startswith(MCP_PATH + "/t/"):
                token = path[len(MCP_PATH) + 3:].strip("/")
                headers = [(k, v) for k, v in scope.get("headers", []) if k.lower() != b"authorization"]
                headers.append((b"authorization", b"Bearer " + token.encode("latin-1", "ignore")))
                scope = {**scope, "headers": headers}
            if path.startswith(MCP_PATH) and path != MCP_PATH:
                scope = {**scope, "path": MCP_PATH, "raw_path": MCP_PATH.encode()}
            return await self.mcp_app(scope, receive, send)
        return await self.api_app(scope, receive, send)
