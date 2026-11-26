"""Onda 4: instrumentação ética do estudo piloto do PTT (MPIE / IFRS Campus Porto Alegre).

- Consentimento informado (TCLE) obrigatório antes de gravar qualquer resposta.
- Pseudonimização por design (SHA-256 com sal do projeto): nunca grava e-mail,
  nome ou UID em texto puro nas respostas nem na exportação CSV.
- Escala SUS (Brooke, 1996) com 10 itens Likert (1..5) + perguntas de autonomia
  + atividade opcional de transferência de aprendizagem (sem IA).
- Direito de retirada de consentimento em 1 clique (DELETE /api/piloto/avaliacao).
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import statistics
from datetime import datetime, timezone
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

PILOT_VERSION = "v1.0-piloto"
COLLECTION = "pilot_responses"

SUS_ITEMS = (
    "Eu gostaria de usar o Scriptorium com frequência nos meus trabalhos acadêmicos.",
    "Achei o Scriptorium desnecessariamente complexo.",
    "Achei o Scriptorium fácil de usar.",
    "Acho que precisaria da ajuda de uma pessoa técnica para conseguir usar o Scriptorium.",
    "Achei que as diferentes funções (Biblioteca, Guia e Seus textos) estão bem integradas.",
    "Achei que há inconsistências demais na interface do Scriptorium.",
    "Imagino que a maioria dos colegas aprenderia a usar o Scriptorium rapidamente.",
    "Achei o Scriptorium muito complicado ou cansativo de usar.",
    "Senti-me confiante ao usar o Scriptorium para organizar minha pesquisa.",
    "Precisei aprender muitas coisas técnicas antes de conseguir começar a usar o Scriptorium.",
)


class TransferTask(BaseModel):
    problema: str = Field(default="", max_length=1500)
    pergunta: str = Field(default="", max_length=1000)
    objetivo_geral: str = Field(default="", max_length=1000)
    como_coletar: str = Field(default="", max_length=1500)


class PilotSubmission(BaseModel):
    tcle_aceito: bool
    vinculo: Literal["graduacao", "mestrado", "doutorado", "docente", "outro"] = "mestrado"
    familiaridade_digital: Literal["iniciante", "intermediaria", "avancada"] = "intermediaria"
    sus: list[int] = Field(min_length=10, max_length=10)
    o_que_ajudou: str = Field(default="", max_length=1500)
    o_que_dificultou: str = Field(default="", max_length=1500)
    percepcao_autoria: str = Field(default="", max_length=1500)
    transferencia: TransferTask = Field(default_factory=TransferTask)


def compute_sus(answers: list[int]) -> float:
    """Cálculo padrão da escala SUS (Brooke, 1996): resultado entre 0 e 100."""
    if len(answers) != 10 or any(not isinstance(v, int) or v < 1 or v > 5 for v in answers):
        raise ValueError("A escala SUS exige exatamente 10 respostas inteiras de 1 a 5.")
    total = 0
    for idx, val in enumerate(answers):
        total += (val - 1) if idx % 2 == 0 else (5 - val)
    return round(total * 2.5, 1)


def sus_band(score: float) -> str:
    if score >= 85:
        return "Excelente"
    if score >= 70:
        return "Boa"
    if score >= 50:
        return "Aceitável (com melhorias)"
    return "Baixa (requer revisão)"


def transfer_completeness(task: TransferTask) -> dict:
    """Indicador estrutural auxiliar (não substitui avaliação qualitativa humana)."""
    filled = {
        "problema": len(task.problema.strip()) >= 20,
        "pergunta": len(task.pergunta.strip()) >= 15,
        "objetivo_geral": len(task.objetivo_geral.strip()) >= 15,
        "como_coletar": len(task.como_coletar.strip()) >= 15,
    }
    return {"blocos_preenchidos": sum(filled.values()), "total_blocos": 4, "detalhe": filled}


def participant_id(uid: str, salt: str = "") -> str:
    """Gera código pseudonimizado estável por conta, sem expor UID nem e-mail."""
    key = f"{salt or os.getenv('PILOT_ANON_SALT', 'scriptorium-mpie-v1')}:{uid}"
    return "P-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12].upper()


def make_pilot_router(db, verify_user: Callable, is_admin_fn: Callable[[dict], bool],
                      salt: str = ""):
    router = APIRouter(tags=["piloto"])
    dep = Depends(verify_user)

    @router.get("/api/piloto/meu-status")
    def my_status(user: dict = dep):
        pid = participant_id(user["uid"], salt)
        snap = db.collection(COLLECTION).document(pid).get()
        if not snap.exists:
            return {"enviado": False, "versao_piloto": PILOT_VERSION, "sus_itens": list(SUS_ITEMS)}
        rec = snap.to_dict() or {}
        return {
            "enviado": True,
            "versao_piloto": rec.get("pilot_version", PILOT_VERSION),
            "sus_score": rec.get("sus_score"),
            "sus_faixa": rec.get("sus_faixa", ""),
            "enviado_em": rec.get("submitted_at", ""),
            "sus_itens": list(SUS_ITEMS),
        }

    @router.post("/api/piloto/avaliacao", status_code=201)
    def submit_evaluation(payload: PilotSubmission, user: dict = dep):
        if not payload.tcle_aceito:
            raise HTTPException(422, "É obrigatório confirmar o Termo de Consentimento (TCLE) antes de enviar.")
        try:
            score = compute_sus(payload.sus)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        pid = participant_id(user["uid"], salt)
        tr = transfer_completeness(payload.transferencia)
        record = {
            "participant_code": pid,
            "pilot_version": PILOT_VERSION,
            "tcle_aceito": True,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "vinculo": payload.vinculo,
            "familiaridade_digital": payload.familiaridade_digital,
            "sus_answers": list(payload.sus),
            "sus_score": score,
            "sus_faixa": sus_band(score),
            "o_que_ajudou": payload.o_que_ajudou.strip(),
            "o_que_dificultou": payload.o_que_dificultou.strip(),
            "percepcao_autoria": payload.percepcao_autoria.strip(),
            "transferencia": payload.transferencia.model_dump(),
            "transferencia_completude": tr["blocos_preenchidos"],
        }
        db.collection(COLLECTION).document(pid).set(record)
        return {
            "salvo": True,
            "codigo_anonimo": pid,
            "versao_piloto": PILOT_VERSION,
            "sus_score": score,
            "sus_faixa": record["sus_faixa"],
            "transferencia_completude": tr["blocos_preenchidos"],
        }

    @router.delete("/api/piloto/avaliacao")
    def withdraw_evaluation(user: dict = dep):
        """Direito de retirada de consentimento (CEP / LGPD): apaga a resposta imediatamente."""
        pid = participant_id(user["uid"], salt)
        doc = db.collection(COLLECTION).document(pid)
        snap = doc.get()
        if snap.exists:
            doc.delete()
            return {"removido": True}
        return {"removido": False}

    @router.get("/api/admin/piloto/resumo.csv")
    def export_pilot_csv(user: dict = dep):
        """Exportação 100% anonimizada (somente administrador) para análise na dissertação."""
        if not is_admin_fn(user):
            raise HTTPException(403, "Somente administradores podem exportar os dados do piloto.")
        rows = [s.to_dict() for s in db.collection(COLLECTION).stream() if s.to_dict()]
        rows.sort(key=lambda r: r.get("submitted_at") or "")
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([
            "codigo_anonimo", "versao_piloto", "data_envio", "vinculo", "familiaridade_digital",
            "sus_score", "sus_faixa", *[f"sus_q{i}" for i in range(1, 11)],
            "o_que_ajudou", "o_que_dificultou", "percepcao_autoria",
            "transf_blocos", "transf_problema", "transf_pergunta", "transf_objetivo", "transf_coleta",
        ])
        for r in rows:
            sus_vals = (r.get("sus_answers") or []) + [""] * 10
            tr = r.get("transferencia") or {}
            writer.writerow([
                r.get("participant_code", ""), r.get("pilot_version", ""), r.get("submitted_at", ""),
                r.get("vinculo", ""), r.get("familiaridade_digital", ""),
                r.get("sus_score", ""), r.get("sus_faixa", ""), *sus_vals[:10],
                r.get("o_que_ajudou", ""), r.get("o_que_dificultou", ""), r.get("percepcao_autoria", ""),
                r.get("transferencia_completude", 0),
                tr.get("problema", ""), tr.get("pergunta", ""), tr.get("objetivo_geral", ""), tr.get("como_coletar", ""),
            ])
        scores = [float(r["sus_score"]) for r in rows if r.get("sus_score") is not None]
        headers = {
            "Content-Disposition": f'attachment; filename="piloto_scriptorium_{PILOT_VERSION}.csv"',
            "Cache-Control": "no-store",
            "X-Scriptorium-Pilot-N": str(len(rows)),
            "X-Scriptorium-SUS-Mean": f"{statistics.mean(scores):.1f}" if scores else "",
        }
        return Response(content=("\ufeff" + out.getvalue()).encode("utf-8"),
                        media_type="text/csv; charset=utf-8", headers=headers)

    return router
