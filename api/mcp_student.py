"""Visão do projeto para o estudante, no site: próximo passo em linguagem simples,
o que o Scriptorium já conferiu e as referências que ainda pedem conferência.

Não usa IA nem muda o projeto: só lê o estado e os arquivos já gravados.
"""
from __future__ import annotations

import mcp_flow as flow

REF_FIX = "corrija as referências marcadas para conferir"


def _quoted(title: str) -> str:
    title = " ".join(str(title or "").split())
    return f"“{title[:90]}{'…' if len(title) > 90 else ''}”" if title else "o meu projeto"


def references_to_check(refs: list[dict]) -> list[dict]:
    """Referências montadas só com o que estava no arquivo (sem correspondência segura)."""
    out = []
    for r in refs or []:
        if r.get("how") != "arquivo":
            continue
        fields = r.get("fields") or {}
        out.append({"chave": r.get("key", ""), "titulo": str(fields.get("title", ""))[:160],
                    "autor": str(fields.get("author", ""))[:120]})
    return out


def proofs(stages: dict, mode: str, kappa: dict | None = None) -> list[str]:
    """Frases curtas com o que já foi conferido, para dar confiança sem jargão."""
    lines = []
    ev = (stages.get("evidencias") or {})
    s = ev.get("summary") or {}
    if ev.get("status") == "aceita" and s.get("total"):
        lines.append(f"{s.get('conferidas', 0)} de {s['total']} citações encontradas, palavra por palavra, no texto das fontes")
    for key in ("reescrita", "redacao"):
        st = stages.get(key) or {}
        s = st.get("summary") or {}
        if st.get("status") == "aceita" and s.get("fontes_citadas") is not None:
            n = len(s.get("fontes_citadas") or [])
            lines.append(f"O texto cita {n} fonte{'s' if n != 1 else ''} do projeto, sempre pelas chaves das referências")
            break
    rv = stages.get("revisao") or {}
    s = rv.get("summary") or {}
    if rv.get("status") == "aceita" and s.get("problemas") is not None:
        p = s["problemas"]
        lines.append(f"Revisão feita em outra conversa: nota {s.get('nota_geral', 0):g} de 10, "
                     f"{p.get('alta', 0)} problema(s) grave(s) apontado(s)")
    vf = stages.get("verificacao") or {}
    s = vf.get("summary") or {}
    if vf.get("status") == "aceita" and s.get("vereditos"):
        v = s["vereditos"]
        lines.append(f"Afirmações verificadas nas fontes: {v.get('sustentada', 0)} sustentadas, "
                     f"{v.get('parcial', 0)} parciais, {v.get('sem_suporte', 0)} sem suporte")
    if kappa and kappa.get("kappa") is not None:
        lines.append(f"Triagem feita duas vezes, às cegas: concordância (kappa) de {kappa['kappa']:.2f}")
    return lines


def next_step(project: dict, mode: str, to_check: int) -> dict:
    """O que o estudante faz agora: título, explicação e, quando couber, o pedido pronto para copiar."""
    status = project.get("status")
    title = _quoted(project.get("title"))
    stages = project.get("stages") or {}
    if status == "preparando":
        return {"titulo": "Aguarde alguns minutos",
                "texto": "O Scriptorium está lendo as fontes do projeto. Atualize esta página daqui a pouco."}
    if status == "falhou_preparo":
        return {"titulo": "A leitura das fontes falhou",
                "texto": "Confira se os arquivos abrem normalmente e peça à sua IA para criar o projeto de novo.",
                "detalhe": str(project.get("error", ""))[:300]}
    if status == "compilando":
        return {"titulo": "Gerando o PDF", "texto": "Leva um ou dois minutos. Atualize esta página em seguida."}
    if status == "concluido":
        return {"titulo": "PDF pronto",
                "texto": "Baixe o PDF, leia com calma e confira as referências antes de levar à orientação."}
    nxt = flow.next_stage(stages, mode)
    if nxt is None:
        if to_check:
            return {"titulo": "Confira as referências e gere o PDF",
                    "texto": f"Todas as etapas foram aceitas. Antes do PDF, peça à sua IA para corrigir as {to_check} referência(s) marcadas.",
                    "pedido": f"Use o Scriptorium: {REF_FIX} do projeto {title} e depois compile o PDF."}
        return {"titulo": "Gere o PDF", "texto": "Todas as etapas foram aceitas.",
                "pedido": f"Use o Scriptorium: compile o projeto {title}."}
    state = stages.get(nxt["key"]) or {}
    returned = state.get("status") == "recusada"
    if nxt.get("nova_conversa"):
        code = state.get("passe")
        why = "Quem escreveu não revisa o próprio texto. "
        if code:
            return {"titulo": f"{nxt['titulo']}: abra uma conversa nova",
                    "texto": why + "Abra uma conversa nova, de preferência em outra IA conectada ao Scriptorium, e cole o pedido abaixo.",
                    "pedido": f"Use o Scriptorium: abrir_passe com o código {code}", "passe": code}
        return {"titulo": f"Próximo: {nxt['titulo']}",
                "texto": why + "Volte à conversa do projeto e peça para continuar; a IA vai entregar um passe para abrir em outra conversa.",
                "pedido": f"Use o Scriptorium: continue o projeto {title}."}
    texto = ("A última entrega desta etapa voltou com correções a fazer. " if returned else "") + \
        "Na conversa com a sua IA, peça para continuar. Ela segue as etapas sozinha e o Scriptorium confere cada entrega."
    return {"titulo": f"Próximo: {nxt['titulo']}", "texto": texto,
            "pedido": f"Use o Scriptorium: continue o projeto {title}."}


def view(project: dict, mode: str, refs: list[dict], kappa: dict | None = None) -> dict:
    to_check = references_to_check(refs)
    return {"proximo_passo": next_step(project, mode, len(to_check)),
            "provas": proofs(project.get("stages") or {}, mode, kappa),
            "referencias_a_conferir": to_check,
            "pedido_referencias": (f"Use o Scriptorium: {REF_FIX} do projeto {_quoted(project.get('title'))}."
                                   if to_check else "")}
