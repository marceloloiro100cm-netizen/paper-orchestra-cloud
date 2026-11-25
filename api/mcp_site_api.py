"""Rotas do site para o modo sem API (MCP): tokens pessoais e projetos.

O token é mostrado uma única vez, na criação; o Firestore guarda só o hash.
"""
from __future__ import annotations

import re
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from mcp_server import MCP_PATH, Falha, Store, project_state

FILES = {"scriptorium.pdf": "application/pdf", "scriptorium.tex": "text/x-tex",
         "references.bib": "text/x-bibtex", "proveniencia.json": "application/json"}


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

    @router.get("/projetos")
    def list_projects(user: dict = dependency):
        return {"projetos": [project_state(store, p) for p in store.projects(user["uid"])]}

    @router.get("/projetos/{project_id}")
    def get_project(project_id: str, user: dict = dependency):
        try:
            return project_state(store, store.project(user["uid"], project_id))
        except Falha:
            raise HTTPException(404, "Projeto não encontrado.") from None

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
