"""Trabalhos do modo sem API (MCP) no worker. Nenhum deles usa modelo de linguagem.

- mcp_prepare: lê as fontes do projeto (documento estruturado + trechos, no
  mesmo cache privado das pesquisas) e monta o BibTeX oficial (DOI/OpenAlex ou
  título do PDF; sem correspondência segura, entrada mínima marcada "a conferir").
- mcp_compile: junta o corpo aceito no quadro com o preâmbulo do modelo e a
  bibliografia oficial e compila com o TeX em modo restrito (sem shell, sem
  leitura fora do diretório), além de gerar o relatório de proveniência
  (qual IA fez cada etapa e com que independência). Versão final só com todas as
  referências confirmadas e sem erro de LaTeX; senão sai RASCUNHO marcado.
- mcp_refs: refaz só a bibliografia de um projeto existente, mantendo as chaves já
  citadas e as correções feitas pela IA no próprio documento.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import bib_integrity

try:  # Na imagem, formatos/ é copiado para /app/formatos no deploy.
    import formatos
except ModuleNotFoundError:  # Rodando direto do repositório (testes, desenvolvimento).
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    import formatos

# Mesma lista do api/mcp_flow.py (tests/test_mcp_jobs.py impede divergência):
# a API já recusa estes comandos; aqui é a segunda barreira antes do TeX.
FORBIDDEN = re.compile(
    r"\\(?:write\d*|immediate|openin|openout|closein|closeout|read|readline|input|include|"
    r"includeonly|InputIfFileExists|usepackage|RequirePackage|documentclass|catcode|special|"
    r"directlua|luaexec|latelua|csname|expandafter|def|edef|gdef|xdef|let|futurelet|newcommand|"
    r"renewcommand|providecommand|DeclareRobustCommand|newenvironment|renewenvironment|"
    r"bibliography|bibliographystyle|addbibresource|printbibliography|includegraphics|verbatiminput|"
    r"lstinputlisting|pdffiledump|pdfximage|pdfobj|scantokens|everyeof|endinput|"
    r"newread|newwrite|loop|jobname|shipout|output|end\s*\{\s*document\s*\}|"
    r"begin\s*\{\s*document\s*\})(?![A-Za-z])")

MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
          "outubro", "novembro", "dezembro"]

# Preâmbulos, estrutura e fecho de cada norma ficam em formatos/<id>/ (ver formatos/README.md).


def latex_escape(text: str) -> str:
    table = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#",
             "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(table.get(c, c) for c in (text or ""))


def run_date(language: str, today: datetime | None = None) -> str:
    today = today or datetime.now(timezone.utc)
    if language == "en":
        return today.strftime("%B %d, %Y").replace(" 0", " ")
    return f"{today.day} de {MONTHS[today.month - 1]} de {today.year}"


LABELS = {
    "pt-BR": {"ident": "Registros identificados", "dup": "Removidos antes da triagem: duplicados",
              "screen": "Registros triados", "title": "Excluídos por título e resumo",
              "sought": "Relatórios buscados para recuperação", "lost": "Relatórios não recuperados",
              "assessed": "Relatórios avaliados para elegibilidade", "excl": "Relatórios excluídos",
              "quality": "Excluídos abaixo da nota de corte de qualidade", "included": "Estudos incluídos na revisão",
              "outside": "Referências teóricas ou metodológicas fora da triagem",
              "caption": "Fluxograma PRISMA 2020 da seleção dos estudos",
              "source": "Fonte: elaborado pelo autor, com as decisões registradas no Scriptorium."},
    "en": {"ident": "Records identified", "dup": "Removed before screening: duplicates",
           "screen": "Records screened", "title": "Excluded by title and abstract",
           "sought": "Reports sought for retrieval", "lost": "Reports not retrieved",
           "assessed": "Reports assessed for eligibility", "excl": "Reports excluded",
           "quality": "Excluded below the quality cut-off", "included": "Studies included in the review",
           "outside": "Theoretical or methodological references outside screening",
           "caption": "PRISMA 2020 flow diagram of study selection",
           "source": "Source: prepared by the author from the decisions recorded in Scriptorium."},
}


def prisma_figure(prisma: dict, language: str = "pt-BR") -> str:
    """Fluxograma PRISMA 2020 em LaTeX simples (caixas e setas, sem TikZ)."""
    t = LABELS.get(language, LABELS["pt-BR"])

    def box(text: str) -> str:
        return r"\fbox{\parbox{0.42\textwidth}{\centering " + text + "}}"

    def n(label: str, value) -> str:
        return label + r"\\(n = " + str(int(value or 0)) + ")"

    rows = []
    if prisma.get("bases"):
        bases = "; ".join(f"{latex_escape(b['nome'])}: {int(b['registros'])}" for b in prisma["bases"])
        rows.append((n(t["ident"], prisma["identificados"]) + r"\\\footnotesize " + bases,
                     n(t["dup"], prisma.get("duplicados"))))
        rows.append((n(t["screen"], prisma.get("triados")), n(t["title"], prisma.get("excluidos_titulo_resumo"))))
        rows.append((n(t["sought"], prisma.get("procurados")), n(t["lost"], prisma.get("nao_recuperados"))))
    reasons = "; ".join(f"{latex_escape(k)}: {v}" for k, v in sorted((prisma.get("motivos") or {}).items()))
    rows.append((n(t["assessed"], prisma.get("avaliados")),
                 n(t["excl"], prisma.get("excluidos_elegibilidade")) + (r"\\\footnotesize " + reasons if reasons else "")))
    if prisma.get("excluidos_qualidade"):
        rows.append(("", n(t["quality"], prisma["excluidos_qualidade"])))
    outside = len(prisma.get("fora_da_triagem") or [])
    rows.append((n(t["included"], prisma.get("incluidos")), n(t["outside"], outside) if outside else ""))
    lines = []
    for i, (left, right) in enumerate(rows):
        lines.append((box(left) if left else "") + " & " + (box(right) if right else "") + r" \\[2pt]")
        if i < len(rows) - 1:
            lines.append(r"$\downarrow$ & \\[2pt]")
    return ("\n" + r"\begin{figure}[htbp]" + "\n" + r"\centering\small" + "\n"
            + r"\begin{tabular}{@{}>{\centering\arraybackslash}p{0.46\textwidth}>{\centering\arraybackslash}p{0.46\textwidth}@{}}"
            + "\n" + "\n".join(lines) + "\n" + r"\end{tabular}" + "\n"
            + r"\caption{" + t["caption"] + "}\n" + r"\label{fig:prisma}" + "\n"
            + r"\par\footnotesize " + t["source"] + "\n" + r"\end{figure}" + "\n")


def place_prisma(body: str, figure: str) -> str:
    marker = re.compile(r"^[ \t]*%[ \t]*PRISMA[ \t]*$", re.M | re.I)
    if marker.search(body):
        return marker.sub(lambda m: figure, body, count=1)
    results = re.search(r"\\section\*?\{(Resultados|Results)", body)
    if results:
        return body[:results.start()] + figure + "\n" + body[results.start():]
    return body + "\n" + figure


def draft_banner(reasons: list[str], language: str = "pt-BR") -> str:
    """Aviso no topo do rascunho: o PDF não pode passar por versão final."""
    head = "RASCUNHO" if language != "en" else "DRAFT"
    lead = ("Não é a versão final do Scriptorium." if language != "en" else
            "This is not the final Scriptorium version.")
    items = " ".join(latex_escape(r) for r in reasons[:4])
    return ("\\begin{center}\\fbox{\\parbox{0.92\\textwidth}{\\centering\\textbf{" + head + "}: " +
            latex_escape(lead) + "\\\\ \\small " + items + "}}\\end{center}\n")


def assemble(project: dict, body: str, today: datetime | None = None, draft: list[str] | None = None) -> str:
    """draft: motivos do rascunho; com motivos, título e topo do PDF saem marcados."""
    if FORBIDDEN.search(body or "") or "^^" in (body or ""):
        raise ValueError("Corpo com comandos não permitidos")
    if project.get("tipo") == "revisao_sistematica" and project.get("prisma"):
        body = place_prisma(body, prisma_figure(project["prisma"], project.get("language", "pt-BR")))
    title = project.get("title", "")
    if draft:
        title = ("RASCUNHO: " if project.get("language") != "en" else "DRAFT: ") + title
        body = draft_banner(draft, project.get("language", "pt-BR")) + (body or "")
    fmt = formatos.obter(project.get("template"))
    lat, language = fmt["latex"], project.get("language", "pt-BR")
    values = {**formatos.textos(fmt["id"], language),
              "title": latex_escape(title),
              "author": "Autoria a preencher pelo pesquisador",
              "date": run_date(language, today),
              "babel": "english" if language == "en" else "brazil",
              "work_type": lat.get("tipo_trabalho") or "Dissertação de Mestrado"}
    text = body.strip()
    if fmt["estrutura"].get("usa_capitulos") and "\\chapter" not in text:
        # Se a IA usou só \section{...} sem \chapter{...}, promove para capítulos.
        text = re.sub(r"\\subsection(\*?\{)", r"\\section\1",
                      re.sub(r"\\section(\*?\{)", r"\\chapter\1", text))
    after = formatos.preencher(lat.get("apos_resumo") or "", values)
    if after:
        end_abstract = "\\end{" + fmt["estrutura"]["resumo"] + "}"
        if end_abstract in text:
            text = text.replace(end_abstract, end_abstract + "\n" + after, 1)
        else:
            text = after + "\n" + text
    return formatos.preambulo(fmt["id"], values) + text + "\n\n" + lat["fecho"] + "\n\\end{document}\n"


def tex_env() -> dict:
    """TeX restrito: sem \\write18 e sem ler ou escrever fora do diretório de trabalho."""
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TEXMFHOME")}
    env.update(openin_any="p", openout_any="p", shell_escape="f")
    return env


def bib_engine(tex: str) -> str:
    """biber para as normas com biblatex (ex.: APA 7); bibtex para abnTeX2 e natbib."""
    return "biber" if re.search(r"backend\s*=\s*biber", tex or "") else "bibtex"


def compile_tex(workdir: Path, tex: str, name: str = "scriptorium", timeout: int = 120) -> tuple[Path | None, dict]:
    (workdir / f"{name}.tex").write_text(tex, encoding="utf-8")
    steps = [["pdflatex", "-no-shell-escape", "-interaction=nonstopmode", f"{name}.tex"],
             [bib_engine(tex), name],
             ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode", f"{name}.tex"],
             ["pdflatex", "-no-shell-escape", "-interaction=nonstopmode", f"{name}.tex"]]
    for command in steps:
        try:
            subprocess.run(command, cwd=str(workdir), capture_output=True, timeout=timeout, check=False,
                           env=tex_env())
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, {"status": "falhou", "motivo": f"{command[0]}: {type(exc).__name__}"}
    log_path = workdir / f"{name}.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    # bibtex/natbib escrevem `chave'; o biblatex escreve 'chave'.
    report = {"citacoes_indefinidas": len(re.findall(r"Citation [`'][^']+' (?:on page \d+ )?undefined", log)),
              "erros_latex": len(re.findall(r"^! ", log, flags=re.M)), "erros_detalhe": latex_errors(log),
              "log_final": log[-3000:]}
    pdf = workdir / f"{name}.pdf"
    if not pdf.exists() or pdf.stat().st_size < 1000:
        return None, {**report, "status": "falhou", "motivo": "pdflatex não gerou o PDF"}
    return pdf, {**report, "status": "ok"}


def latex_errors(log: str, limit: int = 5) -> list[str]:
    """As linhas "! ..." do log com a linha do .tex onde o erro aconteceu (l.123 ...)."""
    out, lines = [], (log or "").splitlines()
    for n, line in enumerate(lines):
        if line.startswith("! "):
            where = next((l.strip() for l in lines[n + 1:n + 8] if re.match(r"l\.\d+", l.strip())), "")
            out.append((line[2:].strip() + (f" ({where[:120]})" if where else ""))[:200])
            if len(out) >= limit:
                break
    return out


def text_quality_metrics(latex: str, bib_keys: list[str]) -> dict:
    """Item 15: indicadores objetivos sem IA (proporção de citações diretas, seções curtas, uso das fontes)."""
    body = re.sub(r"(?m)(?<!\\)%.*$", "", latex or "")
    plain_text = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", " ", body)
    words = len(re.findall(r"[A-Za-zÀ-ÿ0-9]+", plain_text))
    quotes = re.findall(r"``(.+?)''|\u201c(.+?)\u201d|(?<![\w\\])\"(.+?)\"", body, flags=re.S)
    direct = sum(1 for m in quotes if len(re.findall(r"[A-Za-zÀ-ÿ0-9]+", next(g for g in m if g is not None))) >= 4)
    per_1k = round(direct * 1000 / max(words, 1), 1)
    sections = re.split(r"\\section\*?\{([^}]*)\}", body)
    short_sections = []
    for i in range(1, len(sections), 2):
        sec_name = sections[i].strip()
        sec_body = sections[i + 1] if i + 1 < len(sections) else ""
        paras = [p.strip() for p in re.split(r"\n\s*\n", sec_body)
                 if p.strip() and not p.strip().startswith(("\\subsection", "\\begin{figure}", "\\end{"))]
        if len(paras) <= 1:
            short_sections.append(sec_name)
    counts = {k: 0 for k in bib_keys}
    for group in re.findall(r"\\(?:cite|citep|citet|citeonline|citealp|citealt|citeauthor|citeyear|"
                            r"parencite|textcite|Parencite|Textcite|autocite|"
                            r"apud|citeyearpar)\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}", body):
        for k in group.split(","):
            k = k.strip()
            if k in counts:
                counts[k] += 1
    return {
        "palavras": words,
        "citacoes_diretas": direct,
        "citacoes_diretas_por_mil_palavras": per_1k,
        "excesso_citacao_direta": per_1k > 8.0,
        "secoes_um_paragrafo": short_sections,
        "citacoes_por_fonte": counts,
        "fontes_nao_citadas": sorted(k for k, c in counts.items() if c == 0),
        "fontes_citadas_uma_vez": sorted(k for k, c in counts.items() if c == 1),
    }


def pending_refs(refs: list[dict]) -> list[dict]:
    return [r for r in refs or [] if bib_integrity.ref_level(r) != "confirmada"]


def provenance(project: dict, refs: list[dict], manifest: list[dict]) -> dict:
    """Quem fez cada etapa, com que independência, e o que foi conferido."""
    stages = project.get("stages") or {}
    steps = []
    for key, state in stages.items():
        head = state.get("head") or {}
        steps.append({"etapa": key, "versao": state.get("version"), "tentativas": state.get("attempts"),
                      "aceita_em": state.get("accepted_at"), "ia_declarada": head.get("model", ""),
                      "cliente": head.get("client", ""), "cabeca": head.get("id"),
                      "papel": head.get("kind"), "independencia": state.get("independencia"),
                      "conferencia": state.get("summary")})
    order = ["planejamento", "evidencias", "redacao", "revisao", "reescrita", "verificacao"]
    steps.sort(key=lambda s: order.index(s["etapa"]) if s["etapa"] in order else 99)
    ais = sorted({s["ia_declarada"] or s["cliente"] for s in steps if s["ia_declarada"] or s["cliente"]})
    return {
        "schema": "scriptorium.mcp_provenance/1", "projeto": project["id"], "titulo": project.get("title"),
        "modo": "sem API: IA do próprio pesquisador via MCP", "fluxo": project.get("flow_version"),
        "etapas": steps, "ias_usadas": ais,
        "fontes": [{"chave": m.get("key"), "nome": m.get("name"), "trechos": m.get("chunks")} for m in manifest],
        "referencias_a_conferir": [r["key"] for r in pending_refs(refs)],
        "referencias": [{"chave": r.get("key"), "confianca": bib_integrity.ref_level(r), "origem": r.get("how")}
                        for r in refs],
        "revisao_sistematica": ({"prisma": project.get("prisma"), "concordancia": project.get("concordancia"),
                                 "sintese_editada_pelo_pesquisador": sorted((project.get("sintese_final") or {}).keys())}
                                if project.get("tipo") == "revisao_sistematica" else None),
        "declaracao_sugerida": (
            "Texto produzido com apoio de IA generativa (" + ", ".join(ais) + ") conduzida pelo "
            "pesquisador no Scriptorium, em etapas separadas de planejamento, levantamento de "
            "evidências, redação, revisão independente, reescrita e verificação. As citações literais "
            "foram conferidas automaticamente nas fontes; o conteúdo final é de responsabilidade do autor."),
    }


# ---------------------------------------------------------------- trabalhos
def _project(db, data: dict, owner_uid: str):
    pid = data.get("mcp_project_id") or ""
    if not re.fullmatch(r"[0-9a-f]{32}", pid):
        raise ValueError("Projeto MCP inválido")
    ref = db.collection("mcp_projects").document(pid)
    snap = ref.get()
    project = snap.to_dict() if snap.exists else None
    if not project or project.get("owner_uid") != owner_uid:
        raise ValueError("Projeto MCP inválido")
    return ref, project


def _load_library_cards(db, owner_uid: str, sources: list[dict]) -> dict[str, dict]:
    """Item 6: carrega fichas bibliográficas já confirmadas na biblioteca da conta."""
    cards = {}
    for source in sources:
        sid = source.get("id")
        if not sid:
            continue
        try:
            snap = db.collection("library_items").document(sid).get()
            rec = snap.to_dict() if snap.exists else None
            if rec and rec.get("owner_uid") == owner_uid and isinstance(rec.get("bib_entry"), dict):
                cards[sid] = rec["bib_entry"]
        except Exception:
            continue
    return cards


def _persist_confirmed_cards(db, owner_uid: str, entries: list[dict]) -> None:
    """Salva fichas confirmadas (ex.: DOI ou 2 fontes concordantes) de volta na biblioteca."""
    now = datetime.now(timezone.utc).isoformat()
    for entry in entries:
        sid = entry.get("source_id")
        if not sid or bib_integrity.ref_level(entry) != "confirmada":
            continue
        if entry.get("how") == "ficha_da_biblioteca":
            continue
        try:
            doc_ref = db.collection("library_items").document(sid)
            snap = doc_ref.get()
            rec = snap.to_dict() if snap.exists else None
            if not rec or rec.get("owner_uid") != owner_uid:
                continue
            existing = rec.get("bib_entry") or {}
            if bib_integrity.ref_level(existing) == "confirmada":
                continue
            doc_ref.update({"bib_entry": {
                "type": entry.get("type", "misc"), "key": entry.get("key", ""),
                "fields": dict(entry.get("fields") or {}), "how": entry.get("how"),
                "updated_at": now,
            }})
        except Exception:
            continue


def prepare(data: dict, *, db, bucket, owner_uid: str, cache, get_json, update, derive, metadata,
            crossref_get=None, oasisbr_get=None) -> dict:
    """derive(entry, fetch, cache) -> (payload, status); metadata(entry, fetch, cache) -> dict."""
    from source_materials import derived_key
    ref, project = _project(db, data, owner_uid)
    sources = data.get("sources") or []
    if any(not str(s.get("object_path", "")).startswith(f"library/{owner_uid}/{s.get('id', '')}/")
           for s in sources):
        raise ValueError("Referência inválida na biblioteca desta conta")
    update(status="running", stage="Lendo as fontes do projeto",
           started_at=datetime.now(timezone.utc).isoformat())
    fetch = lambda path: bucket.blob(path).download_as_bytes()  # noqa: E731
    manifest, failures, ok, texts = [], [], [], {}
    for source in sources:
        try:
            payload, _ = derive(source, fetch, cache)
            texts[source["id"]] = bib_integrity.first_pages_text(payload)
            path = f"library/{owner_uid}/derived/{derived_key(source)}.json"
            if not bucket.blob(path).exists():  # cache não gravou: grava aqui para a API ler
                bucket.blob(path).upload_from_string(json.dumps(payload, ensure_ascii=False),
                                                     content_type="application/json")
            document = payload.get("document") or {}
            manifest.append({"id": source["id"], "name": source.get("name"), "format": source.get("format"),
                             "sha256": source.get("sha256"), "derived": path,
                             "chunks": len(payload.get("chunks") or []),
                             "pages": document.get("pages_total"), "warnings": document.get("warnings", [])[:5]})
            ok.append(source)
        except Exception as exc:
            failures.append({"id": source.get("id"), "nome": source.get("name"), "erro": type(exc).__name__})
    update(stage="Montando as referências oficiais")
    meta = {}
    for source in ok:
        try:
            meta[source["id"]] = metadata(source, fetch, cache)
        except Exception:
            meta[source["id"]] = {}
    library_cards = _load_library_cards(db, owner_uid, ok)
    entries = bib_integrity.library_entries(
        ok, get_json, meta, texts, crossref_get=crossref_get, oasisbr_get=oasisbr_get,
        library_cards=library_cards)
    _persist_confirmed_cards(db, owner_uid, entries)
    key_of = {e["source_id"]: e["key"] for e in entries}
    for entry in manifest:
        entry["key"] = key_of.get(entry["id"])
    prefix = f"mcp/{owner_uid}/{project['id']}"
    bucket.blob(prefix + "/references.json").upload_from_string(
        json.dumps(entries, ensure_ascii=False), content_type="application/json")
    bucket.blob(prefix + "/references.bib").upload_from_string(
        "".join(bib_integrity.render(e) for e in entries), content_type="text/plain; charset=utf-8")
    bucket.blob(prefix + "/sources.json").upload_from_string(
        json.dumps(manifest, ensure_ascii=False), content_type="application/json")
    readable = [m for m in manifest if m["chunks"]]
    summary = {"fontes": len(sources), "lidas": len(readable), "trechos": sum(m["chunks"] for m in manifest),
               "falhas": failures, "sem_texto": [m["name"] for m in manifest if not m["chunks"]],
               "referencias_a_conferir": [e["key"] for e in pending_refs(entries)],
               "consultas_openalex": _lookup_summary(entries)}
    status = "pronto" if readable else "falhou_preparo"
    fields = {"status": status, "prepare_summary": summary,
              "updated_at": datetime.now(timezone.utc).isoformat(),
              "error": "" if readable else "Nenhuma fonte com texto extraível (PDF escaneado precisa de OCR)."}
    ref.update(fields)
    update(status="completed", stage="Fontes prontas para a IA do pesquisador",
           finished_at=datetime.now(timezone.utc).isoformat())
    return summary


def _lookup_summary(entries: list[dict]) -> dict:
    """Quantas fontes tiveram a consulta ao OpenAlex recusada (chave ausente, limite...)."""
    statuses = [(e.get("consulta") or {}).get("status", "sem_consulta") for e in entries]
    return {"recusadas": sum(s == "api_recusou" for s in statuses),
            "parciais": sum(s == "parcial" for s in statuses),
            "chave_configurada": bool(os.getenv("OPENALEX_API_KEY", "").strip())}


def compile_project(data: dict, *, db, bucket, owner_uid: str, update, workdir: Path, compiler=compile_tex) -> dict:
    ref, project = _project(db, data, owner_uid)
    stages = project.get("stages") or {}
    final_key = "reescrita" if (stages.get("reescrita") or {}).get("status") == "aceita" else "redacao"
    state = stages.get(final_key) or {}
    if state.get("status") != "aceita":
        raise ValueError("Não há texto aceito para compilar")
    prefix = f"mcp/{owner_uid}/{project['id']}"
    update(status="running", stage="Montando o LaTeX", started_at=datetime.now(timezone.utc).isoformat())
    body = bucket.blob(f"{prefix}/etapas/{final_key}-v{state['version']}.txt").download_as_bytes().decode("utf-8")
    refs = json.loads(bucket.blob(prefix + "/references.json").download_as_bytes())
    manifest = json.loads(bucket.blob(prefix + "/sources.json").download_as_bytes())
    pending = pending_refs(refs)
    reasons = []
    if project.get("compile_rascunho"):
        reasons.append("Rascunho pedido pelo pesquisador.")
    if pending:
        reasons.append(f"{len(pending)} referência(s) ainda não confirmada(s): "
                       + ", ".join(r["key"] for r in pending[:8]) + ".")
    (workdir / "references.bib").write_text("".join(bib_integrity.render(e) for e in refs), encoding="utf-8")
    update(stage="Compilando o PDF")
    pdf, report = compiler(workdir, assemble(project, body, draft=reasons or None))
    problems = []
    if report.get("erros_latex"):
        problems.append(f"{report['erros_latex']} erro(s) de LaTeX.")
    if report.get("citacoes_indefinidas"):
        problems.append(f"{report['citacoes_indefinidas']} citação(ões) sem referência.")
    if pdf and problems and not reasons:
        # Saiu "limpo" de referências, mas com erro na compilação: refaz como rascunho.
        reasons = problems
        pdf, report = compiler(workdir, assemble(project, body, draft=reasons))
    elif problems:
        reasons += problems
    final = bool(pdf) and not reasons
    record = provenance(project, refs, manifest)
    record["correcoes_de_referencias"] = project.get("reference_fixes") or []
    record["qualidade_texto"] = text_quality_metrics(body, [r.get("key") for r in refs if r.get("key")])
    record["compilacao"] = {**{k: v for k, v in report.items() if k != "log_final"},
                            "versao": "final" if final else "rascunho", "motivos": reasons}
    files = []
    uploads = [("scriptorium.tex", workdir / "scriptorium.tex", "text/x-tex"),
               ("references.bib", workdir / "references.bib", "text/x-bibtex")]
    if pdf:
        uploads.append(("scriptorium.pdf", pdf, "application/pdf"))
    for name, path, mime in uploads:
        if path.exists():
            bucket.blob(f"{prefix}/final/{name}").upload_from_filename(str(path), content_type=mime)
            files.append(name)
    (workdir / "proveniencia.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    bucket.blob(f"{prefix}/final/proveniencia.json").upload_from_filename(
        str(workdir / "proveniencia.json"), content_type="application/json")
    files.append("proveniencia.json")
    now = datetime.now(timezone.utc).isoformat()
    if pdf:
        ref.update({"status": "concluido" if final else "rascunho", "files": files, "compiled_at": now,
                    "updated_at": now, "compile_report": record["compilacao"],
                    "error": "" if final else " ".join(reasons)})
        update(status="completed", stage="PDF final pronto" if final else "Rascunho pronto", finished_at=now)
    else:
        ref.update({"status": "pronto", "files": files, "updated_at": now, "compile_report": record["compilacao"],
                    "error": "A compilação falhou: " + str(report.get("motivo", "")) +
                    ". O .tex foi salvo para conferência."})
        update(status="completed", stage="Compilação falhou; .tex salvo", finished_at=now)
    return record


def rebuild_references(data: dict, *, db, bucket, owner_uid: str, cache, get_json, update, metadata,
                       crossref_get=None, oasisbr_get=None) -> dict:
    """Refaz só o BibTeX de um projeto existente, sem tocar no texto já aceito.

    - A chave de cada fonte continua a mesma (o texto já cita essas chaves).
    - Referência corrigida no documento ou confirmada pelo pesquisador é mantida.
    - O resto é refeito com a cascata atual (biblioteca, DOI, OpenAlex, Crossref, BDTD/Oasisbr),
      mas nunca piora: se a consulta nova falhar, uma referência mais confiável fica.
    """
    ref, project = _project(db, data, owner_uid)
    prefix = f"mcp/{owner_uid}/{project['id']}"
    before = project.get("status_antes") or "pronto"
    update(status="running", stage="Refazendo as referências", started_at=datetime.now(timezone.utc).isoformat())
    manifest = json.loads(bucket.blob(prefix + "/sources.json").download_as_bytes())
    old = json.loads(bucket.blob(prefix + "/references.json").download_as_bytes())
    fetch = lambda path: bucket.blob(path).download_as_bytes()  # noqa: E731
    sources, texts, meta = [], {}, {}
    by_id = {s.get("id"): s for s in project.get("sources") or []}
    for entry in manifest:
        source = by_id.get(entry.get("id"))
        derived = str(entry.get("derived") or "")
        if not source or not derived.startswith(f"library/{owner_uid}/derived/"):
            continue
        payload = json.loads(bucket.blob(derived).download_as_bytes())
        texts[source["id"]] = bib_integrity.first_pages_text(payload)
        try:
            meta[source["id"]] = metadata(source, fetch, cache)
        except Exception:  # noqa: BLE001 - metadado do PDF é só uma pista de título
            meta[source["id"]] = {}
        sources.append(source)
    library_cards = _load_library_cards(db, owner_uid, sources)
    fresh = {e["source_id"]: e for e in bib_integrity.library_entries(
        sources, get_json, meta, texts, crossref_get=crossref_get, oasisbr_get=oasisbr_get,
        library_cards=library_cards)}
    _persist_confirmed_cards(db, owner_uid, list(fresh.values()))
    out, changed = [], []
    for previous in old:
        sid = previous.get("source_id")
        new = fresh.get(sid)
        rank = {"confirmada": 2, "sugerida": 1, "a_conferir": 0}
        if (previous.get("how") in ("corrigida_pelo_texto", "confirmada_pelo_pesquisador") or not new or
                rank[bib_integrity.ref_level(new)] < rank[bib_integrity.ref_level(previous)]):
            out.append(previous)
            continue
        new = {**new, "key": previous["key"]}  # a chave citada no texto não muda
        if previous.get("proposta_pendente") and bib_integrity.ref_level(new) != "confirmada":
            new["proposta_pendente"] = previous["proposta_pendente"]
        if (new.get("fields"), new.get("how")) != (previous.get("fields"), previous.get("how")):
            changed.append(previous["key"])
        out.append(new)
    bucket.blob(prefix + "/references.json").upload_from_string(
        json.dumps(out, ensure_ascii=False), content_type="application/json")
    bucket.blob(prefix + "/references.bib").upload_from_string(
        "".join(bib_integrity.render(e) for e in out), content_type="text/plain; charset=utf-8")
    summary = {"alteradas": changed, "referencias_a_conferir": [e["key"] for e in pending_refs(out)],
               "consultas_openalex": _lookup_summary(list(fresh.values()))}
    status = "pronto" if before in ("concluido", "rascunho") else before
    note = "Referências refeitas: chame compilar de novo." if before in ("concluido", "rascunho") else ""
    ref.update({"status": status, "refs_summary": summary, "error": note,
                "updated_at": datetime.now(timezone.utc).isoformat()})
    update(status="completed", stage="Referências refeitas", finished_at=datetime.now(timezone.utc).isoformat())
    return summary
