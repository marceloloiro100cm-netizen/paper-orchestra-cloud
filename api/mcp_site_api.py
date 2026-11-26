"""Rotas do site para o modo sem API (MCP): tokens pessoais e projetos.

O token é mostrado uma única vez, na criação; o Firestore guarda só o hash.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

import docx_export
import mcp_flow as flow
import mcp_review as review
import mcp_student as student
from mcp_server import MCP_PATH, Falha, Store, compile_project, mode, project_state, review_context

FILES = {
    "scriptorium.pdf": "application/pdf",
    "scriptorium.docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "scriptorium.tex": "text/x-tex",
    "references.bib": "text/x-bibtex",
    "proveniencia.json": "application/json",
}
WORK_LABELS = {
    "artigo": "Artigo científico",
    "dissertacao": "Dissertação de mestrado",
    "tcc": "TCC / Monografia de graduação",
    "revisao_sistematica": "Revisão sistemática",
}


class NewProject(BaseModel):
    titulo: str = Field(min_length=3, max_length=120)
    pergunta: str = Field(min_length=20, max_length=4000)
    fontes: list[str] = Field(min_length=1, max_length=20)
    idioma: str = "pt-BR"
    modelo: str = "abnt-artigo"
    tipo: str = "artigo"


class FinalSynthesis(BaseModel):
    qp: str = Field(pattern=r"^QP\d{1,2}$")
    texto: str = Field(default="", max_length=8000)


class NewToken(BaseModel):
    label: str = Field(default="Minha IA", min_length=1, max_length=60)


class ConfirmReference(BaseModel):
    aceitar_proposta: bool = False
    autores: list[str] | str = Field(default_factory=list)
    titulo: str = ""
    ano: str = ""
    tipo: str = "article"
    veiculo: str = ""
    doi: str = ""


class CompileRequest(BaseModel):
    rascunho: bool = False


class AdvisorShareRequest(BaseModel):
    dias: int = Field(default=14, ge=1, le=30)
    nota: str = Field(default="", max_length=600)


def make_mcp_site_router(store: Store, verify_user: Callable, public_url: str):
    router = APIRouter(prefix="/api/mcp-conta", tags=["mcp"])
    dependency = Depends(verify_user)
    base = public_url.rstrip("/")

    @router.get("/tokens")
    def list_tokens(user: dict = dependency):
        return {"tokens": store.list_tokens(user["uid"]), "endereco": base + MCP_PATH}

    @router.post("/tokens", status_code=201)
    def create_token(payload: NewToken, user: dict = dependency):
        try:
            created = store.create_token(user["uid"], user.get("email", ""), payload.label)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        return {**created, "endereco": base + MCP_PATH,
                "endereco_com_token": f"{base}{MCP_PATH}/t/{created['token']}"}

    @router.delete("/tokens/{token_id}")
    def revoke_token(token_id: str, user: dict = dependency):
        if not re.fullmatch(r"[0-9a-f]{16}", token_id) or not store.revoke_token(user["uid"], token_id):
            raise HTTPException(404, "Token não encontrado.")
        return {"revogado": True}

    def for_student(project: dict) -> dict:
        """Estado do projeto mais a visão do estudante (próximo passo, provas, referências)."""
        try:
            refs = store.references(project)
        except Exception:  # arquivo ausente ou ilegível: a visão segue sem as referências
            refs = []
        return {**project_state(store, project),
                **student.view(project, mode(project), refs, project.get("concordancia")),
                "tem_link_orientacao": bool(project.get("advisor_share_id")),
                "link_orientacao_expira": project.get("advisor_share_expires") or ""}

    @router.get("/projetos")
    def list_projects(user: dict = dependency):
        projects = store.projects(user["uid"])
        if len(projects) <= 1:
            return {"projetos": [for_student(p) for p in projects]}
        # Onda 1 (G1): evita N leituras sequenciais no GCS quando há vários projetos.
        with ThreadPoolExecutor(max_workers=min(6, len(projects))) as pool:
            return {"projetos": list(pool.map(for_student, projects))}

    @router.post("/projetos", status_code=201)
    def create_project_site(payload: NewProject, user: dict = dependency):
        """Onda 2: cria artigo, dissertação ou TCC direto pelo site (com ou sem plano do Guia)."""
        modelo = payload.modelo
        if payload.tipo == "dissertacao" and modelo == "abnt-artigo":
            modelo = "abnt-dissertacao"
        elif payload.tipo == "tcc" and modelo == "abnt-artigo":
            modelo = "abnt-tcc"
        try:
            record = store.create_project(
                user["uid"], payload.titulo, payload.pergunta, payload.fontes,
                payload.idioma, modelo, payload.tipo,
            )
        except Falha as exc:
            raise HTTPException(422, str(exc)) from None
        return for_student(record)

    @router.get("/projetos/{project_id}")
    def get_project(project_id: str, user: dict = dependency):
        try:
            return for_student(store.project(user["uid"], project_id))
        except Falha:
            raise HTTPException(404, "Projeto não encontrado.") from None

    def owned(project_id: str, user: dict) -> dict:
        try:
            return store.project(user["uid"], project_id)
        except Falha:
            raise HTTPException(404, "Projeto não encontrado.") from None

    @router.post("/projetos/{project_id}/referencias/refazer", status_code=202)
    def rebuild_references(project_id: str, user: dict = dependency):
        """Refaz a bibliografia do projeto com as regras atuais, mantendo chaves e correções."""
        owned(project_id, user)
        try:
            return store.rebuild_references(user["uid"], project_id)
        except Falha as exc:
            raise HTTPException(409, str(exc)) from None

    @router.get("/projetos/{project_id}/referencias/{key}/capa")
    def reference_cover(project_id: str, key: str, page: int = Query(default=1, ge=1, le=5),
                        user: dict = dependency):
        """Item 7 + Onda 1 (G3): renderiza e cacheia no GCS a capa (pág. 1..5) do PDF."""
        project = owned(project_id, user)
        refs = store.references(project)
        entry = next((r for r in refs if r.get("key") == key), None)
        sid = (entry or {}).get("source_id")
        source = next((s for s in (project.get("sources") or []) if s.get("id") == sid), None)
        if not source or source.get("format") != "pdf":
            raise HTTPException(404, "Capa disponível apenas para fontes em PDF.")
        path = str(source.get("object_path", ""))
        if not path.startswith(f"library/{user['uid']}/{source['id']}/"):
            raise HTTPException(404, "Fonte indisponível.")
        sha = str(source.get("sha256") or "")
        cache_prefix = (f"library/{user['uid']}/derived/covers/{sha}_p{page}"
                        if re.fullmatch(r"[0-9a-f]{64}", sha) else "")
        if cache_prefix:
            cached_png = store.bucket.blob(cache_prefix + ".png")
            if cached_png.exists():
                png = cached_png.download_as_bytes()
                meta = store._json(cache_prefix + ".json", {}) or {}
                return Response(content=png, media_type="image/png", headers={
                    "Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff",
                    "X-Scriptorium-Page": str(meta.get("page", page)),
                    "X-Scriptorium-Pages-Total": str(meta.get("total", page)),
                })
        blob = store.bucket.blob(path)
        if not blob.exists():
            raise HTTPException(404, "Arquivo original não encontrado.")
        from pdf_render import fitz
        with fitz.open(stream=blob.download_as_bytes(), filetype="pdf") as doc:
            if doc.page_count == 0:
                raise HTTPException(404, "PDF sem páginas.")
            target = min(page, doc.page_count)
            png = doc[target - 1].get_pixmap(dpi=115, alpha=False).tobytes("png")
            total = doc.page_count
        if cache_prefix:
            try:
                store.bucket.blob(cache_prefix + ".png").upload_from_string(png, content_type="image/png")
                store.bucket.blob(cache_prefix + ".json").upload_from_string(
                    json.dumps({"page": target, "total": total}), content_type="application/json")
            except Exception:
                pass
        return Response(content=png, media_type="image/png", headers={
            "Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff",
            "X-Scriptorium-Page": str(target), "X-Scriptorium-Pages-Total": str(total),
        })

    @router.post("/projetos/{project_id}/referencias/{key}/confirmar")
    def confirm_reference(project_id: str, key: str, payload: ConfirmReference, user: dict = dependency):
        """Itens 6 e 7: confirmação humana em 1 clique ao lado da capa (salva também na biblioteca)."""
        owned(project_id, user)
        try:
            return store.confirm_reference_human(user["uid"], project_id, key, payload.model_dump())
        except Falha as exc:
            raise HTTPException(422, str(exc)) from None

    @router.post("/projetos/{project_id}/compilar", status_code=202)
    def trigger_compile(project_id: str, payload: CompileRequest, user: dict = dependency):
        """Permite gerar PDF final ou rascunho direto pelo botão no site."""
        owned(project_id, user)
        try:
            return compile_project(store, user["uid"], project_id, draft=payload.rascunho)
        except Falha as exc:
            raise HTTPException(409, str(exc)) from None

    def _project_docx_bytes(project: dict, refs: list[dict] | None = None) -> bytes | None:
        prefix = f"{Store.prefix(project)}/final/"
        docx_blob = store.bucket.blob(prefix + "scriptorium.docx")
        if docx_blob.exists():
            return docx_blob.download_as_bytes()
        tex_blob = store.bucket.blob(prefix + "scriptorium.tex")
        if not tex_blob.exists():
            return None
        tex = tex_blob.download_as_bytes().decode("utf-8", errors="replace")
        ref_list = refs if refs is not None else store.references(project)
        is_final = student.final_pdf(project, len(flow.pending_refs(ref_list)))
        return docx_export.build_docx(
            project.get("title") or project["id"], tex, ref_list,
            is_final=is_final, work_label=WORK_LABELS.get(mode(project), "Artigo científico"),
        )

    @router.get("/projetos/{project_id}/pacote-orientacao.zip")
    def advisor_package(project_id: str, user: dict = dependency):
        """Pacote para orientação: PDF, Word (.docx), BibTeX, proveniência e resumo legível em um só ZIP."""
        project = owned(project_id, user)
        prefix = f"{Store.prefix(project)}/final/"
        refs = store.references(project)
        view = student.view(project, mode(project), refs, project.get("concordancia"))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in ("scriptorium.pdf", "references.bib", "proveniencia.json"):
                blob = store.bucket.blob(prefix + name)
                if blob.exists():
                    zf.writestr(name, blob.download_as_bytes())
            docx_bytes = _project_docx_bytes(project, refs)
            if docx_bytes:
                zf.writestr("scriptorium.docx", docx_bytes)
            lines = [
                f"# Pacote para orientação — {project.get('title') or project['id']}",
                "",
                f"- **Situação:** {'PDF final (todas as travas aprovadas)' if view['pdf_final'] else 'Rascunho / com pendências'}",
                f"- **Tipo:** {mode(project)}",
                "",
                "## O que o Scriptorium conferiu",
            ]
            for p in view.get("provas") or ["Nenhuma etapa concluída ainda."]:
                lines.append(f"- {p}")
            pending = view.get("referencias_a_conferir") or []
            lines += ["", "## Pendências antes da versão final"]
            if pending:
                for r in pending:
                    lines.append(f"- `{r['chave']}` ({r['nivel_texto']}): {r.get('titulo') or 'sem título'}")
            else:
                lines.append("- Nenhuma referência pendente.")
            err = str(project.get("error") or "").strip()
            if err:
                lines += ["", "## Avisos da última compilação", err]
            zf.writestr("resumo_para_orientacao.md", "\n".join(lines).encode("utf-8"))
        return Response(content=buf.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="pacote_orientacao.zip"',
                                 "Cache-Control": "no-store"})

    @router.get("/projetos/{project_id}/detalhe")
    def detail(project_id: str, user: dict = dependency):
        project = owned(project_id, user)
        out = {"estado": for_student(project)}
        if mode(project) != review.MODE:
            return out
        ctx = review_context(store, project)
        protocol = ctx.get("protocol") or {}
        cut = protocol.get("nota_corte")
        out["revisao"] = {
            "questoes": protocol.get("questoes", []),
            "campos": [e["campo"] for e in protocol.get("extracao", [])],
            "nota_corte": cut,
            "concordancia": ctx.get("kappa"),
            "prisma": {k: v for k, v in (ctx.get("prisma") or {}).items() if k != "chaves_incluidas"} or None,
            "estudos": [{"chave": r["chave"], "nota": r["nota"],
                         "abaixo_do_corte": r["chave"] in (ctx.get("below_cut") or []), **r["extracao"]}
                        for r in ctx.get("rows", [])],
            "sintese": ctx.get("synthesis") or {},
            "redacao_aceita": (project.get("stages") or {}).get("redacao", {}).get("status") == "aceita",
        }
        return out

    @router.put("/projetos/{project_id}/sintese")
    def save_synthesis(project_id: str, payload: FinalSynthesis, user: dict = dependency):
        project = owned(project_id, user)
        if mode(project) != review.MODE:
            raise HTTPException(422, "Só projetos de revisão sistemática têm síntese por questão.")
        final = dict(project.get("sintese_final") or {})
        if payload.texto.strip():
            final[payload.qp] = payload.texto.strip()
        else:
            final.pop(payload.qp, None)
        store.update_project(project["id"], sintese_final=final)
        late = (project.get("stages") or {}).get("redacao", {}).get("status") == "aceita"
        return {"salvo": True, "aviso": "A redação já foi aceita: a nova versão vale para a reescrita." if late else ""}

    @router.get("/projetos/{project_id}/matriz.csv")
    def matrix(project_id: str, user: dict = dependency):
        project = owned(project_id, user)
        ctx = review_context(store, project)
        if not ctx.get("rows"):
            raise HTTPException(404, "A matriz de extração ainda não foi aceita.")
        data = review.matrix_csv(ctx["rows"], ctx.get("protocol") or {})
        return Response(content=("\ufeff" + data).encode("utf-8"), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="matriz_extracao.csv"',
                                 "Cache-Control": "no-store"})

    @router.post("/projetos/{project_id}/orientacao/link", status_code=201)
    def create_advisor_link(project_id: str, payload: AdvisorShareRequest, user: dict = dependency):
        """Onda 3: gera link temporário (somente leitura) para o(a) orientador(a)."""
        owned(project_id, user)
        try:
            created = store.create_advisor_share(user["uid"], project_id, payload.dias, payload.nota)
        except Falha as exc:
            raise HTTPException(404, str(exc)) from None
        return {
            "id": created["id"],
            "url": f"{base}/?orientacao={created['token']}",
            "expira_em": created["expires_at"],
        }

    @router.delete("/projetos/{project_id}/orientacao/link")
    def revoke_advisor_link(project_id: str, user: dict = dependency):
        """Revoga imediatamente o link de orientação deste projeto."""
        owned(project_id, user)
        store.revoke_advisor_share(user["uid"], project_id)
        return {"revogado": True}

    @router.get("/projetos/{project_id}/arquivos/{name}")
    def download(project_id: str, name: str, user: dict = dependency):
        if name not in FILES:
            raise HTTPException(404, "Arquivo indisponível.")
        try:
            project = store.project(user["uid"], project_id)
        except Falha:
            raise HTTPException(404, "Projeto não encontrado.") from None
        if name == "scriptorium.docx":
            docx_bytes = _project_docx_bytes(project)
            if not docx_bytes:
                raise HTTPException(404, "Word (.docx) disponível assim que o texto for compilado.")
            return Response(content=docx_bytes, media_type=FILES[name],
                            headers={"Content-Disposition": 'attachment; filename="scriptorium.docx"',
                                     "Cache-Control": "no-store"})
        blob = store.bucket.blob(f"{Store.prefix(project)}/final/{name}")
        if not blob.exists():
            raise HTTPException(404, "Arquivo indisponível para este projeto.")
        return Response(content=blob.download_as_bytes(), media_type=FILES[name],
                        headers={"Content-Disposition": f'attachment; filename="{name}"',
                                 "Cache-Control": "no-store"})

    return router


def make_advisor_public_router(store: Store):
    """Onda 3: visão somente leitura para o(a) orientador(a) via link temporário autorizado pelo estudante."""
    router = APIRouter(prefix="/api/orientacao", tags=["orientacao"])

    @router.get("/{token}")
    def read_shared_project(token: str, response: Response):
        found = store.read_advisor_share(token)
        if not found:
            raise HTTPException(404, "Link de orientação inválido, expirado ou revogado pelo estudante.")
        share, project, refs = found["share"], found["project"], found["refs"]
        state = project_state(store, project)
        view = student.view(project, mode(project), refs, project.get("concordancia"))
        pending = view.get("referencias_a_conferir") or []
        confirmed = [
            {
                "chave": r.get("key", ""),
                "titulo": str((r.get("fields") or {}).get("title") or ""),
                "autor": str((r.get("fields") or {}).get("author") or ""),
                "ano": str((r.get("fields") or {}).get("year") or ""),
            }
            for r in refs if flow.ref_level(r) == "confirmada"
        ]
        response.headers["Cache-Control"] = "no-store"
        return {
            "titulo": project.get("title") or "Sem título",
            "tipo": WORK_LABELS.get(mode(project), "Artigo científico"),
            "status": project.get("status") or "",
            "pdf_final": bool(view.get("pdf_final")),
            "etapas": [{"titulo": e.get("titulo"), "status": e.get("status"), "independencia": e.get("independencia")}
                       for e in (state.get("etapas") or [])],
            "provas": view.get("provas") or [],
            "referencias_confirmadas": confirmed,
            "referencias_pendentes": [{"chave": r.get("chave"), "titulo": r.get("titulo"), "nivel": r.get("nivel_texto")}
                                      for r in pending],
            "nota_estudante": share.get("note") or "",
            "atualizado_em": project.get("updated_at") or "",
            "expira_em": share.get("expires_at") or "",
            "pergunta": str(project.get("question") or "")[:1200],
        }

    return router
