"""Backend autenticado do PaperOrchestra Cloud.

As chaves Gemini ficam somente no Cloud Run Job (Secret Manager); não entram aqui.
"""
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

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
    template: Literal["cvpr2025", "iclr2025"] = "iclr2025"
    model: Literal["gemini-3.1-pro-preview", "gemini-3-flash-preview"] = "gemini-3-flash-preview"
    # Permite avaliar um manuscrito com modelo diferente do usado na redação.
    reflection_model: Literal["gemini-3.1-pro-preview", "gemini-3-flash-preview"] | None = None
    plotting: bool = False
    # Idioma do manuscrito solicitado, sem alterar o template LaTeX.
    language: Literal["en", "pt-BR"] = "en"

    @field_validator("idea", "experimental_log")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("O material não pode estar vazio")
        return value


def current_user(authorization: Annotated[str | None, Header()] = None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Entre com sua conta Google")
    try:
        token = auth.verify_id_token(authorization[7:], check_revoked=True)
    except Exception:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada") from None
    email = (token.get("email") or "").lower()
    if not token.get("email_verified") or email not in ALLOWED_EMAILS:
        raise HTTPException(status_code=403, detail="Conta não autorizada")
    return token


User = Annotated[dict, Depends(current_user)]


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
        "audit_findings": record.get("audit_findings"),
        "error": record.get("error", ""),
        "created_at": record.get("created_at", ""),
        "finished_at": record.get("finished_at", ""),
        "files": record.get("files", []),
    }


@app.get("/api/health")
def health():
    return {"ok": True, "version": "v1"}


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
    # Proteção de custos: uma geração por vez por conta.
    docs = db.collection("research_jobs").where("owner_uid", "==", owner_uid).limit(200).stream()
    for s in docs:
        if s.to_dict().get("status") in ("queued", "running"):
            raise HTTPException(status_code=409, detail="Há uma pesquisa em execução. Finalize-a antes de iniciar outra.")
    job_id = uuid.uuid4().hex
    prefix = f"research/{owner_uid}/{job_id}"
    ref = db.collection("research_jobs").document(job_id)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": job_id, "owner_uid": owner_uid,
        "title": payload.title, "status": "queued", "stage": "Preparando materiais",
        "template": payload.template, "model": payload.model,
        "reflection_model": payload.reflection_model or payload.model,
        "plotting": payload.plotting,
        "language": payload.language,
        "audit_status": "pending",
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
def download(job_id: str, file_kind: Literal["pdf", "latex", "log", "audit"], user: User):
    item = get_research(job_id, user)
    if item["status"] != "completed" and not (file_kind == "log" and item["status"] == "failed"):
        raise HTTPException(status_code=409, detail="Pesquisa ainda não concluída")
    filemap = {"pdf": ("final_paper.pdf", "application/pdf"),
               "latex": ("latex_source.zip", "application/zip"),
               "log": ("execution.log", "text/plain; charset=utf-8"),
               "audit": ("scientific_audit.json", "application/json")}
    filename, content_type = filemap[file_kind]
    blob_path = f"research/{user['uid']}/{job_id}/output/{filename}"
    blob = bucket.blob(blob_path)
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Arquivo indisponível para esta pesquisa")
    return Response(
        content=blob.download_as_bytes(), media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
