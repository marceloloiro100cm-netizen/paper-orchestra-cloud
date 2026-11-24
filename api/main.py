"""Backend autenticado do PaperOrchestra Cloud.

As chaves Gemini ficam somente no Cloud Run Job (Secret Manager); não entram aqui.
"""
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal
from library import make_library_router, MAX_SELECTED_SOURCES
from access import (Invitation, get_access, is_admin, set_invitation,
                    request_access, pending_access_requests, mark_request_decided)
from credentials import GeminiCredential, store_credential, delete_credential
from model_access import SUPPORTED_MODELS, verify_key_models, get_model_capabilities

import firebase_admin
from firebase_admin import auth
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from google.cloud import firestore, storage, run_v2
from pydantic import BaseModel, Field, field_validator

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
REGION = os.getenv("REGION", "us-east4")
BUCKET = os.environ["RESEARCH_BUCKET"]
ALLOWED_EMAILS = {x.strip().lower() for x in os.getenv("ALLOWED_EMAILS", "").split(",") if x.strip()}
JOB_NAME = f"projects/{PROJECT}/locations/{REGION}/jobs/paper-orchestra-worker"
NEON_REVIEW_ENABLED = os.getenv("NEON_REVIEW_ENABLED", "false").lower() == "true"
# Fails closed until IAM has been provisioned and audited in deployment.
BYOK_ENABLED = os.getenv("BYOK_ENABLED", "false").lower() == "true"

if not ALLOWED_EMAILS:
    raise RuntimeError("ALLOWED_EMAILS vazio: por segurança, a API não inicia.")

firebase_admin.initialize_app(options={"projectId": PROJECT})
db = firestore.Client(project=PROJECT)
storage_client = storage.Client(project=PROJECT)
run_client = run_v2.JobsClient()
bucket = storage_client.bucket(BUCKET)
app = FastAPI(title="PaperOrchestra Cloud", docs_url=None, redoc_url=None, openapi_url=None)


class NewResearch(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    idea: str = Field(min_length=40, max_length=150_000)
    experimental_log: str = Field(min_length=40, max_length=150_000)
    template: Literal["cvpr2025", "iclr2025", "abnt-artigo", "abnt-dissertacao"] = "iclr2025"
    model: Literal["gemini-3.1-pro-preview", "gemini-3-flash-preview"] = "gemini-3-flash-preview"
    # Permite avaliar um manuscrito com modelo diferente do usado na redação.
    reflection_model: Literal["gemini-3.1-pro-preview", "gemini-3-flash-preview"] | None = None
    plotting: bool = False
    neon_review: bool = False
    # Idioma do manuscrito solicitado, sem alterar o template LaTeX.
    language: Literal["en", "pt-BR"] = "en"
    source_ids: list[str] = Field(default_factory=list, max_length=MAX_SELECTED_SOURCES)

    @field_validator("idea", "experimental_log")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("O material não pode estar vazio")
        return value


def verified_google_user(authorization: Annotated[str | None, Header()] = None):
    """Identidade Google verificada, ainda SEM conceder acesso à pesquisa."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Entre com sua conta Google")
    try:
        return auth.verify_id_token(authorization[7:], check_revoked=True)
    except Exception:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada") from None


def current_user(token: Annotated[dict, Depends(verified_google_user)]):
    if not (is_admin(token, ALLOWED_EMAILS)
            or (BYOK_ENABLED and get_access(db, token, ALLOWED_EMAILS)["allowed"])):
        raise HTTPException(status_code=403, detail="Conta não autorizada")
    return token


VerifiedUser = Annotated[dict, Depends(verified_google_user)]
User = Annotated[dict, Depends(current_user)]

# Biblioteca própria privada, separada das pesquisas já concluídas.
app.include_router(make_library_router(db, bucket, current_user))


def get_research(job_id: str, user: dict) -> dict:
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(status_code=404, detail="Pesquisa não encontrada")
    snap = db.collection("research_jobs").document(job_id).get()
    if not snap.exists or snap.to_dict().get("owner_uid") != user["uid"]:
        raise HTTPException(status_code=404, detail="Pesquisa não encontrada")
    return snap.to_dict()


def serializable(record: dict) -> dict:
    return {
        "id": record["id"],
        "title": record["title"],
        "status": record["status"],
        "stage": record.get("stage", ""),
        "agents": record.get("agents"),
        "model": record.get("model", ""),
        "reflection_model": record.get("reflection_model") or record.get("model", ""),
        "language": record.get("language", "en"),
        "audit_status": record.get("audit_status", "not_available"),
        "neon_review_requested": record.get("neon_review_requested", False),
        "neon_review_status": record.get("neon_review_status", "not_available"),
        "reference_status": record.get("reference_status", "not_available"),
        "references_checked": record.get("references_checked"),
        "references_skipped": record.get("references_skipped"),
        "audit_findings": record.get("audit_findings"),
        "error": record.get("error", ""),
        "created_at": record.get("created_at", ""),
        "finished_at": record.get("finished_at", ""),
        "files": record.get("files", []),
        "sources": [{k: entry.get(k) for k in ("id", "name", "format", "sha256")} for entry in record.get("sources", [])],
    }


@app.get("/api/health")
def health():
    return {"ok": True, "version": "v1"}

@app.get("/api/capabilities")
def capabilities(user: User):
    access = get_access(db, user, ALLOWED_EMAILS)
    models = list(SUPPORTED_MODELS) if access["admin"] else get_model_capabilities(db, user["uid"])["allowed_models"]
    return {
        # Neon usa integração administrativa específica, NÃO é liberado por Gemini Pro.
        "neon_review": NEON_REVIEW_ENABLED and access["admin"],
        "neon_model": "gemini-4-neon",
        "allowed_models": models,
    }


@app.get("/api/account/access")
def account_access(user: User):
    access = get_access(db, user, ALLOWED_EMAILS)
    model_access = ({"status": "admin_vertex", "allowed_models": list(SUPPORTED_MODELS)}
                    if access["admin"] else get_model_capabilities(db, user["uid"]))
    allowed = model_access["allowed_models"]
    return {
        "admin": access["admin"],
        "byok_ready": BYOK_ENABLED and access["byok_ready"],
        "key_connected": BYOK_ENABLED and access["byok_ready"] and not access["admin"],
        "multiuser_enabled": BYOK_ENABLED,
        "research_generation_enabled": access["admin"] or
            (BYOK_ENABLED and access["byok_ready"] and bool(allowed)),
        "allowed_models": allowed,
        "model_status": model_access.get("model_status", {}),
        "model_check_status": model_access["status"],
        "model_checked_at": model_access.get("checked_at", ""),
    }


@app.post("/api/account/request-access", status_code=202)
def request_research_access(user: VerifiedUser):
    """Não concede biblioteca ou geração. Apenas registra pedido de convite."""
    if not BYOK_ENABLED:
        raise HTTPException(status_code=503, detail="Solicitação indisponível; contate o administrador.")
    return request_access(db, user)


@app.get("/api/admin/access-requests")
def list_access_requests(user: User):
    if not is_admin(user, ALLOWED_EMAILS):
        raise HTTPException(status_code=403, detail="Somente administradores podem consultar solicitações.")
    return {"items": pending_access_requests(db)}


@app.put("/api/account/credential")
def save_personal_credential(payload: GeminiCredential, user: User):
    if not BYOK_ENABLED:
        raise HTTPException(status_code=503, detail="Credenciais individuais indisponíveis até aprovação da infraestrutura.")
    if is_admin(user, ALLOWED_EMAILS):
        raise HTTPException(status_code=409, detail="A conta administradora usa a configuração existente.")
    # Chave enviada somente pela sessão autenticada. Nunca retorna o valor.
    try:
        key = payload.normalized
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato da chave inválido.") from None
    # Prova acesso a cada modelo; a simples listagem de modelos não concede permissão.
    # Chamadas mínimas de geração podem consumir a quota ou ter custo na conta da chave.
    checks = verify_key_models(key)
    if checks["status"] == "invalid_key":
        raise HTTPException(status_code=422, detail="O Google recusou esta chave. Confira a chave no AI Studio.")
    try:
        stored = store_credential(db, PROJECT, user["uid"], key, model_access=checks)
    except Exception:
        raise HTTPException(status_code=503, detail="Não foi possível guardar a chave com segurança.") from None
    return {**stored, "allowed_models": checks["allowed_models"],
            "model_status": checks["model_status"], "verification_status": checks["status"]}


@app.delete("/api/account/credential")
def remove_personal_credential(user: User):
    if not BYOK_ENABLED:
        raise HTTPException(status_code=503, detail="Credenciais individuais indisponíveis até aprovação da infraestrutura.")
    if is_admin(user, ALLOWED_EMAILS):
        raise HTTPException(status_code=409, detail="A credencial do administrador não é gerenciada aqui.")
    try:
        return delete_credential(db, PROJECT, user["uid"])
    except Exception:
        raise HTTPException(status_code=503, detail="Credencial desativada; não foi possível confirmar a exclusão no cofre.") from None


@app.post("/api/admin/invitations", status_code=201)
def invite_researcher(payload: Invitation, user: User):
    if not BYOK_ENABLED:
        raise HTTPException(status_code=503, detail="Convites indisponíveis até aprovação da infraestrutura.")
    if not is_admin(user, ALLOWED_EMAILS):
        raise HTTPException(status_code=403, detail="Apenas administradores podem convidar.")
    result = set_invitation(db, payload.email, True, user["uid"], ALLOWED_EMAILS)
    mark_request_decided(db, payload.email, "approved")
    return result


@app.delete("/api/admin/invitations/{email}")
def revoke_researcher(email: str, user: User):
    if not BYOK_ENABLED:
        raise HTTPException(status_code=503, detail="Convites indisponíveis até aprovação da infraestrutura.")
    if not is_admin(user, ALLOWED_EMAILS):
        raise HTTPException(status_code=403, detail="Apenas administradores podem revogar.")
    try:
        result = set_invitation(db, email, False, user["uid"], ALLOWED_EMAILS)
        mark_request_decided(db, email, "revoked")
        return result
    except ValueError:
        raise HTTPException(status_code=422, detail="E-mail inválido.") from None


@app.get("/api/jobs")
def list_researches(user: User):
    # Consulta simples, sem índices compostos. Ordenação em memória para acervo pessoal.
    docs = db.collection("research_jobs").where("owner_uid", "==", user["uid"]).limit(200).stream()
    items = [serializable(s.to_dict()) for s in docs]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"items": items}


@app.post("/api/jobs", status_code=202)
def create_research(payload: NewResearch, user: User):
    owner_uid = user["uid"]
    access = get_access(db, user, ALLOWED_EMAILS)
    allowed_models = (list(SUPPORTED_MODELS) if access["admin"]
                      else get_model_capabilities(db, owner_uid)["allowed_models"])
    if not (access["admin"] or (BYOK_ENABLED and access["byok_ready"] and allowed_models)):
        # Bloqueia geração com chave cadastrada, mas ainda não validada, sem usar a conta central.
        raise HTTPException(status_code=409, detail="Conecte e verifique sua chave Gemini antes de pesquisar.")
    if payload.model not in allowed_models or (payload.reflection_model and payload.reflection_model not in allowed_models):
        raise HTTPException(status_code=403, detail="Modelo indisponível para esta chave Gemini. Verifique sua conexão.")
    if payload.plotting and not access["admin"]:
        raise HTTPException(status_code=403, detail="Imagens exigem verificação separada; recurso indisponível nesta conta.")
    if payload.neon_review and not access["admin"]:
        raise HTTPException(status_code=422, detail="A revisão Neon exige um provedor compatível e não está disponível no BYOK.")
    if payload.neon_review and not NEON_REVIEW_ENABLED:
        raise HTTPException(status_code=409, detail="Revisão Neon indisponível até validar o acesso do worker.")
    # Proteção de custos: uma geração por vez por conta.
    docs = db.collection("research_jobs").where("owner_uid", "==", owner_uid).limit(200).stream()
    for s in docs:
        if s.to_dict().get("status") in ("queued", "running"):
            raise HTTPException(status_code=409, detail="Há uma pesquisa em execução. Finalize-a antes de iniciar outra.")
    # Validar propriedade antes de iniciar tarefas caras ou armazenar a solicitação.
    source_ids = list(dict.fromkeys(payload.source_ids))
    if len(source_ids) > MAX_SELECTED_SOURCES:
        raise HTTPException(status_code=422, detail="Máximo de 8 fontes por pesquisa.")
    sources = []
    for item_id in source_ids:
        if not re.fullmatch(r"[0-9a-f]{32}", item_id):
            raise HTTPException(status_code=422, detail="Identificador de fonte inválido.")
        snap = db.collection("library_items").document(item_id).get()
        if not snap.exists:
            raise HTTPException(status_code=404, detail="Fonte não encontrada.")
        record = snap.to_dict()
        if record.get("owner_uid") != owner_uid or record.get("status") != "active":
            raise HTTPException(status_code=404, detail="Fonte indisponível para esta conta.")
        if not str(record.get("object_path", "")).startswith(f"library/{owner_uid}/{item_id}/"):
            raise HTTPException(status_code=422, detail="Caminho da fonte inválido.")
        sources.append({k: record.get(k) for k in (
            "id", "name", "format", "sha256", "size", "object_path"
        )})
    job_id = uuid.uuid4().hex
    prefix = f"research/{owner_uid}/{job_id}"
    ref = db.collection("research_jobs").document(job_id)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": job_id, "owner_uid": owner_uid,
        "title": payload.title, "status": "queued", "stage": "Preparando materiais",
        "template": payload.template, "model": payload.model,
        "ai_auth_mode": "admin_vertex" if access["admin"] else "user_gemini",
        "reflection_model": payload.reflection_model or payload.model,
        "plotting": payload.plotting,
        "language": payload.language,
        "neon_review_requested": payload.neon_review,
        "neon_review_status": "pending" if payload.neon_review else "disabled",
        "sources": sources,
        "audit_status": "pending",
        "reference_status": "pending",
        # Etapas efetivas serão atualizadas pelo worker por evidências no disco.
        "agents": {
            "outline": "waiting", "literature": "waiting",
            "plotting": "waiting" if payload.plotting else "disabled",
            "writing": "waiting", "refinement": "waiting",
        },
        # A produção do manuscrito não significa validação dos dados científicos.
        "scientific_verification": "manual_required",
        "created_at": now, "finished_at": "", "files": [], "error": "",
    }
    ref.set(record)
    try:
        for name, content in (("idea_sparse.md", payload.idea), ("experimental_log.md", payload.experimental_log)):
            blob = bucket.blob(f"{prefix}/input/{name}")
            blob.upload_from_string(content, content_type="text/markdown; charset=utf-8")
        run_client.run_job(request=run_v2.RunJobRequest(
            name=JOB_NAME,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[run_v2.EnvVar(name="RESEARCH_ID", value=job_id),
                         run_v2.EnvVar(name="RESEARCH_OWNER_UID", value=owner_uid)],
                )],
            ),
        ))
        # A operação é assíncrona: não aguardar o término da redação na requisição HTTP.
        # O worker fará as atualizações de progresso diretamente no Firestore.
        ref.update({"stage": "Execução solicitada"})
    except Exception:
        ref.update({"status": "failed", "error": "Falha ao iniciar o processo na nuvem", "finished_at": datetime.now(timezone.utc).isoformat()})
        raise HTTPException(status_code=503, detail="Não foi possível iniciar. Verifique as permissões do Cloud Run Job.") from None
    return {"id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def get_status(job_id: str, user: User):
    return serializable(get_research(job_id, user))


@app.get("/api/jobs/{job_id}/download/{file_kind}")
def download(job_id: str, file_kind: Literal["pdf", "latex", "log", "audit", "references", "neon"], user: User):
    item = get_research(job_id, user)
    if item["status"] != "completed" and not (file_kind == "log" and item["status"] == "failed"):
        raise HTTPException(status_code=409, detail="Pesquisa ainda não concluída")
    filemap = {"pdf": ("final_paper.pdf", "application/pdf"),
               "latex": ("latex_source.zip", "application/zip"),
               "log": ("execution.log", "text/plain; charset=utf-8"),
               "audit": ("scientific_audit.json", "application/json"),
               "references": ("reference_verification.json", "application/json"),
               "neon": ("neon_critical_review.json", "application/json")}
    filename, content_type = filemap[file_kind]
    blob_path = f"research/{user['uid']}/{job_id}/output/{filename}"
    blob = bucket.blob(blob_path)
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Arquivo indisponível para esta pesquisa")
    return Response(
        content=blob.download_as_bytes(), media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
