"""Rascunho de declaração de uso de IA generativa por execução (M11).

Origem: R25 (IFRS, Instrução Normativa nº 16/2026, de 27/05/2026) e R01.
Plano: Scriptorium V2, módulo M11 "Declaração institucional de uso de IA".

O que se sabe da IN 16/2026 pela divulgação oficial do IFRS: o uso de IA
generativa exige autorização do docente ou orientador e declaração do autor;
sistemas de IA não podem ser autores ou coautores; são vedados plágio,
referências falsas e compartilhamento indevido de dados sensíveis.

O texto do Anexo da IN ainda NÃO foi conferido item a item. Por isso o arquivo
gerado é um RASCUNHO: preenche só fatos registrados no manifesto (M14) e deixa
campos [PREENCHER] para o que depende do pesquisador. Nunca afirma conformidade.
"""
from __future__ import annotations

IN_URL = "https://ifrs.edu.br/documentos/instrucao-normativa-ifrs-n-16-2026/"
ANNEX_URL = "https://ifrs.edu.br/wp-content/uploads/2026/05/Anexo-IN-IAGen.pdf"
FILL = "[PREENCHER]"
STAGES = [
    ("outline", "Planejamento da estrutura do texto"),
    ("literature", "Busca e organização bibliográfica (Semantic Scholar, via PaperOrchestra)"),
    ("plotting", "Geração de gráficos"),
    ("writing", "Redação do rascunho"),
    ("refinement", "Revisão e refinamento do rascunho"),
]


def _date(value: str) -> str:
    return (value or "")[:10] or "data não registrada"


def build_declaration(manifest: dict, agents: dict | None = None) -> str:
    request = manifest.get("request", {})
    software = manifest.get("software", {})
    engine = software.get("paper_orchestra", {})
    agents = agents or {}
    writer = request.get("model") or "não registrado"
    reviewer = request.get("reflection_model") or writer
    provider = request.get("provider") or "Google"

    tools = [
        f"| PaperOrchestra (Google Research), commit `{str(engine.get('commit', ''))[:12]}` | "
        f"Google Research ({engine.get('repository', '')}) | não se aplica | Orquestração dos agentes de escrita |",
        f"| Gemini | {provider} | `{writer}` | Planejamento, busca bibliográfica e redação |",
    ]
    if reviewer != writer:
        tools.append(f"| Gemini | {provider} | `{reviewer}` | Revisão e refinamento do rascunho |")
    else:
        tools[-1] = tools[-1].replace("e redação |", "redação e refinamento |")
    if request.get("plotting"):
        tools.append(f"| Gemini | {provider} | `{request.get('image_model', '')}` | Geração de gráficos |")
    if request.get("neon_review_requested"):
        tools.append(f"| Gemini | Google Cloud (projeto Scriptorium) | `gemini-4-neon` | Parecer crítico opcional (não altera o texto) |")

    embeddings = (manifest.get("ai_services") or {}).get("embeddings")
    if embeddings and embeddings.get("usage", {}).get("texts"):
        tools.append(f"| Gemini Embedding | {embeddings.get('provider', provider)} | "
                     f"`{embeddings.get('model', '')}` | Seleção de trechos das fontes anexadas por "
                     "similaridade semântica e busca de evidências (não gera texto) |")
    compare = (manifest.get("ai_services") or {}).get("contradictions")
    if compare and compare.get("calls"):
        tools.append(f"| Gemini | {compare.get('provider', provider)} | `{compare.get('model', '')}` | "
                     "Comparação experimental de pares de trechos das fontes (não altera o texto) |")
    used_stages = [label for key, label in STAGES
                   if agents.get(key) not in (None, "disabled")]
    sources = manifest.get("sources", [])
    inputs = manifest.get("inputs", {})
    outputs = manifest.get("outputs", {})

    lines = [
        "# Declaração de uso de Inteligência Artificial Generativa",
        "",
        "> **RASCUNHO gerado automaticamente pelo Scriptorium.** Não é o formulário oficial. "
        f"Antes de usar, compare com a Instrução Normativa IFRS nº 16/2026 ({IN_URL}) e com o seu "
        f"Anexo ({ANNEX_URL}), com o(a) orientador(a) e com as normas do programa ou da revista. "
        "O Scriptorium não garante conformidade. Os campos marcados [PREENCHER] dependem de você.",
        "",
        "## 1. Identificação",
        "",
        f"- **Trabalho:** {manifest.get('title') or FILL}",
        f"- **Autor(a):** {FILL}",
        f"- **Orientador(a) ou docente responsável:** {FILL}",
        f"- **Autorização prévia para uso de IA generativa (quem autorizou, data e forma do registro):** {FILL}",
        "",
        "## 2. Ferramentas de IA generativa utilizadas",
        "",
        "| Ferramenta | Fornecedor | Modelo | Finalidade |",
        "|---|---|---|---|",
        *tools,
        "",
        "Verificações automáticas feitas **sem** IA generativa: triagem heurística local do texto; "
        "consulta de metadados bibliográficos em Crossref, OpenAlex e Semantic Scholar; consulta de "
        "retratações e correções na Crossref (inclui dados do Retraction Watch). Essas consultas não "
        "comprovam que as fontes sustentam o que o texto afirma.",
        "",
        "## 3. Etapas e período de uso",
        "",
        f"- **Período:** {_date(manifest.get('started_at'))} a {_date(manifest.get('finished_at'))}",
        "- **Etapas executadas pela ferramenta:**",
        *[f"  - {label}" for label in (used_stages or ["não registradas"])],
        f"- **Idioma solicitado:** {request.get('language') or 'en'}; **template:** {request.get('template') or 'não registrado'}",
        "",
        "## 4. Materiais fornecidos à ferramenta",
        "",
        "- Ideia de pesquisa e registro experimental escritos pelo(a) autor(a) "
        f"(SHA-256: {', '.join(str(v.get('sha256', ''))[:12] for k, v in inputs.items() if k != 'delivered_to_agents') or 'não registrado'}).",
        f"- Estratégia de uso das fontes: {(manifest.get('context') or {}).get('strategy', 'não registrada')}",
        f"- Fontes da biblioteca pessoal enviadas como contexto: {len(sources)}"
        + (": " + "; ".join(str(s.get("name", "")) for s in sources) if sources else "."),
        f"- **Houve envio de dados pessoais ou sensíveis? Quais e com que autorização?** {FILL}",
        "",
        "## 5. Supervisão e verificação humana",
        "",
        *([f"- **Fontes revisadas e aprovadas pelo(a) autor(a) antes da geração:** "
            f"{_date(e.get('at', ''))} (checkpoint registrado no Scriptorium)"
            for e in (manifest.get("approvals") or {}).get("events", [])
            if e.get("checkpoint") == "source_approval" and e.get("decision") == "approve"][:1]),
        f"- **Partes reescritas ou revisadas pelo(a) autor(a):** {FILL}",
        f"- **Referências conferidas nas obras originais (todas? quais?):** {FILL}",
        f"- **Dados, números e resultados conferidos:** {FILL}",
        f"- **Trechos gerados mantidos sem alteração:** {FILL}",
        "",
        "## 6. Autoria e responsabilidade",
        "",
        "As ferramentas de inteligência artificial listadas não são autoras nem coautoras deste trabalho. "
        "O(a) autor(a) declara ser integralmente responsável pelo conteúdo final, inclusive pela "
        "verificação de citações, referências e dados, e pela ausência de plágio e de referências falsas.",
        "",
        "## 7. Rastreabilidade",
        "",
        f"- **Execução:** `{manifest.get('run_id', '')}`",
        f"- **Instantâneo do corpus:** `{manifest.get('corpus_snapshot', '')}`",
        f"- **Manifesto (SHA-256 do conteúdo):** `{manifest.get('content_sha256', '')}`",
        f"- **Versão do Scriptorium:** `{software.get('scriptorium_release_sha', '')}`",
        f"- **Arquivos gerados:** {', '.join(sorted(outputs)) or 'não registrados'}",
        "",
        f"Local e data: {FILL}",
        "",
        f"Assinatura do(a) autor(a): {FILL}",
        "",
    ]
    return "\n".join(lines)
