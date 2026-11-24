"""Escudo de auditoria científica em camadas (M06).

Origem: R01, consolidando os módulos que consultam R08/R09/R10/R11 (bases
bibliográficas), R12 (ponteiros) e R44 (embeddings). Plano: Scriptorium V2,
módulo M06 "Escudo de auditoria científica em camadas".

Quatro estágios do plano, na ordem (decisões determinísticas antes de LLM):
1. resolução de ponteiros e citações literais (M05);
2. correspondência de metadados: DOI, título, ano (conferência bibliográfica);
3. situação editorial: retratações, retiradas, correções (M07);
4. suporte semântico afirmação/evidência (M08): ainda NÃO classificado por
   modelo; o estágio informa só trechos candidatos.
Mais a triagem heurística local do texto (percentuais, BibTeX).

Saída: lista de itens que pedem atenção, por gravidade (alta, média, baixa),
e o estado de cada estágio. Não existe nota geral nem selo de "verificado".
"""
from __future__ import annotations

from source_quality import quality_factors

VERSION = "audit-shield-1"
LEVELS = ("alta", "media", "baixa")
HIGH_HEURISTICS = {"percentages_without_experiments", "missing_bibliography_keys", "no_bibliography"}


def _item(level, stage, title, detail, ref=None):
    return {"level": level, "stage": stage, "title": title, "detail": detail[:500], "ref": ref}


def _stage(status, **extra):
    return {"status": status, **extra}


def build_shield(audit: dict | None, references: dict | None, evidence: dict | None) -> dict:
    items, stages = [], {}

    # Estágio 1: ponteiros e citações literais (M05).
    quotes = (evidence or {}).get("quotes")
    if quotes:
        stages["1_ponteiros_citacoes"] = _stage("executado", **quotes.get("summary", {}))
        for q in quotes.get("quotes", []):
            if q["status"] == "not_found_in_sources":
                items.append(_item("media", "1_ponteiros_citacoes", "Citação literal não encontrada nas fontes anexadas",
                                   f'"{q["quote"]}". Conferir na obra original; pode ter sido inventada.'))
            elif q["status"] == "approximate":
                items.append(_item("baixa", "1_ponteiros_citacoes", "Citação com redação diferente da fonte",
                                   f'"{q["quote"]}" (semelhança {q.get("overlap")}). Corrigir para o texto exato.',
                                   q.get("chunk_id")))
        for p in quotes.get("pointers", []):
            if p["status"] == "unknown":
                items.append(_item("alta", "1_ponteiros_citacoes", "Ponteiro para trecho inexistente",
                                   f"O texto cita o trecho {p['chunk_id']}, que não existe nas fontes desta pesquisa.",
                                   p["chunk_id"]))
    else:
        stages["1_ponteiros_citacoes"] = _stage("nao_executado",
                                                motivo="Disponível com a leitura por trechos (V2) ligada.")

    # Estágios 2 e 3: metadados e situação editorial.
    if references:
        stages["2_metadados"] = _stage("executado", consultadas=references.get("checked"),
                                       nao_consultadas_por_limite=references.get("skipped_by_limit"))
        stages["3_situacao_editorial"] = _stage("executado", **(references.get("editorial_summary") or {}).get("counts", {}))
        for ref in references.get("items", []):
            label = (ref.get("reference") or {}).get("key") or (ref.get("reference") or {}).get("title", "")[:60]
            state = ref.get("classification")
            if state == "metadata_conflict":
                items.append(_item("alta", "2_metadados", "Metadados divergentes",
                                   f"{label}: DOI aponta para obra com título ou ano diferentes.", label))
            elif state == "not_found":
                items.append(_item("media", "2_metadados", "Referência não localizada nas bases globais",
                                   f"{label}: conferir manualmente (links sugeridos no relatório de referências).", label))
            elif state in ("possible_match", "inconclusive", "insufficient_metadata"):
                items.append(_item("baixa", "2_metadados", "Referência não confirmada",
                                   f"{label}: {state}.", label))
            editorial = (ref.get("editorial") or {}).get("editorial_status")
            if editorial in ("retracted", "withdrawn"):
                items.append(_item("alta", "3_situacao_editorial", "Obra retratada ou retirada",
                                   f"{label}: {(ref.get('editorial') or {}).get('label')}. Não usar como evidência sem justificar.",
                                   label))
            elif editorial == "expression_of_concern":
                items.append(_item("media", "3_situacao_editorial", "Expressão de preocupação",
                                   f"{label}: a editora publicou ressalva sobre a obra.", label))
            elif editorial == "corrected":
                items.append(_item("baixa", "3_situacao_editorial", "Obra com correção publicada",
                                   f"{label}: conferir se a correção afeta o trecho citado.", label))
            # Relatórios anteriores ao M18 não trazem os fatores: calcular aqui.
            factors = ref.get("quality_factors") or quality_factors(ref)
            quality = factors.get("retraction_signals") or {}
            if quality.get("openalex_is_retracted") and editorial not in ("retracted", "withdrawn"):
                items.append(_item("alta", "3_situacao_editorial", "OpenAlex indica retratação",
                                   f"{label}: a Crossref não mostrou aviso, mas o OpenAlex marca como retratada. Conferir.",
                                   label))
    else:
        stages["2_metadados"] = _stage("indisponivel")
        stages["3_situacao_editorial"] = _stage("indisponivel")

    # Estágio 4: suporte semântico (só candidatos; sem classificação por modelo).
    matrix = (evidence or {}).get("matrix")
    if matrix:
        stages["4_suporte_semantico"] = _stage("parcial", motivo="Trechos candidatos localizados; relação apoia/contradiz não classificada.",
                                               **matrix.get("summary", {}))
        for row in matrix.get("claims", []):
            if row["audit_state"] == "sem_evidencia_no_corpus":
                level = "baixa" if row.get("cites") else "media"
                why = ("apoia-se em referência da bibliografia que não foi anexada" if row.get("cites")
                       else "não tem citação nem trecho correspondente nas fontes")
                items.append(_item(level, "4_suporte_semantico", "Afirmação sem evidência nas fontes anexadas",
                                   f"{row['claim_id']}: {row['text'][:300]} ({why}).", row["claim_id"]))
    else:
        stages["4_suporte_semantico"] = _stage("nao_executado",
                                               motivo="Disponível com a leitura por trechos (V2) ligada.")

    # Triagem heurística local (já existente na V1).
    if audit:
        stages["triagem_heuristica"] = _stage("executado", alertas=(audit.get("summary") or {}).get("findings"))
        for finding in audit.get("findings", []):
            level = "alta" if finding.get("code") in HIGH_HEURISTICS else "media"
            items.append(_item(level, "triagem_heuristica", finding.get("title") or finding.get("code", ""),
                               finding.get("detail", "")))
    else:
        stages["triagem_heuristica"] = _stage("indisponivel")

    items.sort(key=lambda i: LEVELS.index(i["level"]))
    counts = {level: sum(i["level"] == level for i in items) for level in LEVELS}
    return {
        "version": VERSION, "stages": stages, "counts": counts, "items": items[:300],
        "verdict": None,
        "limitations": [
            "Não há nota geral nem selo de 'verificado': o escudo só organiza o que exige atenção.",
            "Ausência de alertas não comprova validade científica, nem que as fontes sustentam o texto.",
            "O estágio 4 ainda não classifica se o trecho apoia ou contradiz a afirmação.",
        ],
    }
