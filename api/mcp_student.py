"""Visão do projeto para o estudante, no site: próximo passo em linguagem simples,
o que o Scriptorium já conferiu e as referências que ainda pedem conferência.

Não usa IA nem muda o projeto: só lê o estado e os arquivos já gravados.
"""
from __future__ import annotations

import mcp_flow as flow

REF_FIX = "confirme ou corrija as referências marcadas para conferir"
COMPILE_DRAFT = "compile como rascunho"


def _quoted(title: str) -> str:
    title = " ".join(str(title or "").split())
    return f"“{title[:90]}{'…' if len(title) > 90 else ''}”" if title else "o meu projeto"


def references_to_check(refs: list[dict], sources: list[dict] | None = None) -> list[dict]:
    """Referências que ainda não foram confirmadas: sugeridas por busca ou só do arquivo."""
    formats = {s.get("id"): s.get("format") for s in (sources or []) if isinstance(s, dict)}
    out = []
    for r in flow.pending_refs(refs):
        fields = r.get("fields") or {}
        level = flow.ref_level(r)
        sid = r.get("source_id") or ""
        venue = (fields.get("journal") or fields.get("booktitle") or fields.get("school")
                 or fields.get("publisher") or fields.get("institution") or fields.get("howpublished") or "")
        out.append({
            "chave": r.get("key", ""), "source_id": sid, "tipo": r.get("type") or "article",
            "titulo": str(fields.get("title", ""))[:200], "autor": str(fields.get("author", ""))[:200],
            "ano": str(fields.get("year", ""))[:10], "veiculo": str(venue)[:160],
            "doi": str(fields.get("doi", ""))[:120],
            "nivel": level, "nivel_texto": flow.REF_LEVEL_LABELS[level],
            "origem": r.get("how") or "arquivo",
            "tem_capa": formats.get(sid) == "pdf" if formats else True,
            "proposta_pendente": r.get("proposta_pendente"),
        })
    return out


def proofs(stages: dict, mode: str, kappa: dict | None = None) -> list[str]:
    """Frases curtas com o que já foi conferido, para dar confiança sem jargão."""
    lines = []
    ev = (stages.get("evidencias") or {})
    s = ev.get("summary") or {}
    if ev.get("status") == "aceita" and s.get("total"):
        para = f" ({s['parafrases']} paráfrase(s) ancorada(s))" if s.get("parafrases") else ""
        lines.append(f"Evidências: {s.get('conferidas', 0)} de {s['total']} citações encontradas, palavra por "
                     f"palavra, no texto das fontes{para}")
    for key in ("reescrita", "redacao"):
        st = stages.get(key) or {}
        s = st.get("summary") or {}
        if st.get("status") == "aceita" and s.get("fontes_citadas") is not None:
            n = len(s.get("fontes_citadas") or [])
            lines.append(f"O texto cita {n} fonte{'s' if n != 1 else ''} do projeto, sempre pelas chaves das referências")
            quotes = s.get("citacoes_texto")
            if quotes is None:
                lines.append("Citações diretas do texto final: não conferidas (projeto anterior a esta checagem)")
            elif quotes.get("total"):
                extra = f"; {quotes['traduzidas']} marcada(s) como tradução" if quotes.get("traduzidas") else ""
                lines.append(f"Texto final: {quotes.get('conferidas', 0)} de {quotes['total']} citações diretas "
                             f"conferidas na fonte citada{extra}")
            q = s.get("qualidade") or {}
            if q.get("excesso_citacao_direta"):
                lines.append(f"Atenção de estilo: {q['citacoes_diretas_por_mil_palavras']} citações diretas por mil palavras (prefira mais paráfrases)")
            rr = s.get("respostas_revisao") or {}
            if rr.get("altos_total"):
                lines.append(f"Resposta à revisão: {rr.get('altos_respondidos', 0)} de {rr['altos_total']} problema(s) grave(s) respondido(s)")
            break
    rv = stages.get("revisao") or {}
    s = rv.get("summary") or {}
    if rv.get("status") == "aceita" and s.get("problemas") is not None:
        p = s["problemas"]
        ind = rv.get("independencia") or {}
        who = "Autoverificação (mesmo modelo em conversa nova)" if ind.get("autoverificacao") else "Revisão feita em outra conversa"
        crit = s.get("criterios") or {}
        crit_txt = (" · critérios: " + ", ".join(f"{k.replace('_', ' ')} {v:g}" for k, v in crit.items())) if crit else ""
        lines.append(f"{who}: nota {s.get('nota_geral', 0):g} de 10, "
                     f"{p.get('alta', 0)} problema(s) grave(s) apontado(s){crit_txt}")
    vf = stages.get("verificacao") or {}
    s = vf.get("summary") or {}
    if vf.get("status") == "aceita" and s.get("vereditos"):
        v = s["vereditos"]
        ind = vf.get("independencia") or {}
        tag = " (autoverificação — mesmo modelo)" if ind.get("autoverificacao") else ""
        srv = f", {s['sorteadas_pelo_servidor']} sorteada(s) pelo servidor" if s.get("sorteadas_pelo_servidor") else ""
        lines.append(f"Afirmações verificadas nas fontes{tag}: {v.get('sustentada', 0)} sustentadas, "
                     f"{v.get('parcial', 0)} parciais, {v.get('sem_suporte', 0)} sem suporte{srv}")
    if kappa and kappa.get("kappa") is not None:
        lines.append(f"Triagem feita duas vezes, às cegas: concordância (kappa) de {kappa['kappa']:.2f}")
    return lines


def final_pdf(project: dict, to_check: int) -> bool:
    """PDF final de verdade: compilado com a trava (versão "final") e sem referência pendente.

    Projetos compilados antes de 26/11/2026 têm status "concluido" sem essa conferência.
    """
    report = project.get("compile_report") or {}
    return project.get("status") == "concluido" and report.get("versao") == "final" and not to_check


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
    if status == "refazendo_referencias":
        return {"titulo": "Refazendo as referências",
                "texto": "Leva um ou dois minutos. As chaves já citadas no texto continuam as mesmas."}
    if status == "concluido" and not final_pdf(project, to_check):
        pending = (f" Há {to_check} referência(s) ainda não confirmada(s)." if to_check else "")
        return {"titulo": "PDF gerado antes da conferência das referências",
                "texto": "Este PDF foi compilado antes das travas da versão final e pode ter referências "
                         "erradas." + pending + " Refaça as referências, confirme as pendentes e compile de novo.",
                "pedido": f"Use o Scriptorium: refaça as referências do projeto {title}, {REF_FIX} e compile de novo."}
    if status == "concluido":
        return {"titulo": "PDF final pronto",
                "texto": "Todas as referências foram confirmadas e o PDF saiu sem erro de LaTeX. Leia com calma "
                         "antes de levar à orientação."}
    nxt = flow.next_stage(stages, mode)
    if status == "rascunho" and nxt is None:
        why = str(project.get("error", "")).strip()
        ask = (f"Use o Scriptorium: {REF_FIX} do projeto {title} e depois compile de novo." if to_check else
               f"Use o Scriptorium: reabra a reescrita do projeto {title} para corrigir os problemas da compilação.")
        return {"titulo": "Saiu um rascunho, ainda não é a versão final",
                "texto": "O PDF está marcado como RASCUNHO. " + (why or "Há pendências antes da versão final."),
                "pedido": ask}
    if nxt is None:
        if to_check:
            return {"titulo": "Confirme as referências e gere o PDF",
                    "texto": f"Todas as etapas foram aceitas. A versão final só sai depois que as {to_check} "
                             "referência(s) marcadas forem confirmadas. Se quiser ler o texto antes, peça um rascunho.",
                    "pedido": f"Use o Scriptorium: {REF_FIX} do projeto {title} e depois compile o PDF.",
                    "pedido_rascunho": f"Use o Scriptorium: {COMPILE_DRAFT} o projeto {title}."}
        return {"titulo": "Gere o PDF", "texto": "Todas as etapas foram aceitas.",
                "pedido": f"Use o Scriptorium: compile o projeto {title}."}
    state = stages.get(nxt["key"]) or {}
    returned = state.get("status") == "recusada"
    if nxt.get("nova_conversa"):
        code = state.get("passe")
        writer_head = next(((stages.get(k) or {}).get("head") for k in ("reescrita", "redacao", "triagem")
                            if (stages.get(k) or {}).get("head")), None)
        suggested = flow.recommend_other_family((writer_head or {}).get("model", ""))
        why = "Quem escreveu não revisa o próprio texto. "
        if code:
            return {"titulo": f"{nxt['titulo']}: abra uma conversa nova",
                    "texto": why + f"Abra uma conversa nova — de preferência em outra IA ({suggested}) conectada ao Scriptorium — e cole o pedido abaixo.",
                    "pedido": f"Use o Scriptorium: abrir_passe com o código {code}", "passe": code,
                    "ia_recomendada": suggested}
        return {"titulo": f"Próximo: {nxt['titulo']}",
                "texto": why + "Volte à conversa do projeto e peça para continuar; a IA vai entregar um passe para abrir em outra conversa.",
                "pedido": f"Use o Scriptorium: continue o projeto {title}."}
    texto = ("A última entrega desta etapa voltou com correções a fazer. " if returned else "") + \
        "Na conversa com a sua IA, peça para continuar. Ela segue as etapas sozinha e o Scriptorium confere cada entrega."
    return {"titulo": f"Próximo: {nxt['titulo']}", "texto": texto,
            "pedido": f"Use o Scriptorium: continue o projeto {title}."}


def view(project: dict, mode: str, refs: list[dict], kappa: dict | None = None) -> dict:
    to_check = references_to_check(refs, project.get("sources"))
    all_done = flow.next_stage(project.get("stages") or {}, mode) is None
    return {"proximo_passo": next_step(project, mode, len(to_check)),
            "pdf_final": final_pdf(project, len(to_check)),
            "pode_compilar": all_done and project.get("status") not in ("preparando", "compilando", "refazendo_referencias"),
            "provas": proofs(project.get("stages") or {}, mode, kappa),
            "referencias_a_conferir": to_check,
            "pedido_referencias": (f"Use o Scriptorium: {REF_FIX} do projeto {_quoted(project.get('title'))}."
                                   if to_check else "")}
