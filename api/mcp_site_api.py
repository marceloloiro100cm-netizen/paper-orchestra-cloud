"""Rotas do site para o modo sem API (MCP): tokens pessoais e projetos.

O token é mostrado uma única vez, na criação; o Firestore guarda só o hash.
"""
from __future__ import annotations

import re
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

import mcp_review as review
import mcp_student as student
from mcp_server import MCP_PATH, Falha, Store, mode, project_state, review_context

FILES = {"scriptorium.pdf": "application/pdf", "scriptorium.tex": "text/x-tex",
         "references.bib": "text/x-bibtex", "proveniencia.json": "application/json"}


class FinalSynthesis(BaseModel):
    qp: str = Field(pattern=r"^QP\d{1,2}$")
    texto: str = Field(default="", max_length=8000)


class NewToken(BaseModel):
    label: str = Field(default="Minha IA", min_length=1, max_length=60)


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
                **student.view(project, mode(project), refs, project.get("concordancia"))}

    @router.get("/projetos")
    def list_projects(user: dict = dependency):
        return {"projetos": [for_student(p) for p in store.projects(user["uid"])]}

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

    @router.get("/projetos/{project_id}/arquivos/{name}")
    def download(project_id: str, name: str, user: dict = dependency):
        if name not in FILES:
            raise HTTPException(404, "Arquivo indisponível.")
        try:
            project = store.project(user["uid"], project_id)
        except Falha:
            raise HTTPException(404, "Projeto não encontrado.") from None
        blob = store.bucket.blob(f"{Store.prefix(project)}/final/{name}")
        if not blob.exists():
            raise HTTPException(404, "Arquivo indisponível para este projeto.")
        return Response(content=blob.download_as_bytes(), media_type=FILES[name],
                        headers={"Content-Disposition": f'attachment; filename="{name}"',
                                 "Cache-Control": "no-store"})

    return router
