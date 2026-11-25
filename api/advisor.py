"""Autorização do orientador e política de dados por pesquisa (M11, IN IFRS 16/2026).

Origem: R25 (IFRS, Instrução Normativa nº 16/2026, texto conferido em
24/11/2026 a partir do PDF assinado em 26/05/2026) e R47 (Termos adicionais da
Gemini API, uso dos dados no nível gratuito).

O que a IN exige e como o Scriptorium registra:
- Art. 6º, caput, e Art. 8º: os usos permitidos dependem de autorização do
  docente ou orientador, formalmente registrada. O pesquisador registra aqui
  quem autorizou, quando, de que forma (e-mail, ata, SIGAA...) e para quais
  incisos do Art. 6º. É um registro do pesquisador, somente acréscimo; o
  documento oficial continua sendo o do orientador;
- Art. 9º: dados sensíveis, inéditos ou sigilosos não podem ir para IA externa
  cuja política não garanta que não serão usados para treinar modelos. Nos
  termos da Gemini API (R47), o uso SEM faturamento ativo (nível gratuito) pode
  ser usado pelo Google para melhorar produtos; com faturamento ativo no
  projeto da chave, não. Por isso, pesquisa com dados inéditos só começa se o
  pesquisador confirmar faturamento ativo e dados sem identificação pessoal.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

COLLECTION = "advisor_authorizations"
MAX_HISTORY = 50
# Art. 6º da IN 16/2026 (o inciso IX aparece como "XIX" no texto publicado).
ART6 = {
    "I": "Exploração inicial de ideias, brainstorming, hipóteses e problemáticas",
    "II": "Busca e organização de materiais bibliográficos (fontes verificadas individualmente)",
    "III": "Resumo e leitura assistida de artigos científicos",
    "IV": "Revisão gramatical, ortográfica e estilística",
    "V": "Tradução de textos acadêmicos com revisão crítica humana",
    "VI": "Transcrição de áudios e vídeos",
    "VII": "Visualizações, tabelas, gráficos e infográficos com dados da pessoa",
    "VIII": "Exploração de perspectivas, argumentos e contrapontos",
    "IX": "Apoio à análise de dados qualitativos",
    "X": "Elaboração parcial de seções textuais com revisão crítica integral",
    "XI": "Pré-avaliação de manuscritos (formato, plágio, linguagem)",
    "XII": "Agentes de IAGen para tarefas múltiplas encadeadas (documentação completa)",
    "XIII": "Geração e correção de código",
}
FORMS = ("e-mail", "ata ou registro de reunião", "SIGAA ou sistema institucional",
         "documento assinado", "plano de trabalho ou projeto aprovado", "outro")


class AdvisorAuthorization(BaseModel):
    advisor_name: str = Field(min_length=3, max_length=120)
    authorized_on: date
    record_form: Literal[FORMS]  # type: ignore[valid-type]
    record_reference: str = Field(default="", max_length=200)
    scope: list[str] = Field(min_length=1, max_length=len(ART6))
    notes: str = Field(default="", max_length=600)

    @field_validator("scope")
    @classmethod
    def known_items(cls, value: list[str]) -> list[str]:
        unknown = [v for v in value if v not in ART6]
        if unknown:
            raise ValueError("Inciso do Art. 6º desconhecido: " + ", ".join(unknown))
        return sorted(set(value), key=list(ART6).index)

    @field_validator("authorized_on")
    @classmethod
    def not_future(cls, value: date) -> date:
        if value > datetime.now(timezone.utc).date():
            raise ValueError("A data da autorização não pode estar no futuro.")
        return value


def latest_authorization(db, owner_uid: str) -> dict | None:
    docs = [s.to_dict() for s in db.collection(COLLECTION).where("owner_uid", "==", owner_uid)
            .limit(MAX_HISTORY).stream()]
    docs.sort(key=lambda d: d.get("recorded_at", ""))
    return docs[-1] if docs else None


def snapshot(authorization: dict | None) -> dict | None:
    """O que vai para a pesquisa, o manifesto e a declaração."""
    if not authorization:
        return None
    return {k: authorization.get(k) for k in ("id", "advisor_name", "authorized_on", "record_form",
                                              "record_reference", "scope", "notes", "recorded_at")}


def data_policy(unpublished_data: bool, paid_tier_confirmed: bool, deidentified_confirmed: bool,
                project_ai: bool) -> dict:
    """Art. 9º: bloqueia dados inéditos em chave que pode alimentar treinamento."""
    if unpublished_data and not project_ai:
        if not paid_tier_confirmed:
            raise HTTPException(422, "IN IFRS 16/2026, Art. 9º: com dados inéditos ou sensíveis, use uma chave "
                                     "Gemini de projeto com faturamento ativo (no nível gratuito o Google pode usar "
                                     "o conteúdo para melhorar produtos) e confirme isso no formulário.")
        if not deidentified_confirmed:
            raise HTTPException(422, "IN IFRS 16/2026, Art. 9º e LGPD: confirme que os dados não identificam "
                                     "participantes antes de enviar dados inéditos.")
    return {
        "unpublished_data": unpublished_data,
        "paid_tier_confirmed": bool(paid_tier_confirmed) if not project_ai else None,
        "deidentified_confirmed": bool(deidentified_confirmed),
        "provider_training_policy": ("Vertex AI no projeto Scriptorium (dados de cliente não usados para treino)"
                                     if project_ai else
                                     "Gemini API com chave pessoal: sem faturamento ativo, o Google pode usar o conteúdo "
                                     "para melhorar produtos; com faturamento ativo, não (termos adicionais da Gemini API, R47)"),
        "in16_reference": "Art. 9º e Art. 10",
    }


def addendum(authorization: dict) -> str:
    """Adendo à declaração já gerada, quando a autorização foi registrada depois."""
    scope = "; ".join(f"{k} ({ART6[k]})" for k in authorization.get("scope") or [] if k in ART6)
    return "\n".join([
        "", "## Adendo: autorização do orientador registrada depois da geração", "",
        f"- **Orientador(a):** {authorization.get('advisor_name')}",
        f"- **Data da autorização:** {authorization.get('authorized_on')}",
        f"- **Forma do registro (Art. 8º):** {authorization.get('record_form')}"
        + (f", {authorization['record_reference']}" if authorization.get("record_reference") else ""),
        f"- **Usos autorizados (Art. 6º):** {scope}",
        f"- **Registrado no Scriptorium em:** {str(authorization.get('recorded_at', ''))[:10]}",
        "",
    ])


def make_advisor_router(db, verify_user: Callable):
    router = APIRouter(prefix="/api/account/advisor-authorization", tags=["IN 16/2026"])
    dependency = Depends(verify_user)

    @router.get("")
    def get_authorization(user: dict = dependency):
        docs = [s.to_dict() for s in db.collection(COLLECTION).where("owner_uid", "==", user["uid"])
                .limit(MAX_HISTORY).stream()]
        docs.sort(key=lambda d: d.get("recorded_at", ""))
        return {"latest": snapshot(docs[-1]) if docs else None,
                "history": [snapshot(d) for d in docs], "art6": ART6, "forms": list(FORMS)}

    @router.post("", status_code=201)
    def record_authorization(payload: AdvisorAuthorization, user: dict = dependency):
        existing = list(db.collection(COLLECTION).where("owner_uid", "==", user["uid"]).limit(MAX_HISTORY).stream())
        if len(existing) >= MAX_HISTORY:
            raise HTTPException(409, "Limite de registros de autorização atingido.")
        record = {
            "id": uuid.uuid4().hex, "owner_uid": user["uid"],
            "advisor_name": re.sub(r"\s+", " ", payload.advisor_name).strip(),
            "authorized_on": payload.authorized_on.isoformat(),
            "record_form": payload.record_form, "record_reference": payload.record_reference.strip(),
            "scope": payload.scope, "notes": payload.notes.strip(),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        # Somente acréscimo: uma nova autorização não apaga a anterior.
        db.collection(COLLECTION).document(record["id"]).create(record)
        return snapshot(record)

    return router
