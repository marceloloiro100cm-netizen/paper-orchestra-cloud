"""Backend autenticado do PaperOrchestra Cloud.

As chaves Gemini ficam somente no Cloud Run Job (Secret Manager); não entram aqui.
"""
import json
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
from job_state import (ACTIVE_STATUSES, StateConflict, claim_active_slot, reconcile,
                       transition)
from zotero_import import make_zotero_router
from reviews import ReviewIn, add_review, list_reviews, reference_fingerprint
from research_tools import make_research_tools_router
from library_index import make_library_index_router
from advisor import (WORK_TYPES, academic_profile, addendum, data_policy, latest_authorization,
                     make_advisor_router, snapshot as authorization_snapshot)
from reading_notes_api import make_reading_notes_router
from oa_import import make_oa_import_router

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
# Separação de custos: infraestrutura no projeto do Scriptorium; tokens de IA
# sempre na chave Gemini pessoal de quem gera, inclusive o administrador.
# Só com esta variável em "true" o administrador volta a usar o Vertex do projeto.
PROJECT_AI = os.getenv("SCRIPTORIUM_ALLOW_PROJECT_AI", "false").lower() == "true"


def uses_project_ai(access: dict) -> bool:
    return bool(access.get("admin")) and PROJECT_AI

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
    # M16 + M12: diagnosticar as fontes e esperar aprovação antes de gerar.
    preflight: bool = False
    # M11, IN IFRS 16/2026, Art. 9º: o pesquisador declara se há dados inéditos.
    unpublished_data: bool
    # Anexo I, seção 2: natureza do trabalho acadêmico.
    work_type: Literal[WORK_TYPES] = "artigo científico"  # type: ignore[valid-type]
    paid_tier_confirmed: bool = False
    deidentified_confirmed: bool = False

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
# M26: importação somente leitura do Zotero (a chave nunca é guardada).
app.include_router(make_zotero_router(db, bucket, current_user))
# PDFs de acesso aberto por DOI ou link (OpenAlex, R09), com proteção contra SSRF.
app.include_router(make_oa_import_router(db, bucket, current_user))

AWAITING_SOURCES = "awaiting_source_approval"


class CheckpointDecision(BaseModel):
    decision: Literal["approve", "discard"]
    # Subconjunto das fontes do diagnóstico que seguem para a geração.
    source_ids: list[str] | None = Field(default=None, max_length=MAX_SELECTED_SOURCES)


def start_job(job_id: str, owner_uid: str, mode: str) -> None:
    run_client.run_job(request=run_v2.RunJobRequest(
        name=JOB_NAME,
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[run_v2.RunJobRequest.Overrides.ContainerOverride(
                env=[run_v2.EnvVar(name="RESEARCH_ID", value=job_id),
                     run_v2.EnvVar(name="RESEARCH_OWNER_UID", value=owner_uid),
                     run_v2.EnvVar(name="RESEARCH_MODE", value=mode)],
            )],
        ),
    ))


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
        "mode": record.get("mode", "generate"),
        "ai_billing": "projeto" if record.get("ai_auth_mode", "admin_vertex") == "admin_vertex" else "chave_pessoal",
        "checkpoint": record.get("checkpoint"),
        "approvals": record.get("approvals", []),
        "gap_summary": record.get("gap_summary"),
        "references_checked": record.get("references_checked"),
        "references_skipped": record.get("references_skipped"),
        "editorial_alerts": record.get("editorial_alerts"),
        "evidence_status": record.get("evidence_status", "not_available"),
        "evidence_summary": record.get("evidence_summary"),
        "shield_counts": record.get("shield_counts"),
        "audit_findings": record.get("audit_findings"),
        "error": record.get("error", ""),
        # M15: cancelamento pedido; M07: reavaliação editorial.
        "cancel_requested": bool(record.get("cancel_requested")),
        "editorial_recheck": record.get("editorial_recheck"),
        "created_at": record.get("created_at", ""),
        "finished_at": record.get("finished_at", ""),
        "files": record.get("files", []),
        "sources": [{k: entry.get(k) for k in ("id", "name", "format", "sha256")} for entry in record.get("sources", [])],
    }


# Onda 6 do plano V2: cancelamento (M15), reavaliação editorial (M07), página do
# PDF com o trecho (M02), matriz revisada (M08) e exportação CSL/ABNT (M27).
app.include_router(make_research_tools_router(db, bucket, current_user, get_research, start_job))
# M03/M21: busca na biblioteca inteira e ficha de leitura por documento.
app.include_router(make_library_index_router(db, bucket, current_user))
# M11 (IN IFRS 16/2026): autorização do orientador registrada pelo pesquisador.
app.include_router(make_advisor_router(db, current_user))


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
    project_ai = uses_project_ai(access)
    models = ({"status": "admin_vertex", "verified_models": [FLASH_MODEL, PRO_MODEL]}
              if project_ai else account_model_access(db, user["uid"]))
    available = [FLASH_MODEL, PRO_MODEL] if project_ai else allowed_models(models)
    return {"admin": access["admin"], "byok_ready": BYOK_ENABLED and access["byok_ready"],
            "multiuser_enabled": BYOK_ENABLED,
            "research_generation_enabled": project_ai or
                (BYOK_ENABLED and access["byok_ready"] and bool(available)),
            "allowed_models": available,
            "model_access": models,
            # Quem paga cada parte, para a interface mostrar com clareza.
            "billing": {"infrastructure": "projeto Scriptorium (administrador)",
                        "ai_tokens": "projeto Scriptorium (Vertex)" if project_ai
                                     else "chave Gemini pessoal de quem gera a pesquisa"}}


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
    items = [serializable(reconcile(s.reference, s.to_dict())) for s in docs
             if (s.to_dict() or {}).get("mode") != "reading_notes"]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"items": items}


@app.post("/api/jobs", status_code=202)
def create_research(payload: NewResearch, user: User):
    owner_uid = user["uid"]
    access = get_access(db, user, ALLOWED_EMAILS)
    project_ai = uses_project_ai(access)
    if not (project_ai or (BYOK_ENABLED and access["byok_ready"])):
        # Bloqueia antes de armazenar materiais ou iniciar Cloud Run.
        raise HTTPException(status_code=409, detail="Configure sua chave Gemini antes de iniciar uma pesquisa.")
    # Permissões efetivas no backend: não confiar em opções ocultas no navegador.
    if not project_ai:
        access_models = allowed_models(account_model_access(db, owner_uid))
        if payload.model not in access_models or (
            payload.reflection_model and payload.reflection_model not in access_models
        ):
            raise HTTPException(status_code=403, detail="Modelo indisponível para sua chave Gemini. Atualize a chave no painel de acesso.")
        # O agente de gráficos chama um modelo de imagem distinto do Pro
        # textual; só liberar após teste próprio desse modelo, ainda pendente.
        if payload.plotting:
            raise HTTPException(status_code=403, detail="Gráficos com IA ainda não estão habilitados para esta chave.")
    # Art. 9º da IN 16/2026: dados inéditos só com chave que não alimenta treinamento.
    policy = data_policy(payload.unpublished_data, payload.paid_tier_confirmed,
                         payload.deidentified_confirmed, project_ai)
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
        current = reconcile(s.reference, s.to_dict())
        # Fichamentos (M21) rodam à parte e não bloqueiam uma pesquisa.
        if current.get("mode") != "reading_notes" and current.get("status") in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail=busy_detail)
    # Validar propriedade antes de iniciar tarefas caras ou armazenar a solicitação.
    source_ids = list(dict.fromkeys(payload.source_ids))
    if payload.preflight and not source_ids:
        raise HTTPException(status_code=422, detail="Selecione ao menos uma fonte para o diagnóstico.")
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
        "title": payload.title, "status": "queued",
        "stage": "Diagnóstico das fontes na fila" if payload.preflight else "Preparando materiais",
        "mode": "preflight" if payload.preflight else "generate",
        "approvals": [],
        "template": payload.template, "model": payload.model,
        # Tokens sempre na chave pessoal, salvo exceção explícita (PROJECT_AI).
        "ai_auth_mode": "admin_vertex" if project_ai else "user_gemini",
        "reflection_model": payload.reflection_model or payload.model,
        "plotting": payload.plotting,
        "language": payload.language,
        "neon_review_requested": payload.neon_review,
        "neon_review_status": "pending" if payload.neon_review else "disabled",
        "sources": sources,
        # M11: política de dados (Art. 9º) e autorização do orientador (Art. 6º e 8º)
        # vigentes no momento da criação; vão para o manifesto e a declaração.
        "data_policy": policy,
        "advisor_authorization": authorization_snapshot(latest_authorization(db, owner_uid)),
        # Anexo I, seções 1 e 2: identificação do(a) autor(a) e natureza do trabalho.
        "academic_profile": academic_profile(db, owner_uid),
        "work_type": payload.work_type,
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
        start_job(job_id, owner_uid, record["mode"])
        # A operação é assíncrona: não aguardar o término da redação na requisição HTTP.
        # O worker fará as atualizações de progresso diretamente no Firestore.
        ref.update({"stage": "Execução solicitada"})
    except Exception:
        ref.update({"status": "failed", "error": "Falha ao iniciar o processo na nuvem", "finished_at": datetime.now(timezone.utc).isoformat()})
        raise HTTPException(status_code=503, detail="Não foi possível iniciar. Verifique as permissões do Cloud Run Job.") from None
    return {"id": job_id, "status": "queued"}


@app.post("/api/jobs/{job_id}/checkpoint")
def decide_checkpoint(job_id: str, payload: CheckpointDecision, user: User):
    """M12: o pesquisador aprova (ou descarta) as fontes depois do diagnóstico (M16)."""
    record = get_research(job_id, user)
    if record.get("status") != AWAITING_SOURCES:
        raise HTTPException(status_code=409, detail="Esta pesquisa não está aguardando aprovação.")
    now = datetime.now(timezone.utc).isoformat()
    event = {"checkpoint": "source_approval", "decision": payload.decision,
             "by_uid": user["uid"], "at": now}
    if payload.decision == "discard":
        try:
            transition(db, job_id, AWAITING_SOURCES, {
                "status": "discarded", "stage": "Descartada pelo pesquisador", "finished_at": now,
                "checkpoint": None, "approvals": [*record.get("approvals", []), event]})
        except StateConflict:
            raise HTTPException(status_code=409, detail="A decisão já foi registrada.") from None
        return {"id": job_id, "status": "discarded"}
    sources = record.get("sources", [])
    if payload.source_ids is not None:
        wanted = set(payload.source_ids)
        if not wanted or not wanted <= {s.get("id") for s in sources}:
            raise HTTPException(status_code=422, detail="Escolha ao menos uma das fontes do diagnóstico.")
        sources = [s for s in sources if s.get("id") in wanted]
    event["sources_kept"] = [s.get("id") for s in sources]
    if not access_allows_generation(user, record):
        raise HTTPException(status_code=403, detail="Sua chave Gemini não está mais disponível para gerar.")
    updated = {**record, "status": "queued", "mode": "generate", "sources": sources,
               "stage": "Fontes aprovadas; preparando a geração", "checkpoint": None,
               "approvals": [*record.get("approvals", []), event], "finished_at": "", "error": ""}
    try:
        if not claim_active_slot(db, user["uid"], job_id, updated, expected_status=AWAITING_SOURCES):
            raise HTTPException(status_code=409, detail="Há uma pesquisa em execução. Finalize-a antes de aprovar esta.")
    except StateConflict:
        raise HTTPException(status_code=409, detail="A decisão já foi registrada.") from None
    try:
        start_job(job_id, user["uid"], "generate")
    except Exception:
        db.collection("research_jobs").document(job_id).update({
            "status": "failed", "error": "Falha ao iniciar o processo na nuvem",
            "finished_at": datetime.now(timezone.utc).isoformat()})
        raise HTTPException(status_code=503, detail="Não foi possível iniciar. Verifique as permissões do Cloud Run Job.") from None
    return {"id": job_id, "status": "queued", "sources_kept": event["sources_kept"]}


def get_access_for_notes(user: dict) -> dict:
    """M21: quem pode gerar fichamento por IA e com qual identidade de IA."""
    access = get_access(db, user, ALLOWED_EMAILS)
    project_ai = uses_project_ai(access)
    if project_ai:
        return {"ai_auth_mode": "admin_vertex", "models": [FLASH_MODEL, PRO_MODEL]}
    if not (BYOK_ENABLED and access["byok_ready"]):
        raise HTTPException(status_code=409, detail="Configure sua chave Gemini antes de gerar fichamentos.")
    return {"ai_auth_mode": "user_gemini", "models": allowed_models(account_model_access(db, user["uid"]))}


def access_allows_generation(user: dict, record: dict) -> bool:
    """Revalida o acesso no momento da aprovação (a chave pode ter sido removida)."""
    access = get_access(db, user, ALLOWED_EMAILS)
    if record.get("ai_auth_mode") == "admin_vertex":
        return uses_project_ai(access)
    if not (BYOK_ENABLED and access["byok_ready"]):
        return False
    allowed = allowed_models(account_model_access(db, user["uid"]))
    return record.get("model") in allowed and (record.get("reflection_model") or record.get("model")) in allowed


@app.post("/api/jobs/{job_id}/reviews", status_code=201)
def create_review(job_id: str, payload: ReviewIn, user: User):
    """M08/M12/M24: decisão humana registrada (somente acréscimo)."""
    record = get_research(job_id, user)
    if record.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Revisões só para pesquisas concluídas.")
    extra = None
    if payload.target_type == "reference":
        # M24: guarda DOI e título junto da decisão, para a próxima pesquisa reconhecer a obra.
        try:
            blob = bucket.blob(f"research/{user['uid']}/{job_id}/output/reference_verification.json")
            report = json.loads(blob.download_as_bytes().decode("utf-8"))
            ref = next((i.get("reference") or {} for i in report.get("items", [])
                        if (i.get("reference") or {}).get("key") == payload.target_id), None)
            if ref:
                extra = {"reference_fingerprint": reference_fingerprint(ref)}
        except Exception:
            extra = None
    return add_review(db, job_id, user["uid"], payload, extra)


@app.get("/api/jobs/{job_id}/reviews")
def get_reviews(job_id: str, user: User):
    get_research(job_id, user)
    return list_reviews(db, job_id, user["uid"])


@app.get("/api/jobs/{job_id}")
def get_status(job_id: str, user: User):
    return serializable(get_research(job_id, user))


@app.get("/api/jobs/{job_id}/download/{file_kind}")
def download(job_id: str, file_kind: Literal["pdf", "latex", "log", "audit", "references", "neon",
                                             "manifest", "declaration", "evidence", "evidence_csv",
                                             "shield", "coverage", "gap_report", "contradictions",
                                             "fire"],
             user: User):
    if file_kind == "neon" and not (NEON_REVIEW_ENABLED and is_admin(user, ALLOWED_EMAILS)):
        raise HTTPException(status_code=403, detail="Parecer Neon não está disponível nesta conta.")
    item = get_research(job_id, user)
    # Em falhas, log e manifesto mostram até onde a execução chegou.
    readable_early = (
        (file_kind in ("log", "manifest") and item["status"] == "failed")
        # O diagnóstico (M16) fica legível durante e depois do checkpoint.
        or (file_kind in ("gap_report", "manifest") and item.get("mode") in ("preflight", "generate")
            and "gap_report" in item.get("files", []))
    )
    if item["status"] != "completed" and not readable_early:
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
               "evidence_csv": ("evidence_matrix.csv", "text/csv; charset=utf-8"),
               # M06: escudo de auditoria; M09: cobertura da seleção de trechos.
               "shield": ("audit_shield.json", "application/json"),
               "coverage": ("retrieval_coverage.json", "application/json"),
               # M16: diagnóstico das fontes antes da geração.
               "gap_report": ("gap_report.json", "application/json"),
               # M17 (experimental): possíveis divergências entre fontes.
               "contradictions": ("contradictions.json", "application/json"),
               # M22 (experimental): verificação iterativa das afirmações.
               "fire": ("fire_audit.json", "application/json")}
    filename, content_type = filemap[file_kind]
    blob_path = f"research/{user['uid']}/{job_id}/output/{filename}"
    blob = bucket.blob(blob_path)
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Arquivo indisponível para esta pesquisa")
    content = blob.download_as_bytes()
    if file_kind == "declaration" and not item.get("advisor_authorization"):
        # M11: autorização registrada depois da geração entra como adendo datado.
        current = latest_authorization(db, user["uid"])
        if current:
            content += addendum(current).encode("utf-8")
    return Response(
        content=content, media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )

# M21: fichamento por IA sob demanda, na chave Gemini de quem pede.
app.include_router(make_reading_notes_router(db, bucket, current_user, get_access_for_notes, start_job))
