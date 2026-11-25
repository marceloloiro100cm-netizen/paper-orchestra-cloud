"""Modo revisão sistemática do fluxo MCP (ideias da LENAI, colega do mestrado, 25/11/2026).

Etapas, na ordem:
1. protocolo: PICOC, questões (QP), inclusão (IC), exclusão (EC), avaliação de
   qualidade (AQ) com escala de pesos e nota de corte, campos de extração e a
   busca declarada (bases e números de registros, para o PRISMA);
2. triagem: decisão por fonte, critério por critério, com checklist de leitura
   e uma citação literal conferida;
3. triagem independente: outra cabeça, por passe e às cegas, refaz a triagem;
   o Scriptorium calcula o kappa de Cohen e lista as divergências;
4. consenso: a cabeça redatora resolve só as divergências (pulada se não há);
5. qualidade e extração: nota por AQ e campos de extração, cada valor com
   citação literal conferida; trechos de método, resultados e limitações;
6. síntese por QP (o pesquisador pode gravar a versão final no site);
7. redação, revisão independente, reescrita e verificação, como no artigo.

O PRISMA 2020 sai das decisões e confere a conservação dos números. Lógica
pura, sem rede: os testes rodam sem Firestore.
"""
from __future__ import annotations

import csv
import io
import json
import re

import mcp_flow as flow

MODE = "revisao_sistematica"
CHECKLIST = ("titulo_resumo", "metodo", "resultados", "limitacoes")
DECISIONS = ("incluir", "excluir", "fora_da_triagem")
NOT_REPORTED = "nao_relatado"

STAGES = [
    {
        "key": "protocolo", "titulo": "Protocolo", "cabeca": "redatora", "nova_conversa": False,
        "formato": "json", "min": 400,
        "instrucoes": (
            "Você é a cabeça PLANEJADORA de uma revisão sistemática. Leia as fichas das fontes e entregue o "
            "protocolo em JSON com: \"pergunta\"; \"picoc\" {populacao, intervencao, comparacao, resultado, "
            "contexto}; \"questoes\" [{id: QP1, texto}]; \"inclusao\" [{id: IC1, texto}]; \"exclusao\" "
            "[{id: EC1, texto}]; \"qualidade\" [{id: AQ1, texto}]; \"escala\" [{descricao, peso}] com no "
            "mínimo 3 respostas (ex.: Sim 1, Parcial 0.5, Não 0); \"nota_corte\"; \"excluir_abaixo_do_corte\" "
            "(true/false); \"extracao\" [{campo, descricao}]; e \"busca\" {bases: [{nome, registros, data, "
            "string}], duplicados_removidos, excluidos_titulo_resumo, nao_recuperados}. Os números da busca "
            "são os que o PESQUISADOR informou; se ele não informou, pergunte antes de inventar ou deixe a "
            "busca de fora."),
    },
    {
        "key": "triagem", "titulo": "Triagem (elegibilidade)", "cabeca": "redatora", "nova_conversa": False,
        "formato": "json", "min": 200,
        "instrucoes": (
            "Você é a primeira TRIADORA. Para CADA fonte do projeto, leia título, resumo, método e "
            "resultados (buscar_trechos com zona, ler_trecho) e entregue uma lista JSON com: \"chave\"; "
            "\"decisao\" (incluir, excluir ou fora_da_triagem, esta para guias de método e textos teóricos "
            "que não são estudos primários); \"criterios\" {IC1: true/false, ..., EC1: true/false, ...} "
            "(EC true quando a fonte TEM o motivo de exclusão); \"motivo\" (o EC ou IC que exclui, se "
            "excluir); \"checklist\" {titulo_resumo, metodo, resultados, limitacoes} marcando o que você "
            "leu; e \"citacao_literal\" + \"chunk_id\" de um trecho que sustenta a decisão."),
    },
    {
        "key": "triagem_independente", "titulo": "Triagem independente", "cabeca": "triadora",
        "nova_conversa": True, "formato": "json", "min": 200, "compara_com": ("triagem",),
        "instrucoes": (
            "Você é a SEGUNDA TRIADORA, às cegas: não viu a primeira triagem. Faça a triagem de CADA fonte "
            "com o mesmo formato JSON da primeira (chave, decisao, criterios, motivo, checklist, "
            "citacao_literal, chunk_id), lendo as fontes por conta própria. O Scriptorium calcula a "
            "concordância (kappa de Cohen) e as divergências."),
    },
    {
        "key": "consenso", "titulo": "Consenso das divergências", "cabeca": "redatora", "nova_conversa": False,
        "formato": "json", "min": 2,
        "instrucoes": (
            "Você é a cabeça REDATORA. Para cada fonte em que as duas triagens divergiram, releia a fonte e "
            "decida. Entregue uma lista JSON com \"chave\", \"decisao_final\" (incluir, excluir ou "
            "fora_da_triagem), \"motivo\" (se excluir) e \"justificativa\"."),
    },
    {
        "key": "qualidade_extracao", "titulo": "Qualidade e extração", "cabeca": "redatora",
        "nova_conversa": False, "formato": "json", "min": 200,
        "instrucoes": (
            "Você é a cabeça LEITORA. Para cada estudo INCLUÍDO, entregue um objeto JSON com: \"chave\"; "
            "\"qualidade\" {AQ1: descricao da escala, ...}; \"extracao\" {nome do campo: {\"valor\": ..., "
            "\"citacao_literal\": trecho copiado da fonte ou \"nao_relatado\"}}; e \"trechos\" {metodo, "
            "resultados, limitacoes} com citações literais (limitacoes pode ser \"nao_relatado\"). O "
            "Scriptorium confere cada citação e calcula a nota de qualidade."),
    },
    {
        "key": "sintese", "titulo": "Síntese por questão", "cabeca": "redatora", "nova_conversa": False,
        "formato": "json", "min": 200,
        "instrucoes": (
            "Você é a cabeça SINTETIZADORA. Para cada QP, responda com base na matriz de extração. Entregue "
            "JSON {QP1: {\"resposta\": texto, \"chaves\": [estudos que sustentam]}, ...}. Diga quando os "
            "estudos não respondem à QP. O pesquisador pode gravar a versão final de cada resposta no site; "
            "essa versão substitui a sua na redação."),
    },
]
WRITING = ["redacao", "revisao", "reescrita", "verificacao"]
BY_KEY = {s["key"]: s for s in STAGES}


def stages() -> list[dict]:
    return STAGES + [flow.BY_KEY[k] for k in WRITING]


# ---------------------------------------------------------------- zonas
ZONES = [
    ("referencias", r"refer[eê]ncias|bibliograf|references|works cited"),
    ("resumo", r"\bresumo\b|abstract|resumen"),
    ("limitacoes", r"limita[cç]|limitation|amea[cç]as|validade|threats"),
    ("metodo", r"m[eé]todo|metodolog|method|procedimentos|participantes|amostra|materiais|design"),
    ("resultados", r"resultado|results|achados|findings|an[aá]lise dos dados"),
    ("discussao", r"discuss|considera[cç][oõ]es|conclus|conclusion"),
    ("introducao", r"introdu|introduction|justificativa|referencial|fundamenta|revis[aã]o de literatura"),
]


def zone_of(heading: str) -> str:
    """Zona do artigo pelo título da seção (método, resultados, limitações...)."""
    text = (heading or "").lower()
    for zone, pattern in ZONES:
        if re.search(pattern, text):
            return zone
    return "outra"


# ---------------------------------------------------------------- protocolo
def _ids(items, prefix: str) -> list[dict]:
    out = []
    for n, item in enumerate(items or [], 1):
        if isinstance(item, str):
            item = {"id": f"{prefix}{n}", "texto": item}
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or f"{prefix}{n}").replace("-", "").replace(" ", "").upper()
        if not re.fullmatch(prefix + r"\d+", ident):
            ident = f"{prefix}{n}"
        out.append({**item, "id": ident, "texto": str(item.get("texto") or item.get("descricao") or "").strip()})
    return out


def parse_protocol(content: str) -> dict:
    data = flow.parse_json(content)
    if not isinstance(data, dict):
        raise ValueError("O protocolo deve ser um objeto JSON.")
    data["questoes"] = _ids(data.get("questoes"), "QP")
    data["inclusao"] = _ids(data.get("inclusao"), "IC")
    data["exclusao"] = _ids(data.get("exclusao"), "EC")
    data["qualidade"] = _ids(data.get("qualidade"), "AQ")
    data["extracao"] = [e if isinstance(e, dict) else {"campo": str(e)} for e in data.get("extracao") or []]
    return data


def validate_protocol(content: str) -> dict:
    errors = flow._size_errors(content, BY_KEY["protocolo"]["min"])
    try:
        p = parse_protocol(content)
    except ValueError as exc:
        return flow._report(False, errors + [str(exc) if "objeto" in str(exc) else "O conteúdo não é um JSON válido."])
    picoc = p.get("picoc") or {}
    for part in ("populacao", "intervencao", "resultado"):
        if not str(picoc.get(part) or "").strip():
            errors.append(f"PICOC: preencha \"{part}\".")
    for field, label in (("questoes", "questão de pesquisa"), ("inclusao", "critério de inclusão"),
                         ("exclusao", "critério de exclusão"), ("qualidade", "questão de qualidade")):
        if not p[field] or any(not i["texto"] for i in p[field]):
            errors.append(f"Inclua ao menos uma {label}, com texto.")
        if len({i["id"] for i in p[field]}) != len(p[field]):
            errors.append(f"Identificadores repetidos em {field}.")
    scale = p.get("escala") or []
    try:
        weights = [float(s["peso"]) for s in scale]
        names = [str(s["descricao"]).strip() for s in scale]
    except (KeyError, TypeError, ValueError):
        weights, names = [], []
    if len(weights) < 3 or len(set(names)) < 3 or len(set(weights)) < 2:
        errors.append("A escala de qualidade precisa de pelo menos 3 respostas distintas com peso numérico.")
    maximum = max(weights) * len(p["qualidade"]) if weights else 0
    try:
        cut = float(p.get("nota_corte"))
        if not 0 <= cut <= maximum:
            errors.append(f"A nota de corte deve ficar entre 0 e {maximum:g}.")
    except (TypeError, ValueError):
        errors.append("Informe a nota_corte (número).")
    if not p["extracao"] or any(not str(e.get("campo") or "").strip() for e in p["extracao"]):
        errors.append("Defina ao menos um campo de extração, com nome.")
    busca = p.get("busca")
    if busca:
        try:
            for base in busca.get("bases") or []:
                int(base.get("registros"))
            for key in ("duplicados_removidos", "excluidos_titulo_resumo", "nao_recuperados"):
                int(busca.get(key) or 0)
        except (TypeError, ValueError, AttributeError):
            errors.append("Os números da busca (registros, duplicados, excluídos, não recuperados) devem ser inteiros.")
    return flow._report(True, errors, questoes=len(p["questoes"]), criterios=len(p["inclusao"]) + len(p["exclusao"]),
                        nota_maxima=maximum, campos=len(p["extracao"]))


# ---------------------------------------------------------------- triagem
def _list(content: str, key: str):
    data = flow.parse_json(content)
    if isinstance(data, dict):
        data = data.get(key) or data.get("itens") or []
    if not isinstance(data, list):
        raise ValueError
    return data


def validate_screening(content: str, protocol: dict, source_keys: list[str], chunks_for_key) -> dict:
    errors = flow._size_errors(content, BY_KEY["triagem"]["min"])
    try:
        items = _list(content, "triagem")
    except ValueError:
        return flow._report(False, errors + ["Entregue uma lista JSON, um item por fonte."])
    ic = [c["id"] for c in protocol["inclusao"]]
    ec = [c["id"] for c in protocol["exclusao"]]
    seen, decisions = [], {}
    for n, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f"Item {n}: deveria ser um objeto.")
            continue
        key, decision = str(item.get("chave", "")), item.get("decisao")
        if key not in source_keys:
            errors.append(f"Item {n}: chave '{key}' não é fonte deste projeto.")
            continue
        seen.append(key)
        if decision not in DECISIONS:
            errors.append(f"{key}: decisao deve ser incluir, excluir ou fora_da_triagem.")
            continue
        decisions[key] = decision
        if decision == "fora_da_triagem":
            continue
        crit = item.get("criterios") or {}
        missing = [c for c in ic + ec if not isinstance(crit.get(c), bool)]
        if missing:
            errors.append(f"{key}: marque true/false em " + ", ".join(missing) + ".")
            continue
        if decision == "incluir" and (not all(crit[c] for c in ic) or any(crit[c] for c in ec)):
            errors.append(f"{key}: para incluir, todos os IC devem ser true e todos os EC false.")
        if decision == "excluir":
            reason = str(item.get("motivo", "")).upper().replace("-", "")
            if not ((reason in ec and crit.get(reason)) or (reason in ic and not crit.get(reason))):
                errors.append(f"{key}: o motivo deve ser um EC marcado true ou um IC marcado false.")
        checklist = item.get("checklist") or {}
        if not checklist.get("titulo_resumo") or not checklist.get("metodo"):
            errors.append(f"{key}: leia ao menos título, resumo e método antes de decidir (checklist).")
        if decision == "incluir" and not all(checklist.get(c) for c in CHECKLIST):
            errors.append(f"{key}: para incluir, o checklist de leitura deve estar completo.")
        quote = str(item.get("citacao_literal") or "")
        chunks = chunks_for_key(key) or []
        if not 20 <= len(quote) <= 600 or not any(flow.quote_in(quote, c.get("text", "")) for c in chunks):
            errors.append(f"{key}: a citação literal não foi encontrada na fonte.")
    missing_keys = [k for k in source_keys if k not in seen]
    if missing_keys:
        errors.append("Faltou decidir: " + ", ".join(missing_keys) + ".")
    repeated = sorted({k for k in seen if seen.count(k) > 1})
    if repeated:
        errors.append("Fontes repetidas: " + ", ".join(repeated) + ".")
    tally = {d: sum(1 for v in decisions.values() if v == d) for d in DECISIONS}
    return flow._report(True, errors, decisoes=tally)


def decisions_of(content: str) -> dict:
    try:
        return {str(i.get("chave")): i.get("decisao") for i in _list(content, "triagem") if isinstance(i, dict)}
    except (ValueError, TypeError):
        return {}


def reasons_of(content: str) -> dict:
    try:
        return {str(i.get("chave")): str(i.get("motivo", "")).upper().replace("-", "")
                for i in _list(content, "triagem") if isinstance(i, dict)}
    except (ValueError, TypeError):
        return {}


def cohen_kappa(a: dict, b: dict) -> dict:
    """Kappa de Cohen entre duas triagens (incluir, excluir, fora_da_triagem)."""
    keys = sorted(set(a) & set(b))
    if not keys:
        return {"kappa": None, "concordancia": None, "n": 0, "divergencias": [], "leitura": "sem dados"}
    agree = sum(1 for k in keys if a[k] == b[k]) / len(keys)
    expected = sum((sum(1 for k in keys if a[k] == c) / len(keys)) * (sum(1 for k in keys if b[k] == c) / len(keys))
                   for c in DECISIONS)
    kappa = 1.0 if expected >= 1 else (agree - expected) / (1 - expected)
    reading = ("quase perfeita" if kappa > 0.8 else "substancial" if kappa > 0.6 else "moderada" if kappa > 0.4
               else "razoável" if kappa > 0.2 else "fraca")
    return {"kappa": round(kappa, 3), "concordancia": round(agree, 3), "n": len(keys), "leitura": reading,
            "divergencias": [k for k in keys if a[k] != b[k]]}


def validate_consensus(content: str, divergent: list[str], protocol: dict) -> dict:
    try:
        items = _list(content, "consenso")
    except ValueError:
        return flow._report(False, ["Entregue uma lista JSON (vazia se não houver divergências)."])
    errors, keys = [], []
    ids = {c["id"] for c in protocol["inclusao"] + protocol["exclusao"]}
    for item in items:
        key = str((item or {}).get("chave", ""))
        keys.append(key)
        if key not in divergent:
            errors.append(f"{key}: não está entre as divergências.")
        if item.get("decisao_final") not in DECISIONS:
            errors.append(f"{key}: decisao_final inválida.")
        if item.get("decisao_final") == "excluir" and str(item.get("motivo", "")).upper().replace("-", "") not in ids:
            errors.append(f"{key}: informe o critério (EC ou IC) que exclui.")
        if len(str(item.get("justificativa") or "").strip()) < 30:
            errors.append(f"{key}: justifique a decisão (mínimo de 30 caracteres).")
    missing = [k for k in divergent if k not in keys]
    if missing:
        errors.append("Faltou resolver: " + ", ".join(missing) + ".")
    return flow._report(True, errors, resolvidas=len(keys))


def final_decisions(board: dict) -> tuple[dict, dict]:
    """Decisões finais e motivos: acordo das duas triagens + consenso."""
    a = decisions_of((board.get("triagem") or {}).get("content", ""))
    b = decisions_of((board.get("triagem_independente") or {}).get("content", ""))
    reasons = reasons_of((board.get("triagem") or {}).get("content", ""))
    final = {k: a[k] for k in a if b.get(k) == a[k]}
    try:
        for item in _list((board.get("consenso") or {}).get("content", "[]"), "consenso"):
            final[str(item.get("chave"))] = item.get("decisao_final")
            if item.get("motivo"):
                reasons[str(item.get("chave"))] = str(item["motivo"]).upper().replace("-", "")
    except (ValueError, TypeError):
        pass
    return final, reasons


# ---------------------------------------------------------------- qualidade e extração
def _score(protocol: dict, answers: dict) -> tuple[float | None, list[str]]:
    scale = {str(s["descricao"]).strip().lower(): float(s["peso"]) for s in protocol.get("escala") or []}
    total, errors = 0.0, []
    for q in protocol["qualidade"]:
        value = str((answers or {}).get(q["id"], "")).strip().lower()
        if value not in scale:
            errors.append(f"{q['id']}: responda com uma das opções da escala ({', '.join(scale)}).")
        else:
            total += scale[value]
    return (None if errors else round(total, 2)), errors


def validate_quality_extraction(content: str, protocol: dict, included: list[str], chunks_for_key) -> dict:
    errors = flow._size_errors(content, BY_KEY["qualidade_extracao"]["min"])
    try:
        items = _list(content, "estudos")
    except ValueError:
        return flow._report(False, errors + ["Entregue uma lista JSON, um objeto por estudo incluído."])
    fields = [e["campo"] for e in protocol["extracao"]]
    cut = float(protocol.get("nota_corte") or 0)
    scores, seen = {}, []
    for item in items:
        key = str((item or {}).get("chave", ""))
        if key not in included:
            errors.append(f"{key}: não é estudo incluído.")
            continue
        seen.append(key)
        chunks = chunks_for_key(key) or []
        found = lambda q: 20 <= len(q) <= 600 and any(flow.quote_in(q, c.get("text", "")) for c in chunks)  # noqa: E731
        score, problems = _score(protocol, item.get("qualidade"))
        errors += [f"{key}: {p}" for p in problems]
        scores[key] = score
        extraction = item.get("extracao") or {}
        for field in fields:
            entry = extraction.get(field)
            if not isinstance(entry, dict) or not str(entry.get("valor", "")).strip():
                errors.append(f"{key}: preencha o campo \"{field}\" com valor e citacao_literal.")
                continue
            quote = str(entry.get("citacao_literal") or "")
            if quote != NOT_REPORTED and not found(quote):
                errors.append(f"{key}: a citação do campo \"{field}\" não foi encontrada na fonte.")
        parts = item.get("trechos") or {}
        for part in ("metodo", "resultados", "limitacoes"):
            quote = str(parts.get(part) or "")
            if part == "limitacoes" and quote == NOT_REPORTED:
                continue
            if not found(quote):
                errors.append(f"{key}: o trecho de {part} não foi encontrado na fonte.")
    missing = [k for k in included if k not in seen]
    if missing:
        errors.append("Faltou avaliar: " + ", ".join(missing) + ".")
    below = sorted(k for k, s in scores.items() if s is not None and s < cut)
    return flow._report(True, errors, notas=scores, abaixo_do_corte=below, nota_corte=cut)


def quality_rows(content: str, protocol: dict) -> list[dict]:
    try:
        items = _list(content, "estudos")
    except ValueError:
        return []
    rows = []
    for item in items:
        score, _ = _score(protocol, item.get("qualidade"))
        rows.append({"chave": item.get("chave"), "nota": score,
                     "qualidade": item.get("qualidade") or {},
                     "extracao": {k: (v or {}).get("valor", "") for k, v in (item.get("extracao") or {}).items()},
                     "citacoes": {k: (v or {}).get("citacao_literal", "") for k, v in (item.get("extracao") or {}).items()}})
    return rows


def matrix_csv(rows: list[dict], protocol: dict) -> str:
    fields = [e["campo"] for e in protocol.get("extracao") or []]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["chave", "nota_qualidade"] + fields)
    for row in rows:
        writer.writerow([row["chave"], row["nota"]] + [row["extracao"].get(f, "") for f in fields])
    return out.getvalue()


# ---------------------------------------------------------------- síntese
def validate_synthesis(content: str, protocol: dict, eligible: list[str]) -> dict:
    errors = flow._size_errors(content, BY_KEY["sintese"]["min"])
    try:
        data = flow.parse_json(content)
    except ValueError:
        return flow._report(False, errors + ["O conteúdo não é um JSON válido."])
    if not isinstance(data, dict):
        return flow._report(False, errors + ["Entregue um objeto JSON com uma entrada por QP."])
    for q in protocol["questoes"]:
        entry = data.get(q["id"])
        if not isinstance(entry, dict) or len(str(entry.get("resposta") or "").strip()) < 80:
            errors.append(f"{q['id']}: escreva a resposta (mínimo de 80 caracteres).")
            continue
        unknown = [k for k in entry.get("chaves") or [] if k not in eligible]
        if unknown:
            errors.append(f"{q['id']}: chaves fora da amostra final: " + ", ".join(unknown) + ".")
    return flow._report(True, errors, questoes=len(protocol["questoes"]))


def synthesis(board: dict, project: dict) -> dict:
    """Resposta da IA por QP e, quando houver, a versão final do pesquisador."""
    try:
        data = flow.parse_json((board.get("sintese") or {}).get("content", "{}"))
    except ValueError:
        data = {}
    human = project.get("sintese_final") or {}
    return {qp: {"ia": (v or {}).get("resposta", ""), "chaves": (v or {}).get("chaves", []),
                 "final": human.get(qp, "")} for qp, v in (data or {}).items() if isinstance(v, dict)}


# ---------------------------------------------------------------- PRISMA
def prisma(protocol: dict, final: dict, reasons: dict, below_cut: list[str]) -> dict:
    """Números do PRISMA 2020 e a conferência de conservação."""
    assessed = [k for k, d in final.items() if d in ("incluir", "excluir")]
    excluded = [k for k in assessed if final[k] == "excluir"]
    by_reason: dict[str, int] = {}
    for k in excluded:
        by_reason[reasons.get(k) or "sem motivo"] = by_reason.get(reasons.get(k) or "sem motivo", 0) + 1
    drop_quality = sorted(below_cut) if protocol.get("excluir_abaixo_do_corte") else []
    included = [k for k in assessed if final[k] == "incluir" and k not in drop_quality]
    out = {"avaliados": len(assessed), "excluidos_elegibilidade": len(excluded), "motivos": by_reason,
           "excluidos_qualidade": len(drop_quality), "incluidos": len(included), "chaves_incluidas": included,
           "fora_da_triagem": sorted(k for k, d in final.items() if d == "fora_da_triagem"), "conferencias": []}
    checks = out["conferencias"]
    checks.append({"regra": "avaliados - excluídos = incluídos",
                   "ok": len(assessed) - len(excluded) - len(drop_quality) == len(included)})
    checks.append({"regra": "soma dos motivos = excluídos na elegibilidade",
                   "ok": sum(by_reason.values()) == len(excluded)})
    busca = protocol.get("busca") or {}
    if busca.get("bases"):
        bases = [{"nome": b.get("nome", ""), "registros": int(b.get("registros") or 0)} for b in busca["bases"]]
        identified = sum(b["registros"] for b in bases)
        dup = int(busca.get("duplicados_removidos") or 0)
        title = int(busca.get("excluidos_titulo_resumo") or 0)
        lost = int(busca.get("nao_recuperados") or 0)
        out.update(bases=bases, identificados=identified, duplicados=dup, triados=identified - dup,
                   excluidos_titulo_resumo=title, procurados=identified - dup - title, nao_recuperados=lost)
        checks.append({"regra": "identificados - duplicados - excluídos na triagem - não recuperados = avaliados",
                       "ok": identified - dup - title - lost == len(assessed),
                       "detalhe": f"{identified} - {dup} - {title} - {lost} = {identified - dup - title - lost}; "
                                  f"avaliados no Scriptorium: {len(assessed)}"})
    out["fecha"] = all(c["ok"] for c in checks)
    return out


# ---------------------------------------------------------------- contexto e material
def context(project: dict, board: dict, manifest_keys: list[str]) -> dict:
    """Tudo que as etapas seguintes precisam, montado do quadro aceito."""
    ctx = {"source_keys": manifest_keys}
    if "protocolo" in board:
        try:
            ctx["protocol"] = parse_protocol(board["protocolo"]["content"])
        except ValueError:
            pass
    if "triagem" in board and "triagem_independente" in board:
        a = decisions_of(board["triagem"]["content"])
        b = decisions_of(board["triagem_independente"]["content"])
        ctx["kappa"] = cohen_kappa(a, b)
        ctx["primeira"], ctx["segunda"] = a, b
    if "consenso" in board or ("kappa" in ctx and not ctx["kappa"]["divergencias"]):
        ctx["final"], ctx["reasons"] = final_decisions(board)
        ctx["included"] = sorted(k for k, d in ctx["final"].items() if d == "incluir")
    if "qualidade_extracao" in board and "protocol" in ctx:
        report = (board["qualidade_extracao"] or {}).get("validation") or {}
        ctx["below_cut"] = report.get("abaixo_do_corte") or []
        ctx["rows"] = quality_rows(board["qualidade_extracao"]["content"], ctx["protocol"])
    if "final" in ctx and "protocol" in ctx:
        ctx["prisma"] = prisma(ctx["protocol"], ctx["final"], ctx.get("reasons", {}), ctx.get("below_cut", []))
        ctx["eligible"] = ctx["prisma"]["chaves_incluidas"]
    if "sintese" in board:
        ctx["synthesis"] = synthesis(board, project)
    return ctx


def validate(stage_key: str, content: str, ctx: dict, chunks_for_key) -> dict:
    protocol = ctx.get("protocol") or {}
    if stage_key == "protocolo":
        return validate_protocol(content)
    if stage_key in ("triagem", "triagem_independente"):
        return validate_screening(content, protocol, ctx["source_keys"], chunks_for_key)
    if stage_key == "consenso":
        return validate_consensus(content, (ctx.get("kappa") or {}).get("divergencias", []), protocol)
    if stage_key == "qualidade_extracao":
        return validate_quality_extraction(content, protocol, ctx.get("included", []), chunks_for_key)
    if stage_key == "sintese":
        return validate_synthesis(content, protocol, ctx.get("eligible", []))
    raise ValueError("Etapa desconhecida")


def _protocol_brief(p: dict) -> dict:
    keep = ("pergunta", "picoc", "questoes", "inclusao", "exclusao", "qualidade", "escala", "nota_corte",
            "excluir_abaixo_do_corte", "extracao")
    return {k: p.get(k) for k in keep if k in p}


def material(stage_key: str, project: dict, board: dict, references: list[dict], ctx: dict) -> dict:
    base = flow.material("planejamento", project, board, references)
    protocol = _protocol_brief(ctx.get("protocol") or {})
    if stage_key == "protocolo":
        return base
    if stage_key in ("triagem", "triagem_independente"):
        # A segunda triagem é às cegas: nunca recebe as decisões da primeira.
        return {**base, "protocolo": protocol, "fontes_para_triar": ctx.get("source_keys", []),
                "dica": "Use buscar_trechos com zona=metodo, resultados ou limitacoes para achar as partes."}
    if stage_key == "consenso":
        k = ctx.get("kappa") or {}
        return {**base, "protocolo": protocol, "concordancia": {x: k.get(x) for x in ("kappa", "leitura", "n")},
                "divergencias": [{"chave": key, "primeira": ctx.get("primeira", {}).get(key),
                                  "segunda": ctx.get("segunda", {}).get(key)} for key in k.get("divergencias", [])]}
    if stage_key == "qualidade_extracao":
        return {**base, "protocolo": protocol, "estudos_incluidos": ctx.get("included", [])}
    if stage_key == "sintese":
        return {**base, "protocolo": protocol, "amostra_final": ctx.get("eligible", []),
                "matriz": [{"chave": r["chave"], "nota": r["nota"], **r["extracao"]} for r in ctx.get("rows", [])]}
    if stage_key in WRITING:
        written = flow.material(stage_key, project, board, references)
        extra = {"protocolo": protocol, "prisma": {k: v for k, v in (ctx.get("prisma") or {}).items()
                                                  if k != "chaves_incluidas"},
                 "concordancia": {x: (ctx.get("kappa") or {}).get(x) for x in ("kappa", "concordancia", "leitura", "n")}}
        if stage_key == "redacao":
            synth = ctx.get("synthesis") or {}
            extra["sintese"] = {qp: {"texto": v["final"] or v["ia"], "chaves": v["chaves"],
                                     "versao": "pesquisador" if v["final"] else "ia"} for qp, v in synth.items()}
            extra["matriz"] = [{"chave": r["chave"], "nota": r["nota"], **r["extracao"]} for r in ctx.get("rows", [])]
            extra["figura_prisma"] = ("Escreva a linha %PRISMA sozinha no ponto da Metodologia onde a figura do "
                                      "fluxograma deve entrar; o Scriptorium a gera com os números acima.")
        return {**written, **extra}
    raise ValueError("Etapa desconhecida")
