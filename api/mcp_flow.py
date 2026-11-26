"""Fluxo de escrita conduzido pela IA do próprio pesquisador (MCP), sem API paga.

O Scriptorium não chama modelo de linguagem neste modo. Ele guarda as fontes,
entrega os trechos, confere o que cada "cabeça" entrega e só libera a etapa
seguinte quando a anterior passa nas checagens. Quem lê e escreve é a IA que
o pesquisador já usa (Claude, Gemini CLI, ChatGPT...), com a conta dele.

Cabeças:
- redatora: planeja, levanta evidências, redige e reescreve (pode ser a
  mesma conversa);
- revisora e verificadora: entram por um PASSE, numa conversa nova (de
  preferência outra IA), e recebem só o material da etapa, nunca a conversa
  de quem escreveu. Uma cabeça que já entregou uma etapa não pode revisar
  nem verificar.

Este módulo é lógica pura (sem Firestore nem rede), para ser testável.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import secrets
import unicodedata

FLOW_VERSION = "mcp-flow-1"

# ------------------------------------------------------------------ confiança das referências
# Achado do teste de 25/11/2026: uma correspondência errada do OpenAlex (Kitchenham
# virou "Department of Computer Science, 2013") passava como oficial. Agora só é
# "confirmada" a referência que veio de DOI registrado na importação ou que foi
# conferida no próprio documento; busca por título fica "sugerida" até alguém
# conferir. A lista é idêntica em worker/bib_integrity.py (teste impede divergência).
REF_LEVELS = {
    "doi": "confirmada",                    # DOI registrado na importação da fonte
    "corrigida_pelo_texto": "confirmada",   # corrigir_referencia, conferida no documento
    "doi_no_texto": "sugerida",             # DOI achado nas primeiras páginas
    "texto_do_pdf": "sugerida",             # busca por título, confirmada pelo texto
    "titulo_do_pdf": "sugerida",            # busca por título, sem texto para confirmar
    "arquivo": "a_conferir",                # só o que o arquivo diz
}
REF_LEVEL_LABELS = {"confirmada": "confirmada", "sugerida": "sugerida, falta conferir",
                    "a_conferir": "a conferir"}


def ref_level(entry: dict) -> str:
    """confirmada, sugerida ou a_conferir. Origem desconhecida conta como a_conferir."""
    return REF_LEVELS.get((entry or {}).get("how") or "", "a_conferir")


def pending_refs(refs: list[dict]) -> list[dict]:
    """Referências que ainda impedem a versão final do PDF."""
    return [r for r in refs or [] if ref_level(r) != "confirmada"]
TOKEN_PREFIX = "scr_"
MAX_CONTENT = 250_000
MATERIAL_BUDGET = 90_000

# ------------------------------------------------------------------ tokens
def new_token() -> tuple[str, str]:
    """Token pessoal mostrado uma única vez; só o hash é guardado."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def looks_like_token(token: str) -> bool:
    return bool(re.fullmatch(TOKEN_PREFIX + r"[A-Za-z0-9_-]{40,60}", token or ""))


def new_pass_code() -> str:
    """Código curto e legível para colar numa conversa nova (sem 0/O, 1/I)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


def new_head_id() -> str:
    return "cab_" + secrets.token_hex(8)


# ------------------------------------------------------------------ etapas
TEMPLATES = {
    "abnt-artigo": {
        "nome": "Artigo ABNT (abntex2)",
        "secoes": ["Introdução", "Referencial teórico", "Metodologia", "Resultados e discussão",
                   "Considerações finais"],
        "resumo": "resumo",
    },
    "artigo-simples": {
        "nome": "Artigo simples (article)",
        "secoes": ["Introdução", "Trabalhos relacionados", "Método", "Resultados", "Discussão",
                   "Conclusão"],
        "resumo": "abstract",
    },
}

COMMON_RULES = (
    "Regras do Scriptorium, valem para todas as etapas:\n"
    "- Use somente as fontes do projeto. Para ler, chame buscar_trechos e ler_trecho.\n"
    "- Cite apenas com as chaves de referencias_do_projeto; nunca invente autor, ano, título ou página.\n"
    "- Quando as fontes não sustentarem algo, diga isso no texto em vez de completar de memória.\n"
    "- Referência com confianca sugerida ou a_conferir, ou com título, autor ou ano errados: confirme ou "
    "corrija com corrigir_referencia, lendo a capa da fonte. Sem isso o PDF só sai como rascunho.\n"
    "- Toda citação direta (entre aspas) precisa estar, palavra por palavra, na fonte citada no mesmo "
    "parágrafo; marque com \"tradução nossa\" a citação que você traduziu. Prefira paráfrase.\n"
    "- Entregue o resultado chamando entregar_etapa. Se a entrega voltar com erros, corrija e entregue de novo.\n"
)

STAGES = [
    {
        "key": "planejamento", "titulo": "Planejamento", "cabeca": "redatora", "nova_conversa": False,
        "formato": "markdown", "min": 600,
        "instrucoes": (
            "Você é a cabeça PLANEJADORA. Leia as fichas das fontes (ficha_da_fonte) e faça buscas "
            "exploratórias. Entregue, em Markdown, o plano do texto: a pergunta reformulada, o argumento "
            "central e, para cada seção do modelo, o que ela vai sustentar e quais chaves de referência "
            "vai usar. Termine com uma lista de lacunas: o que as fontes NÃO cobrem."),
    },
    {
        "key": "evidencias", "titulo": "Levantamento de evidências", "cabeca": "redatora",
        "nova_conversa": False, "formato": "json", "min": 200,
        "instrucoes": (
            "Você é a cabeça LEITORA. Para cada afirmação que o texto vai fazer, encontre o trecho que a "
            "sustenta (buscar_trechos, depois ler_trecho). Entregue um JSON: lista de objetos com "
            "\"afirmacao\", \"chave\", \"chunk_id\" e \"citacao_literal\" (20 a 600 caracteres copiados "
            "EXATAMENTE do trecho, sem reescrever). O Scriptorium confere cada citação no texto da fonte; "
            "as que não baterem voltam para correção. Mínimo de 8 evidências."),
    },
    {
        "key": "redacao", "titulo": "Redação", "cabeca": "redatora", "nova_conversa": False,
        "formato": "latex", "min": 6000,
        "instrucoes": (
            "Você é a cabeça REDATORA. Escreva o corpo do texto em LaTeX a partir do plano e das "
            "evidências aceitas: comece pelo ambiente de resumo indicado e siga com \\section{...} para "
            "cada seção do modelo. Cite com \\cite{chave} (ou \\citeonline{chave} no modelo ABNT). "
            "Entregue só o corpo: sem preâmbulo, \\documentclass, \\usepackage, \\begin{document}, "
            "\\bibliography, macros (\\def, \\newcommand) nem \\input/\\include; o Scriptorium monta o "
            "documento e a bibliografia."),
    },
    {
        "key": "revisao", "titulo": "Revisão independente", "cabeca": "revisora", "nova_conversa": True,
        "formato": "json", "min": 300,
        "instrucoes": (
            "Você é a cabeça REVISORA, independente de quem escreveu: não teve acesso à conversa da "
            "redação e deve ser cética. Leia o rascunho e confira nas fontes (buscar_trechos) as "
            "afirmações mais importantes. Entregue um JSON com \"nota_geral\" (0 a 10), \"resumo\" e "
            "\"problemas\": lista de objetos com \"trecho\" (cópia curta do rascunho), \"tipo\" "
            "(sem_suporte, citacao_errada, logica, lacuna, clareza, estrutura), \"gravidade\" (alta, "
            "media, baixa) e \"sugestao\". Aponte problemas reais; não elogie por elogiar."),
    },
    {
        "key": "reescrita", "titulo": "Reescrita", "cabeca": "redatora", "nova_conversa": False,
        "formato": "latex", "min": 6000,
        "instrucoes": (
            "Você é a cabeça REDATORA de novo. Reescreva o corpo em LaTeX tratando cada problema da "
            "revisão (corrija ou, se discordar, justifique num comentário LaTeX % no ponto). Mesmas "
            "regras de formato da redação."),
    },
    {
        "key": "verificacao", "titulo": "Verificação de afirmações", "cabeca": "verificadora",
        "nova_conversa": True, "formato": "json", "min": 200,
        "instrucoes": (
            "Você é a cabeça VERIFICADORA, independente da redação e da revisão. Escolha as afirmações "
            "do texto final que dependem de fontes (no mínimo 10, priorizando as citadas) e confira "
            "cada uma. Entregue um JSON: lista de objetos com \"afirmacao\", \"chave\", \"veredito\" "
            "(sustentada, parcial, sem_suporte), \"chunk_id\" e \"citacao_literal\" do trecho da fonte "
            "(obrigatória quando o veredito não for sem_suporte). O Scriptorium confere as citações."),
    },
]
STAGE_KEYS = [s["key"] for s in STAGES]
BY_KEY = {s["key"]: s for s in STAGES}


MODES = ("artigo", "revisao_sistematica")


def stages_for(mode: str = "artigo") -> list[dict]:
    if mode == "revisao_sistematica":
        import mcp_review
        return mcp_review.stages()
    return STAGES


def stage(key: str) -> dict:
    if key in BY_KEY:
        return BY_KEY[key]
    import mcp_review
    if key in mcp_review.BY_KEY:
        return mcp_review.BY_KEY[key]
    raise ValueError("Etapa desconhecida: " + str(key))


def next_stage(stages_state: dict, mode: str = "artigo") -> dict | None:
    """Primeira etapa ainda não aceita, na ordem do fluxo do projeto."""
    for s in stages_for(mode):
        if (stages_state.get(s["key"]) or {}).get("status") != "aceita":
            return s
    return None


REOPEN = ("reescrita", "verificacao")


def reopen_rewrite(stages_state: dict) -> dict:
    """Reabre a reescrita e, por consequência, a verificação (o texto vai mudar).

    Serve para corrigir um erro que só aparece na compilação (LaTeX, citação). As
    tentativas anteriores ficam contadas, para as versões gravadas não se sobreporem;
    o passe e a cabeça da verificação antiga deixam de valer.
    """
    if any((stages_state.get(k) or {}).get("status") != "aceita" for k in REOPEN):
        raise ValueError("Só dá para reabrir a reescrita depois que ela e a verificação foram aceitas.")
    out = dict(stages_state)
    for key in REOPEN:
        old = out.get(key) or {}
        out[key] = {"status": "pendente", "attempts": old.get("attempts", 0),
                    "reaberta": int(old.get("reaberta", 0)) + 1, "versao_anterior": old.get("version")}
    return out


# ------------------------------------------------------------------ cabeças
def check_head(stage_def: dict, head: dict, stages_state: dict) -> str | None:
    """Motivo para recusar a entrega desta cabeça, ou None se pode entregar."""
    if not head:
        return "Cabeça desconhecida. Chame proxima_etapa (ou abrir_passe) para receber uma."
    if stage_def["cabeca"] == "redatora":
        if head.get("kind") != "redatora":
            return ("Esta cabeça entrou por passe para revisar ou verificar e não pode escrever. "
                    "Volte à conversa da redação.")
        return None
    if head.get("kind") != stage_def["cabeca"] or head.get("stage") != stage_def["key"]:
        return (f"A etapa {stage_def['titulo']} só aceita a cabeça aberta pelo passe desta etapa, "
                "numa conversa nova.")
    for key, state in stages_state.items():
        if key != stage_def["key"] and (state or {}).get("head", {}).get("id") == head.get("id"):
            return "Esta cabeça já entregou outra etapa e não pode avaliar o próprio trabalho."
    return None


def _family(model: str) -> str:
    text = (model or "").lower()
    for name in ("claude", "gemini", "gpt", "openai", "llama", "mistral", "qwen", "deepseek", "grok",
                 "gemma", "copilot"):
        if name in text:
            return "gpt" if name in ("openai", "copilot") else name
    return text.split()[0] if text.split() else ""


def independence(writer: dict | None, reviewer: dict | None) -> dict:
    """Quão independente é a cabeça avaliadora em relação à redatora."""
    if not writer or not reviewer:
        return {"nivel": "indeterminada", "explicacao": "Faltam dados de uma das cabeças."}
    if writer.get("id") == reviewer.get("id"):
        return {"nivel": "mesma_cabeca", "explicacao": "A mesma cabeça escreveu e avaliou."}
    fw, fr = _family(writer.get("model", "")), _family(reviewer.get("model", ""))
    cw, cr = (writer.get("client") or "").lower(), (reviewer.get("client") or "").lower()
    if (fw and fr and fw != fr) or (cw and cr and cw != cr):
        return {"nivel": "outra_ia", "explicacao":
                f"Avaliada por outra IA ({reviewer.get('model') or reviewer.get('client')})."}
    return {"nivel": "outra_conversa", "explicacao":
            "Conversa nova com a mesma IA: sem a memória da redação, mas com o mesmo modelo."}


# ------------------------------------------------------------------ texto
def normalize(text: str) -> str:
    """Normalização tolerante a quebras de linha, hifenização e pontuação do PDF."""
    text = unicodedata.normalize("NFKC", text or "").replace("\u00ad", "")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def quote_in(quote: str, text: str) -> bool:
    q = normalize(quote)
    return len(q) >= 15 and q in normalize(text)


def parse_json(content: str):
    raw = (content or "").strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.S)
    if fence:
        raw = fence.group(1)
    return json.loads(raw)


CITE = re.compile(r"\\(?:cite|citep|citet|citeonline|citealp|citealt|citeauthor|citeyear|"
                  r"apud|citeyearpar)\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}")
# O LaTeX entregue pela IA é compilado no worker: nada que leia arquivos, escreva
# no disco, rode comandos ou redefina macros (inclusive por \csname e ^^).
FORBIDDEN = re.compile(
    r"\\(?:write\d*|immediate|openin|openout|closein|closeout|read|readline|input|include|"
    r"includeonly|InputIfFileExists|usepackage|RequirePackage|documentclass|catcode|special|"
    r"directlua|luaexec|latelua|csname|expandafter|def|edef|gdef|xdef|let|futurelet|newcommand|"
    r"renewcommand|providecommand|DeclareRobustCommand|newenvironment|renewenvironment|"
    r"bibliography|bibliographystyle|addbibresource|includegraphics|verbatiminput|"
    r"lstinputlisting|pdffiledump|pdfximage|pdfobj|scantokens|everyeof|endinput|"
    r"newread|newwrite|loop|jobname|shipout|output|end\s*\{\s*document\s*\}|"
    r"begin\s*\{\s*document\s*\})(?![A-Za-z])")


def cited_keys(latex: str) -> list[str]:
    out = []
    for group in CITE.findall(latex or ""):
        out += [k.strip() for k in group.split(",") if k.strip()]
    return out


def _report(ok: bool, errors: list[str], **extra) -> dict:
    return {"ok": ok and not errors, "erros": errors[:40], **extra}


def _size_errors(content: str, minimum: int) -> list[str]:
    if len(content or "") > MAX_CONTENT:
        return [f"Entrega grande demais ({len(content)} caracteres; máximo {MAX_CONTENT})."]
    if len((content or "").strip()) < minimum:
        return [f"Entrega curta demais para esta etapa (mínimo de {minimum} caracteres)."]
    return []


def validate_plan(content: str, bib_keys: set[str]) -> dict:
    errors = _size_errors(content, BY_KEY["planejamento"]["min"])
    used = sorted(k for k in bib_keys if k in (content or ""))
    if bib_keys and not used:
        errors.append("O plano não usa nenhuma chave de referencias_do_projeto.")
    return _report(True, errors, chaves_usadas=used)


def _quote_check(entries: list, bib_keys: set[str], chunks_for_key, require_quote) -> tuple[list, list]:
    """chunks_for_key(chave) -> lista de {chunk_id, text}. Devolve (resultados, erros)."""
    results, errors = [], []
    for n, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            errors.append(f"Item {n}: deveria ser um objeto JSON.")
            continue
        key = str(entry.get("chave", "")).strip()
        quote = str(entry.get("citacao_literal", "") or "").strip()
        claim = str(entry.get("afirmacao", "") or "").strip()
        result = {"n": n, "chave": key, "chunk_id": entry.get("chunk_id"), "citacao_conferida": False}
        if not claim:
            errors.append(f"Item {n}: falta a afirmação.")
        if key not in bib_keys:
            errors.append(f"Item {n}: chave '{key}' não está nas referências do projeto.")
            results.append(result)
            continue
        if not require_quote(entry):
            results.append(result)
            continue
        if not 20 <= len(quote) <= 600:
            errors.append(f"Item {n}: a citação literal deve ter de 20 a 600 caracteres.")
            results.append(result)
            continue
        chunks = chunks_for_key(key) or []
        wanted = [c for c in chunks if c.get("chunk_id") == entry.get("chunk_id")]
        found = next((c for c in wanted + chunks if quote_in(quote, c.get("text", ""))), None)
        if found:
            result.update(citacao_conferida=True, chunk_id=found.get("chunk_id"))
        else:
            errors.append(f"Item {n}: a citação literal não foi encontrada na fonte '{key}'. Copie o "
                          "trecho exatamente como está em ler_trecho.")
        results.append(result)
    return results, errors


def validate_evidence(content: str, bib_keys: set[str], chunks_for_key) -> dict:
    errors = _size_errors(content, BY_KEY["evidencias"]["min"])
    try:
        data = parse_json(content)
    except ValueError:
        return _report(False, errors + ["O conteúdo não é um JSON válido."])
    if isinstance(data, dict):
        data = data.get("evidencias") or data.get("itens") or []
    if not isinstance(data, list) or len(data) < 8:
        return _report(False, errors + ["Entregue uma lista JSON com no mínimo 8 evidências."])
    results, problems = _quote_check(data, bib_keys, chunks_for_key, lambda e: True)
    return _report(True, errors + problems, conferidas=sum(r["citacao_conferida"] for r in results),
                   total=len(results), itens=results)


# ------------------------------------------------------------------ citações do texto final
# Achado do teste de 25/11/2026: só as evidências eram conferidas; as citações diretas
# escritas na redação e na reescrita passavam sem conferência. Agora cada trecho entre
# aspas com 4 ou mais palavras é procurado na fonte citada no mesmo parágrafo (termos
# curtos entre aspas, como "nativos digitais", não contam como citação).
QUOTE = re.compile(r"``(.+?)''|\u201c(.+?)\u201d|(?<![\w\\])\"(.+?)\"", re.S)
ELLIPSIS = re.compile(r"\[\s*(?:\.\.\.|\u2026)\s*\]|\(\s*(?:\.\.\.|\u2026)\s*\)|\u2026|\.\.\.")
TRANSLATED = re.compile(r"tradu[cç][aã]o\s+(nossa|livre|minha)|our\s+translation|translated\s+by", re.I)
LATEX_CMD = re.compile(r"\\[A-Za-z]+\*?|[{}~]")


def _plain_quote(text: str) -> str:
    """Tira comandos LaTeX (\\emph, \\%, ~) antes de comparar com a fonte."""
    return LATEX_CMD.sub(" ", (text or "").replace("\\%", "%").replace("\\&", "&"))


def final_quotes(latex: str) -> list[dict]:
    """Citações diretas do corpo, com as chaves citadas no mesmo parágrafo."""
    out = []
    body = re.sub(r"(?m)(?<!\\)%.*$", "", latex or "")  # comentários LaTeX não são texto
    for paragraph in re.split(r"\n\s*\n", body):
        keys = [k.strip() for group in CITE.findall(paragraph) for k in group.split(",") if k.strip()]
        for match in QUOTE.finditer(paragraph):
            raw = next(g for g in match.groups() if g is not None)
            parts = [p for p in ELLIPSIS.split(_plain_quote(raw)) if len(normalize(p)) >= 15]
            if not parts or len(normalize(" ".join(parts)).split()) < 4:
                continue  # termo curto entre aspas ("nativos digitais"), não citação
            after = paragraph[match.end():match.end() + 160]
            out.append({"trecho": " ".join(raw.split())[:160], "partes": parts, "chaves": list(dict.fromkeys(keys)),
                        "traduzida": bool(TRANSLATED.search(after))})
    return out


def check_final_quotes(latex: str, bib_keys: set[str], chunks_for_key) -> tuple[dict, list[str]]:
    """Confere cada citação direta na fonte citada no parágrafo. Devolve (resumo, erros)."""
    quotes = final_quotes(latex)
    errors, checked, translated = [], 0, 0
    for n, q in enumerate(quotes, 1):
        if q["traduzida"]:
            translated += 1
            continue
        keys = [k for k in q["chaves"] if k in bib_keys]
        if not keys:
            errors.append(f"Citação direta {n} (\u201c{q['trecho'][:80]}\u201d) sem \\cite no mesmo parágrafo.")
            continue

        def found_in(key: str) -> bool:
            texts = [c.get("text", "") for c in chunks_for_key(key) or []]
            return all(any(quote_in(part, t) for t in texts) for part in q["partes"])

        if any(found_in(k) for k in keys):
            checked += 1
            continue
        other = next((k for k in sorted(bib_keys) if k not in keys and found_in(k)), None)
        where = (f" O trecho está na fonte '{other}': corrija a chave citada." if other else
                 " Copie o trecho exatamente como está em ler_trecho, ou troque a citação direta por paráfrase.")
        errors.append(f"Citação direta {n} (\u201c{q['trecho'][:80]}\u201d) não foi encontrada em "
                      f"{', '.join(keys)}.{where}")
    summary = {"total": len(quotes), "conferidas": checked, "traduzidas": translated}
    return summary, errors


def validate_latex(content: str, bib_keys: set[str], minimum: int, template: str, chunks_for_key=None) -> dict:
    errors = _size_errors(content, minimum)
    bad = sorted(set(m.group(0) for m in FORBIDDEN.finditer(content or "")))
    if bad:
        errors.append("Comandos não permitidos no corpo: " + ", ".join(bad[:10]) +
                      ". O Scriptorium monta preâmbulo e bibliografia.")
    if "^^" in (content or ""):
        errors.append("Sequências ^^ não são permitidas.")
    sections = len(re.findall(r"\\section\*?\{", content or ""))
    if sections < 3:
        errors.append("O corpo precisa de pelo menos 3 seções (\\section{...}).")
    env = TEMPLATES.get(template, TEMPLATES["abnt-artigo"])["resumo"]
    if not re.search(r"\\begin\{" + env + r"\}", content or ""):
        errors.append(f"Inclua o ambiente \\begin{{{env}}} ... \\end{{{env}}}.")
    keys = cited_keys(content)
    unknown = sorted(set(k for k in keys if k not in bib_keys))
    if unknown:
        errors.append("Chaves citadas que não existem nas referências do projeto: " + ", ".join(unknown[:15]))
    if bib_keys and not keys:
        errors.append("O texto não cita nenhuma fonte do projeto.")
    if (content or "").count("{") != (content or "").count("}"):
        errors.append("Chaves { } desbalanceadas no LaTeX.")
    extra = {}
    if chunks_for_key is not None:
        quotes, problems = check_final_quotes(content, bib_keys, chunks_for_key)
        errors += problems[:20]
        if len(problems) > 20:
            errors.append(f"... e mais {len(problems) - 20} citação(ões) diretas sem conferência.")
        extra["citacoes_texto"] = quotes
    return _report(True, errors, secoes=sections, citacoes=len(keys),
                   fontes_citadas=sorted(set(keys) & bib_keys), **extra)


def validate_review(content: str) -> dict:
    errors = _size_errors(content, BY_KEY["revisao"]["min"])
    try:
        data = parse_json(content)
    except ValueError:
        return _report(False, errors + ["O conteúdo não é um JSON válido."])
    if not isinstance(data, dict):
        return _report(False, errors + ["A revisão deve ser um objeto JSON."])
    problems = data.get("problemas")
    try:
        grade = float(data.get("nota_geral"))
    except (TypeError, ValueError):
        grade = -1
    if not 0 <= grade <= 10:
        errors.append("Informe nota_geral de 0 a 10.")
    if not isinstance(problems, list) or not problems:
        errors.append("Liste os problemas encontrados (problemas: [...]).")
        problems = []
    kinds = {"sem_suporte", "citacao_errada", "logica", "lacuna", "clareza", "estrutura"}
    for n, p in enumerate(problems, 1):
        if not isinstance(p, dict) or p.get("tipo") not in kinds or p.get("gravidade") not in (
                "alta", "media", "baixa") or not str(p.get("sugestao", "")).strip():
            errors.append(f"Problema {n}: precisa de tipo, gravidade (alta, media, baixa) e sugestao.")
    counts = {g: sum(1 for p in problems if isinstance(p, dict) and p.get("gravidade") == g)
              for g in ("alta", "media", "baixa")}
    return _report(True, errors, nota_geral=grade, problemas=counts)


def validate_verification(content: str, bib_keys: set[str], chunks_for_key) -> dict:
    errors = _size_errors(content, BY_KEY["verificacao"]["min"])
    try:
        data = parse_json(content)
    except ValueError:
        return _report(False, errors + ["O conteúdo não é um JSON válido."])
    if isinstance(data, dict):
        data = data.get("verificacoes") or data.get("itens") or []
    if not isinstance(data, list) or len(data) < 10:
        return _report(False, errors + ["Entregue uma lista JSON com no mínimo 10 afirmações verificadas."])
    verdicts = ("sustentada", "parcial", "sem_suporte")
    for n, e in enumerate(data, 1):
        if isinstance(e, dict) and e.get("veredito") not in verdicts:
            errors.append(f"Item {n}: veredito deve ser sustentada, parcial ou sem_suporte.")
    results, problems = _quote_check(
        data, bib_keys, chunks_for_key,
        lambda e: isinstance(e, dict) and e.get("veredito") in ("sustentada", "parcial"))
    tally = {v: sum(1 for e in data if isinstance(e, dict) and e.get("veredito") == v) for v in verdicts}
    return _report(True, errors + problems, vereditos=tally, itens=results)


def validate(stage_key: str, content: str, *, bib_keys: set[str], chunks_for_key, template: str) -> dict:
    if stage_key == "planejamento":
        return validate_plan(content, bib_keys)
    if stage_key == "evidencias":
        return validate_evidence(content, bib_keys, chunks_for_key)
    if stage_key in ("redacao", "reescrita"):
        return validate_latex(content, bib_keys, BY_KEY[stage_key]["min"], template, chunks_for_key)
    if stage_key == "revisao":
        return validate_review(content)
    if stage_key == "verificacao":
        return validate_verification(content, bib_keys, chunks_for_key)
    raise ValueError("Etapa desconhecida")


# ------------------------------------------------------------------ referências
REF_TYPES = {"article": "journal", "inproceedings": "booktitle", "incollection": "booktitle",
             "phdthesis": "school", "mastersthesis": "school", "book": "publisher",
             "techreport": "institution", "misc": "howpublished"}
REF_ORDER = ("author", "title", "journal", "booktitle", "school", "institution", "publisher",
             "howpublished", "year", "volume", "number", "pages", "doi", "note")


def _has_word(word: str, plain: str) -> bool:
    return len(word) >= 3 and f" {word} " in f" {plain} "


TITLE_SIMILARITY = 0.9


def title_in_text(title: str, first_text: str) -> bool:
    """Título nas primeiras páginas: trecho exato ou uma linha quase idêntica.

    Achado do teste de 25/11/2026: o título de capas e cabeçalhos (guardado pelo
    parser como título de seção, ou quebrado em linhas com hífen) não aparecia como
    texto corrido, e correções verdadeiras eram recusadas. A comparação por linha
    tolera essas diferenças sem aceitar um título que o documento não mostra.
    """
    wanted = normalize(title)
    if wanted in normalize(first_text):
        return True
    lines = [normalize(l) for l in (first_text or "").splitlines()]
    lines = [l for l in lines if l]
    # Títulos longos costumam ocupar 2 ou 3 linhas na capa.
    windows = lines + [" ".join(lines[i:i + 2]) for i in range(len(lines))] + \
        [" ".join(lines[i:i + 3]) for i in range(len(lines))]
    return any(abs(len(w) - len(wanted)) <= max(8, len(wanted) // 5) and
               difflib.SequenceMatcher(None, w, wanted).ratio() >= TITLE_SIMILARITY for w in windows)


def check_reference_fix(fix: dict, first_text: str, full_text: str) -> tuple[dict, list[str]]:
    """Confere uma correção de referência proposta pela IA no próprio texto da fonte.

    Título (exato ou quase idêntico a uma linha) e sobrenomes precisam estar nas
    primeiras páginas; ano, veículo e DOI, em algum lugar do documento. Nada que o
    documento não mostre entra.
    """
    errors = []
    first, full = normalize(first_text), normalize(full_text)
    for name, value in fix.items():
        values = value if isinstance(value, list) else [value]
        if any(re.search(r"[{}\\@]", str(v or "")) for v in values):
            errors.append(f"{name}: não use chaves, barra invertida nem @.")
    kind = fix.get("tipo") or "misc"
    if kind not in REF_TYPES:
        errors.append("tipo inválido. Use: " + ", ".join(REF_TYPES))
    title = " ".join(str(fix.get("titulo") or "").split())
    if len(normalize(title)) < 10:
        errors.append("Informe o título completo (mínimo de 10 caracteres).")
    elif not title_in_text(title, first_text):
        errors.append("O título não aparece nas primeiras páginas da fonte. Copie-o como está no documento.")
    authors = [" ".join(str(a).split()) for a in (fix.get("autores") or []) if str(a).strip()]
    if not authors:
        errors.append("Informe ao menos um autor no formato 'Sobrenome, Nome'.")
    for author in authors[:20]:
        last = normalize(author.split(",")[0]).split()
        if not last or not _has_word(last[-1], first):
            errors.append(f"O sobrenome de '{author}' não aparece nas primeiras páginas da fonte.")
    year = str(fix.get("ano") or "").strip()
    if not re.fullmatch(r"(1[5-9]|20)\d{2}", year):
        errors.append("Ano inválido.")
    elif not _has_word(year, full) and year not in full.split():
        errors.append(f"O ano {year} não aparece no documento.")
    venue = " ".join(str(fix.get("veiculo") or "").split())
    if venue and normalize(venue) not in full:
        errors.append("O veículo (revista, evento, instituição ou editora) não aparece no documento. "
                      "Escreva-o como está impresso, ou deixe em branco.")
    doi = str(fix.get("doi") or "").strip().lower()
    if doi and (not re.fullmatch(r"10\.\d{4,9}/\S+", doi) or normalize(doi) not in full):
        errors.append("O DOI não aparece no documento. Deixe em branco se a fonte não o imprime.")
    if errors:
        return {}, errors
    fields = {"author": " and ".join(authors[:20]), "title": title, "year": year}
    if venue:
        fields[REF_TYPES[kind]] = venue
    if doi:
        fields["doi"] = doi
    return fields, []


def render_reference(entry: dict) -> str:
    fields = entry["fields"]
    names = [k for k in REF_ORDER if fields.get(k)] + sorted(
        k for k in fields if k not in REF_ORDER and fields.get(k))
    body = ",\n".join(f"  {k} = {{{fields[k]}}}" for k in names)
    return f"@{entry['type']}{{{entry['key']},\n{body}\n}}\n"


# ------------------------------------------------------------------ material
def _clip(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + f"\n[... cortado: {len(text) - limit} caracteres]"


def accepted_evidence(content: str, report: dict) -> list:
    """Só as evidências com citação conferida seguem para a redação."""
    try:
        data = parse_json(content)
    except ValueError:
        return []
    if isinstance(data, dict):
        data = data.get("evidencias") or data.get("itens") or []
    ok = {r["n"] for r in (report or {}).get("itens", []) if r.get("citacao_conferida")}
    return [e for n, e in enumerate(data, 1) if n in ok]


def material(stage_key: str, project: dict, board: dict, references: list[dict]) -> dict:
    """O que cada cabeça recebe. board: etapa -> {"content", "validation"}."""
    template = TEMPLATES.get(project.get("template"), TEMPLATES["abnt-artigo"])
    refs = [{"chave": r["key"], "fonte": r.get("source_id"), "titulo": (r.get("fields") or {}).get("title", ""),
             "ano": (r.get("fields") or {}).get("year", ""),
             "confianca": ref_level(r)} for r in references]
    base = {
        "projeto": project["id"], "titulo": project.get("title", ""), "pergunta": project.get("question", ""),
        "idioma": project.get("language", "pt-BR"), "modelo": template["nome"],
        "secoes_do_modelo": template["secoes"], "ambiente_de_resumo": template["resumo"],
        "referencias": refs,
    }
    get = lambda key: (board.get(key) or {}).get("content", "")
    if stage_key == "planejamento":
        return base
    if stage_key == "evidencias":
        return {**base, "plano": _clip(get("planejamento"), 30_000)}
    if stage_key == "redacao":
        evidence = accepted_evidence(get("evidencias"), (board.get("evidencias") or {}).get("validation"))
        while evidence and len(json.dumps(evidence, ensure_ascii=False)) > 50_000:
            evidence = evidence[:-1]
        return {**base, "plano": _clip(get("planejamento"), 30_000), "evidencias_conferidas": evidence}
    if stage_key == "revisao":
        return {**base, "rascunho": _clip(get("redacao"), MATERIAL_BUDGET)}
    if stage_key == "reescrita":
        return {**base, "rascunho": _clip(get("redacao"), 70_000), "revisao": _clip(get("revisao"), 30_000)}
    if stage_key == "verificacao":
        return {**base, "texto_final": _clip(get("reescrita") or get("redacao"), MATERIAL_BUDGET)}
    raise ValueError("Etapa desconhecida")


def brief(stage_def: dict, language: str) -> str:
    lang = "português do Brasil" if language == "pt-BR" else "inglês"
    return (f"{stage_def['instrucoes']}\n\nIdioma do texto: {lang}. Formato da entrega: "
            f"{stage_def['formato']}.\n\n{COMMON_RULES}")
