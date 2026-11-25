"""Rascunho de declaração de uso de IA generativa por execução (M11).

Origem: R25 (IFRS, Instrução Normativa nº 16/2026, assinada em 26/05/2026) e
R01. Plano: Scriptorium V2, módulo M11 "Declaração institucional de uso de IA".

Texto da IN conferido em 24/11/2026 a partir do PDF assinado (4 páginas,
código de verificação d3ba1f7224 no SIG do IFRS). O rascunho segue a IN artigo
por artigo:
- Art. 2º, II e Art. 5º: uso declarado de forma clara e detalhada;
- Art. 3º: IA não é autora nem coautora;
- Art. 4º: revisão crítica pela pessoa (correção, citações, ética);
- Art. 6º: usos permitidos, com autorização do orientador; cada etapa da
  execução é ligada ao inciso correspondente;
- Art. 6º, XII: agentes encadeados exigem documentação completa (manifesto)
  e verificação das políticas de privacidade de cada ferramenta;
- Art. 7º: vedações, como itens que o autor precisa confirmar;
- Art. 8º: registro formal da autorização (dados vindos da conta);
- Art. 9º e 10: dados inéditos ou sensíveis e LGPD (política registrada na criação).

O modelo do Anexo I NÃO estava no PDF recebido e ainda não foi conferido. Por
isso o arquivo continua sendo um RASCUNHO, nunca afirma conformidade e deixa
campos [PREENCHER] para o que só a pessoa pode declarar.
"""
from __future__ import annotations

IN_URL = "https://ifrs.edu.br/documentos/instrucao-normativa-ifrs-n-16-2026/"
ANNEX_URL = "https://ifrs.edu.br/wp-content/uploads/2026/05/Anexo-IN-IAGen.pdf"
SIG_VERIFICATION = ("https://sig.ifrs.edu.br/public/documentos/index.jsp (IN nº 16/2026, emissão 26/05/2026, "
                    "código de verificação d3ba1f7224)")
FILL = "[PREENCHER]"
STAGES = [
    ("outline", "Planejamento da estrutura do texto"),
    ("literature", "Busca e organização bibliográfica (Semantic Scholar, via PaperOrchestra)"),
    ("plotting", "Geração de gráficos"),
    ("writing", "Redação do rascunho"),
    ("refinement", "Revisão e refinamento do rascunho"),
]
ART6 = {
    "I": "exploração de ideias e problemáticas",
    "II": "busca e organização bibliográfica",
    "III": "leitura assistida de artigos",
    "IV": "revisão gramatical, ortográfica e estilística",
    "VII": "visualizações e gráficos com dados da pessoa",
    "VIII": "exploração de perspectivas e contrapontos",
    "X": "elaboração parcial de seções textuais",
    "XI": "pré-avaliação de manuscritos",
    "XII": "agentes de IAGen em tarefas encadeadas",
}
POLICIES = {
    "user_gemini": "Gemini API, termos adicionais: https://ai.google.dev/gemini-api/terms (sem faturamento ativo, "
                   "o conteúdo pode ser usado para melhorar produtos do Google; com faturamento ativo, não)",
    "admin_vertex": "Google Cloud / Vertex AI: https://cloud.google.com/terms/service-terms",
}
METADATA_POLICIES = [
    "Semantic Scholar API (consultas de busca bibliográfica do PaperOrchestra): https://www.semanticscholar.org/product/api/license",
    "Crossref REST API (só DOI e título das referências): https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
    "OpenAlex (só DOI e título das referências): https://openalex.org/",
]


def _date(value: str) -> str:
    return (value or "")[:10] or "data não registrada"


def uses_by_article(manifest: dict, agents: dict) -> list[tuple[str, str]]:
    """Incisos do Art. 6º da IN acionados nesta execução, com a descrição do uso."""
    request = manifest.get("request", {})
    ran = lambda key: agents.get(key) not in (None, "disabled")  # noqa: E731
    services = manifest.get("ai_services") or {}
    uses = []
    if ran("outline"):
        uses.append(("I", "o agente de planejamento estruturou o texto a partir da ideia e do registro experimental"))
    if ran("literature"):
        uses.append(("II", "o agente de literatura buscou e organizou referências; cada fonte precisa ser verificada "
                           "individualmente (use a conferência de referências do Scriptorium como apoio)"))
    if manifest.get("sources"):
        uses.append(("III", "trechos das fontes da biblioteca pessoal foram lidos pelos agentes como contexto"))
    if ran("refinement"):
        uses.append(("IV", "o agente de refinamento revisou linguagem e estilo do rascunho"))
    if request.get("plotting") and ran("plotting"):
        uses.append(("VII", "gráficos gerados a partir dos dados do registro experimental; imagens geradas por IA "
                            "exigem descrição metodológica explícita (Art. 7º, VI)"))
    if (services.get("contradictions") or {}).get("calls") or request.get("neon_review_requested"):
        uses.append(("VIII", "comparação de fontes e/ou parecer crítico apontaram divergências e contrapontos"))
    if ran("writing"):
        uses.append(("X", "o agente de redação produziu o rascunho das seções; exige revisão crítica integral "
                          "pelo autor e não pode ser apresentado como trabalho próprio sem isso (Art. 7º, I)"))
    if request.get("neon_review_requested") or (services.get("fire") or {}).get("calls"):
        uses.append(("XI", "pré-avaliação do manuscrito (parecer crítico e/ou verificação de afirmações)"))
    uses.append(("XII", "o PaperOrchestra encadeia vários agentes de IA; a documentação completa do processo é o "
                        "manifesto de proveniência desta execução"))
    return uses


def build_declaration(manifest: dict, agents: dict | None = None) -> str:
    request = manifest.get("request", {})
    software = manifest.get("software", {})
    engine = software.get("paper_orchestra", {})
    institutional = manifest.get("institutional") or {}
    authorization = institutional.get("advisor_authorization") or {}
    policy = institutional.get("data_policy") or {}
    agents = agents or {}
    writer = request.get("model") or "não registrado"
    reviewer = request.get("reflection_model") or writer
    provider = request.get("provider") or "Google"
    auth_mode = request.get("ai_auth_mode") or "admin_vertex"

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
        tools.append(f"| Gemini | {provider} | `gemini-4-neon` | Parecer crítico opcional (não altera o texto) |")
    services = manifest.get("ai_services") or {}
    embeddings = services.get("embeddings")
    if embeddings and embeddings.get("usage", {}).get("texts"):
        tools.append(f"| Gemini Embedding | {embeddings.get('provider', provider)} | "
                     f"`{embeddings.get('model', '')}` | Seleção de trechos das fontes anexadas por "
                     "similaridade semântica e busca de evidências (não gera texto) |")
    fire = services.get("fire")
    if fire and fire.get("calls"):
        tools.append(f"| Gemini | {fire.get('provider', provider)} | `{fire.get('model', '')}` | "
                     "Verificação experimental de afirmações nas fontes anexadas (não altera o texto) |")
    compare = services.get("contradictions")
    if compare and compare.get("calls"):
        tools.append(f"| Gemini | {compare.get('provider', provider)} | `{compare.get('model', '')}` | "
                     "Comparação experimental de pares de trechos das fontes (não altera o texto) |")

    used_stages = [label for key, label in STAGES if agents.get(key) not in (None, "disabled")]
    uses = uses_by_article(manifest, agents)
    authorized = set(authorization.get("scope") or [])
    outside = [code for code, _ in uses if authorization and code not in authorized]
    sources = manifest.get("sources", [])
    inputs = manifest.get("inputs", {})
    outputs = manifest.get("outputs", {})

    if authorization:
        auth_lines = [
            f"- **Autorização prévia registrada pelo(a) autor(a) no Scriptorium:** sim, em {_date(authorization.get('recorded_at', ''))}",
            f"- **Orientador(a) ou docente que autorizou:** {authorization.get('advisor_name')}",
            f"- **Data da autorização:** {authorization.get('authorized_on')}",
            f"- **Forma do registro formal (Art. 8º):** {authorization.get('record_form')}"
            + (f", {authorization['record_reference']}" if authorization.get("record_reference") else ""),
            f"- **Incisos do Art. 6º autorizados:** {', '.join(authorization.get('scope') or []) or 'não informados'}",
        ] + ([f"- **Atenção: usos desta execução fora da autorização registrada:** {', '.join(outside)}. "
              "Obtenha autorização complementar antes de usar o resultado."] if outside else [])
    else:
        auth_lines = [
            f"- **Autorização prévia para uso de IA generativa (quem autorizou, data e forma do registro, Art. 6º e 8º):** {FILL}",
            "- Nenhuma autorização estava registrada no Scriptorium quando esta pesquisa foi criada.",
        ]

    if policy:
        data_lines = [
            f"- **Dados inéditos ou sensíveis no material enviado (declarado na criação):** "
            f"{'sim' if policy.get('unpublished_data') else 'não'}",
        ]
        if policy.get("unpublished_data"):
            data_lines += [
                f"- **Chave em projeto com faturamento ativo (conteúdo não usado para treinar modelos):** "
                f"{'confirmado pelo(a) autor(a)' if policy.get('paid_tier_confirmed') else 'não se aplica (IA do projeto)' if policy.get('paid_tier_confirmed') is None else 'não confirmado'}",
                f"- **Dados sem identificação de participantes (LGPD):** "
                f"{'confirmado pelo(a) autor(a)' if policy.get('deidentified_confirmed') else 'não confirmado'}",
            ]
        data_lines.append(f"- **Política do fornecedor:** {policy.get('provider_training_policy', '')}")
    else:
        data_lines = [f"- **Houve envio de dados pessoais, inéditos ou sensíveis? Quais e com que autorização?** {FILL}"]

    lines = [
        "# Declaração de uso de Inteligência Artificial Generativa",
        "",
        "> **RASCUNHO gerado automaticamente pelo Scriptorium** com base na Instrução Normativa IFRS nº 16/2026 "
        f"({IN_URL}; autenticidade: {SIG_VERIFICATION}). Não é o formulário oficial: o modelo do Anexo I "
        f"({ANNEX_URL}) ainda não foi conferido item a item. Compare com o Anexo, com o(a) orientador(a) e com as "
        "normas do programa ou da revista. O Scriptorium não garante conformidade. Os campos marcados "
        "[PREENCHER] dependem de você.",
        "",
        "## 1. Identificação",
        "",
        f"- **Trabalho:** {manifest.get('title') or FILL}",
        f"- **Autor(a):** {FILL}",
        f"- **Orientador(a) ou docente responsável:** {authorization.get('advisor_name') or FILL}",
        "",
        "## 2. Autorização do orientador (Art. 6º, caput, e Art. 8º)",
        "",
        *auth_lines,
        "",
        "## 3. Usos de IA generativa nesta execução (Art. 5º e Art. 6º)",
        "",
        "| Inciso do Art. 6º | Uso | Como foi usado |",
        "|---|---|---|",
        *[f"| {code} | {ART6.get(code, '')} | {text} |" for code, text in uses],
        "",
        "## 4. Ferramentas e políticas de privacidade (Art. 6º, XII, e Art. 9º)",
        "",
        "| Ferramenta | Fornecedor | Modelo | Finalidade |",
        "|---|---|---|---|",
        *tools,
        "",
        f"- **Política de dados do fornecedor de IA:** {POLICIES.get(auth_mode, POLICIES['admin_vertex'])}",
        *[f"- {line}" for line in METADATA_POLICIES],
        "",
        "Verificações automáticas feitas **sem** IA generativa: triagem heurística local do texto; "
        "consulta de metadados bibliográficos em Crossref, OpenAlex e Semantic Scholar; consulta de "
        "retratações e correções na Crossref (inclui dados do Retraction Watch). Essas consultas não "
        "comprovam que as fontes sustentam o que o texto afirma.",
        "",
        "## 5. Dados enviados às ferramentas (Art. 9º e Art. 10)",
        "",
        *data_lines,
        "",
        "## 6. Etapas e período de uso",
        "",
        f"- **Período:** {_date(manifest.get('started_at'))} a {_date(manifest.get('finished_at'))}",
        "- **Etapas executadas pela ferramenta:**",
        *[f"  - {label}" for label in (used_stages or ["não registradas"])],
        f"- **Idioma solicitado:** {request.get('language') or 'en'}; **template:** {request.get('template') or 'não registrado'}",
        "",
        "## 7. Materiais fornecidos à ferramenta",
        "",
        "- Ideia de pesquisa e registro experimental escritos pelo(a) autor(a) "
        f"(SHA-256: {', '.join(str(v.get('sha256', ''))[:12] for k, v in inputs.items() if k != 'delivered_to_agents') or 'não registrado'}).",
        f"- Estratégia de uso das fontes: {(manifest.get('context') or {}).get('strategy', 'não registrada')}",
        f"- Fontes da biblioteca pessoal enviadas como contexto: {len(sources)}"
        + (": " + "; ".join(str(s.get("name", "")) for s in sources) if sources else "."),
        "",
        "## 8. Supervisão e revisão crítica humana (Art. 4º)",
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
        "## 9. Vedações (Art. 7º): confirmar antes de usar",
        "",
        "- [ ] O trabalho não foi desenvolvido integral ou substancialmente pela IA e apresentado como de autoria própria (I).",
        "- [ ] Nenhuma referência falsa foi mantida; todas foram conferidas nas obras originais (II).",
        "- [ ] Nenhum dado sensível, inédito ou sigiloso foi enviado sem autorização e garantias de privacidade (III; Art. 9º).",
        "- [ ] Nenhum conteúdo de desinformação, deepfake ou violação de direitos autorais (V).",
        "- [ ] Imagens geradas por IA, se houver, têm descrição metodológica explícita e respeitam a política da revista (VI).",
        "",
        "## 10. Autoria e responsabilidade (Art. 3º e Art. 4º)",
        "",
        "As ferramentas de inteligência artificial listadas não são autoras nem coautoras deste trabalho. "
        "O(a) autor(a) declara ser integralmente responsável pelo conteúdo, pelos resultados, pelas conclusões e "
        "pelas interpretações apresentadas, inclusive pela verificação de citações, referências e dados, e pela "
        "ausência de plágio e de referências falsas.",
        "",
        "## 11. Rastreabilidade (documentação completa do processo, Art. 6º, XII)",
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
