"""Backend autenticado do PaperOrchestra Cloud.

As chaves Gemini ficam somente no Cloud Run Job (Secret Manager); não entram aqui.
"""
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal
from library import make_library_router, MAX_SELECTED_SOURCES
from access import Invitation, get_access, is_admin, set_invitation
from credentials import GeminiCredential, store_credential, delete_credential
from model_access import (FLASH_MODEL, PRO_MODEL, account_model_access,
                          allowed_models, validate_key_and_models)
from access_requests import (request_access, pending_access_requests,
                             approve_access_request)
from job_state import ACTIVE_STATUSES, claim_active_slot, reconcile

import firebase_admin
from firebase_admin import auth
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from google.cloud import firestore, storage, run_v2
from pydantic import BaseModel, Field, field_validator

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
REGION = os.getenv("REGION", "southamerica-east1")
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


def identified_user(authorization: Annotated[str | None, Header()] = None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Entre com sua conta Google")
    try:
        token = auth.verify_id_token(authorization[7:], check_revoked=True)
    except Exception:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada") from None
    return token


def current_user(identity: Annotated[dict, Depends(identified_user)]):
    if not (is_admin(identity, ALLOWED_EMAILS) or
            (BYOK_ENABLED and get_access(db, identity, ALLOWED_EMAILS)["allowed"])):
        raise HTTPException(status_code=403, detail="Conta não autorizada")
    return identity


User = Annotated[dict, Depends(current_user)]
IdentifiedUser = Annotated[dict, Depends(identified_user)]

# Biblioteca própria privada, separada das pesquisas já concluídas.
app.include_router(make_library_router(db, bucket, current_user))


def get_research(job_id: str, user: dict) -> dict:
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(status_code=404, detail="Pesquisa não encontrada")
    ref = db.collection("research_jobs").document(job_id)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("owner_uid") != user["uid"]:
        raise HTTPException(status_code=404, detail="Pesquisa não encontrada")
    # Job interrompido sem atualizar o Firestore não fica "running" para sempre.
    return reconcile(ref, snap.to_dict())


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
        "editorial_alerts": record.get("editorial_alerts"),
        "evidence_status": record.get("evidence_status", "not_available"),
        "evidence_summary": record.get("evidence_summary"),
        "audit_findings": record.get("audit_findings"),
        "error": record.get("error", ""),
        "created_at": record.get("created_at", ""),
        "finished_at": record.get("finished_at", ""),
        "files": record.get("files", []),
        "sources": [{k: entry.get(k) for k in ("id", "name", "format", "sha256")} for entry in record.get("sources", [])],
    }


@app.get("/api/health")
def health():
    # Identificador público e não secreto para auditoria do rollout da API.
    # Permite saber se o Firebase está roteando para a revisão certa.
    return {"ok": True, "version": "multiuser-v2",
            "release_sha": os.getenv("SCRIPTORIUM_RELEASE_SHA", "")}

@app.get("/api/capabilities")
def capabilities(user: User):
    return {"neon_review": NEON_REVIEW_ENABLED and is_admin(user, ALLOWED_EMAILS),
            "neon_model": "gemini-4-neon"}



@app.get("/api/account/access")
def account_access(user: User):
    access = get_access(db, user, ALLOWED_EMAILS)
    models = ({"status": "admin_vertex", "verified_models": [FLASH_MODEL, PRO_MODEL]}
              if access["admin"] else account_model_access(db, user["uid"]))
    available = [FLASH_MODEL, PRO_MODEL] if access["admin"] else allowed_models(models)
    return {"admin": access["admin"], "byok_ready": BYOK_ENABLED and access["byok_ready"],
            "multiuser_enabled": BYOK_ENABLED,
            "research_generation_enabled": access["admin"] or
                (BYOK_ENABLED and access["byok_ready"] and bool(available)),
            "allowed_models": available,
            "model_access": models}


@app.post("/api/account/request-access", status_code=202)
def submit_access_request(identity: IdentifiedUser):
    if is_admin(identity, ALLOWED_EMAILS):
        raise HTTPException(status_code=409, detail="Conta administradora já autorizada.")
    if BYOK_ENABLED and get_access(db, identity, ALLOWED_EMAILS)["allowed"]:
        raise HTTPException(status_code=409, detail="Sua conta já está autorizada.")
    return request_access(db, identity)


@app.get("/api/admin/access-requests")
def get_access_requests(user: User):
    if not is_admin(user, ALLOWED_EMAILS):
        raise HTTPException(status_code=403, detail="Somente administradores.")
    return pending_access_requests(db)


@app.post("/api/admin/access-requests/{request_id}/approve")
def approve_access(request_id: str, user: User):
    if not BYOK_ENABLED:
        raise HTTPException(status_code=503, detail="Convites indisponíveis.")
    if not is_admin(user, ALLOWED_EMAILS):
        raise HTTPException(status_code=403, detail="Somente administradores.")
    return approve_access_request(db, request_id, user["uid"], ALLOWED_EMAILS)


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
    # Verificar acesso real ANTES de ativar uma nova chave. O Google pode cobrar
    # um consumo mínimo nas duas chamadas de teste (informado no primeiro acesso).
    try:
        model_access = validate_key_and_models(key)
    except ValueError:
        raise HTTPException(status_code=422, detail="O Google recusou esta chave. Copie-a novamente no AI Studio.") from None
    except ConnectionError:
        raise HTTPException(status_code=503, detail="O Google não respondeu à verificação. Tente novamente.") from None
    try:
        saved = store_credential(db, PROJECT, user["uid"], key,
                                  model_access=model_access)
        return {**saved, "model_access": model_access}
    except Exception:
        raise HTTPException(status_code=503, detail="Não foi possível guardar a credencial de IA.") from None


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
    return set_invitation(db, payload.email, True, user["uid"], ALLOWED_EMAILS)


@app.delete("/api/admin/invitations/{email}")
def revoke_researcher(email: str, user: User):
    if not BYOK_ENABLED:
        raise HTTPException(status_code=503, detail="Convites indisponíveis até aprovação da infraestrutura.")
    if not is_admin(user, ALLOWED_EMAILS):
        raise HTTPException(status_code=403, detail="Apenas administradores podem revogar.")
    try:
        return set_invitation(db, email, False, user["uid"], ALLOWED_EMAILS)
    except ValueError:
        raise HTTPException(status_code=422, detail="E-mail inválido.") from None


@app.get("/api/jobs")
def list_researches(user: User):
    # Consulta simples, sem índices compostos. Ordenação em memória para acervo pessoal.
    docs = db.collection("research_jobs").where("owner_uid", "==", user["uid"]).limit(200).stream()
    items = [serializable(reconcile(s.reference, s.to_dict())) for s in docs]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"items": items}


@app.post("/api/jobs", status_code=202)
def create_research(payload: NewResearch, user: User):
    owner_uid = user["uid"]
    access = get_access(db, user, ALLOWED_EMAILS)
    if not (access["admin"] or (BYOK_ENABLED and access["byok_ready"])):
        # Bloqueia antes de armazenar materiais ou iniciar Cloud Run.
        raise HTTPException(status_code=409, detail="Configure sua chave Gemini antes de iniciar uma pesquisa.")
    # Permissões efetivas no backend: não confiar em opções ocultas no navegador.
    if not access["admin"]:
        access_models = allowed_models(account_model_access(db, owner_uid))
        if payload.model not in access_models or (
            payload.reflection_model and payload.reflection_model not in access_models
        ):
            raise HTTPException(status_code=403, detail="Modelo indisponível para sua chave Gemini. Atualize a chave no painel de acesso.")
        # O agente de gráficos chama um modelo de imagem distinto do Pro
        # textual; só liberar após teste próprio desse modelo, ainda pendente.
        if payload.plotting:
            raise HTTPException(status_code=403, detail="Gráficos com IA ainda não estão habilitados para esta chave.")
    if payload.neon_review and not access["admin"]:
        raise HTTPException(status_code=403, detail="A revisão Neon não está habilitada para esta conta.")
    if payload.neon_review and not NEON_REVIEW_ENABLED:
        raise HTTPException(status_code=409, detail="Revisão Neon indisponível até validar o acesso do worker.")
    # Proteção de custos: uma geração por vez por conta. Esta varredura cobre
    # pesquisas criadas antes da trava transacional e reconcilia as travadas;
    # a garantia contra requisições simultâneas está em claim_active_slot.
    busy_detail = "Há uma pesquisa em execução. Finalize-a antes de iniciar outra."
    docs = db.collection("research_jobs").where("owner_uid", "==", owner_uid).limit(200).stream()
    for s in docs:
        if reconcile(s.reference, s.to_dict()).get("status") in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail=busy_detail)
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
    if not claim_active_slot(db, owner_uid, job_id, record):
        raise HTTPException(status_code=409, detail=busy_detail)
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
def download(job_id: str, file_kind: Literal["pdf", "latex", "log", "audit", "references", "neon",
                                             "manifest", "declaration", "evidence", "evidence_csv"],
             user: User):
    if file_kind == "neon" and not (NEON_REVIEW_ENABLED and is_admin(user, ALLOWED_EMAILS)):
        raise HTTPException(status_code=403, detail="Parecer Neon não está disponível nesta conta.")
    item = get_research(job_id, user)
    # Em falhas, log e manifesto mostram até onde a execução chegou.
    if item["status"] != "completed" and not (file_kind in ("log", "manifest") and item["status"] == "failed"):
        raise HTTPException(status_code=409, detail="Pesquisa ainda não concluída")
    filemap = {"pdf": ("final_paper.pdf", "application/pdf"),
               "latex": ("latex_source.zip", "application/zip"),
               "log": ("execution.log", "text/plain; charset=utf-8"),
               "audit": ("scientific_audit.json", "application/json"),
               "references": ("reference_verification.json", "application/json"),
               "neon": ("neon_critical_review.json", "application/json"),
               # M14: proveniência; M11: rascunho de declaração de uso de IA.
               "manifest": ("run_manifest.json", "application/json"),
               "declaration": ("declaracao_uso_ia.md", "text/markdown; charset=utf-8"),
               # M05 + M08/M10: citações literais e matriz de evidências.
               "evidence": ("evidence_report.json", "application/json"),
               "evidence_csv": ("evidence_matrix.csv", "text/csv; charset=utf-8")}
    filename, content_type = filemap[file_kind]
    blob_path = f"research/{user['uid']}/{job_id}/output/{filename}"
    blob = bucket.blob(blob_path)
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Arquivo indisponível para esta pesquisa")
    return Response(
        content=blob.download_as_bytes(), media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
