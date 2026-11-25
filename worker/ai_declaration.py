"""Declaração de uso de IA generativa no modelo do Anexo I da IN IFRS 16/2026 (M11).

Origem: R25 (IFRS, Instrução Normativa nº 16/2026 e seu Anexo I, ambos
assinados em 26/05/2026; códigos de verificação d3ba1f7224 e e712908ba1 no SIG
do IFRS) e R48 (Guia para o uso de IA generativa no IFRS, que explica o
preenchimento do Anexo I passo a passo). Cópias em docs/normas/. Plano V2,
módulo M11 "Declaração institucional de uso de IA".

A parte principal segue as 5 seções do Anexo I, na ordem e com os mesmos
rótulos:
1. Identificação do autor; 2. Identificação do trabalho acadêmico;
3. Registro do uso de IAGen (Art. 6º): ferramenta/modelo, finalidade com o
   inciso, etapa do trabalho e conteúdo produzido ou modificado;
4. Autorização do(a) servidor(a) (Art. 8º); 5. Compromisso do(a) autor(a).
O texto do compromisso e a nota são os do Anexo, com "XX/2026" trocado por
"16/2026" (número da IN que o Anexo acompanha).

Depois vem um apêndice técnico do Scriptorium, fora do Anexo I: dados enviados
(Art. 9º), vedações (Art. 7º) e rastreabilidade (Art. 6º, XII). O que só a
pessoa pode declarar (matrícula, etapa exata no trabalho, assinaturas) fica
como [PREENCHER]. O Scriptorium não garante conformidade: a pessoa revisa,
completa e assina.
"""
from __future__ import annotations

IN_URL = "https://ifrs.edu.br/documentos/instrucao-normativa-ifrs-n-16-2026/"
ANNEX_URL = "https://ifrs.edu.br/wp-content/uploads/2026/05/Anexo-IN-IAGen.pdf"
SIG = "https://sig.ifrs.edu.br/documentos/"
FILL = "[PREENCHER]"
STAGES = [
    ("outline", "Planejamento da estrutura do texto"),
    ("literature", "Busca e organização bibliográfica (Semantic Scholar, via PaperOrchestra)"),
    ("plotting", "Geração de gráficos"),
    ("writing", "Redação do rascunho"),
    ("refinement", "Revisão e refinamento do rascunho"),
]
ART6 = {
    "I": "exploração de ideias e formulação de hipóteses",
    "II": "busca e organização bibliográfica",
    "III": "leitura assistida e resumo de artigos",
    "IV": "revisão gramatical, ortográfica e estilística",
    "VII": "criação de visualizações e gráficos",
    "VIII": "exploração de perspectivas e argumentos",
    "X": "elaboração parcial de seções textuais",
    "XI": "pré-avaliação de manuscritos",
    "XII": "agentes de IAGen encadeados",
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
COMMITMENT = ("Declaro que as informações prestadas são verídicas. Afirmo que revisei criticamente todo o conteúdo "
              "produzido com auxílio de IAGen e assumo **responsabilidade intelectual, ética e legal integral** pelo "
              "produto acadêmico resultante, em conformidade com os Arts. 3º, 4º e 5º da Instrução Normativa nº "
              "16/2026 e com as normas de integridade acadêmica do IFRS.")
NOTE = ("**Nota:** Esta declaração deve ser inserida como Anexo I no trabalho acadêmico, preferencialmente antes das "
        "referências bibliográficas. O simples uso de corretores gramaticais ou verificadores ortográficos nativos de "
        "processadores de texto não requer declaração (Art. 5º, parágrafo único). A omissão intencional das "
        "informações ou a prestação de dados falsos configura violação à integridade acadêmica do IFRS.")


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def _date(value: str) -> str:
    return (value or "")[:10] or "data não registrada"


def _br(value: str) -> str:
    """AAAA-MM-DD -> DD/MM/AAAA (formato do Anexo I)."""
    value = (value or "")[:10]
    parts = value.split("-")
    return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else "DD/MM/AAAA"


def usage_rows(manifest: dict, agents: dict) -> list[dict]:
    """Linhas da seção 3 do Anexo I: ferramenta, finalidade (inciso), etapa e conteúdo."""
    request = manifest.get("request", {})
    services = manifest.get("ai_services") or {}
    ran = lambda key: agents.get(key) not in (None, "disabled")  # noqa: E731
    writer = request.get("model") or "Gemini"
    reviewer = request.get("reflection_model") or writer
    rows = []

    def add(tool, inc, stage, content):
        rows.append({"tool": tool, "inciso": inc, "stage": stage, "content": content})

    if ran("outline"):
        add(f"Gemini `{writer}` (via PaperOrchestra)", "I", "Planejamento do trabalho",
            "Estrutura e roteiro do texto gerados a partir da ideia e do registro experimental do autor")
    if ran("literature"):
        add(f"Gemini `{writer}` (via PaperOrchestra, com Semantic Scholar)", "II", "Revisão de literatura",
            "Busca e organização de referências (references.bib); cada fonte precisa ser verificada individualmente")
    if manifest.get("sources"):
        add(f"Gemini `{writer}` (via PaperOrchestra)", "III", "Fundamentação teórica",
            f"Leitura assistida de trechos de {len(manifest['sources'])} fonte(s) da biblioteca pessoal do autor")
    embeddings = services.get("embeddings") or {}
    if (embeddings.get("usage") or {}).get("texts"):
        add(f"Gemini Embedding `{embeddings.get('model', '')}`", "III", "Seleção de trechos das fontes",
            "Seleção por similaridade dos trechos lidos pelos agentes e busca de evidências (não gera texto)")
    if ran("writing"):
        add(f"Gemini `{writer}` (via PaperOrchestra)", "X", f"{FILL} (seções em que o texto foi usado)",
            "Rascunho das seções do manuscrito; exige revisão crítica integral e não pode ser apresentado como "
            "trabalho próprio sem essa revisão (Art. 7º, I)")
    if ran("refinement"):
        add(f"Gemini `{reviewer}` (via PaperOrchestra)", "IV", "Revisão do rascunho",
            "Revisão de linguagem, estilo e coerência do rascunho gerado")
    if request.get("plotting") and ran("plotting"):
        add(f"Gemini `{request.get('image_model', '')}` (via PaperOrchestra)", "VII", "Figuras e gráficos",
            "Gráficos a partir dos dados do registro experimental; exigem descrição metodológica explícita (Art. 7º, VI)")
    fire = services.get("fire") or {}
    if fire.get("calls"):
        add(f"Gemini `{fire.get('model', '')}`", "XI", "Pré-avaliação do manuscrito",
            "Verificação experimental de afirmações nas fontes anexadas (relatório; não altera o texto)")
    compare = services.get("contradictions") or {}
    if compare.get("calls"):
        add(f"Gemini `{compare.get('model', '')}`", "VIII", "Discussão",
            "Indicação de possíveis divergências entre fontes (relatório; não altera o texto)")
    if request.get("neon_review_requested"):
        add("Gemini `gemini-4-neon`", "XI", "Pré-avaliação do manuscrito",
            "Parecer crítico sobre argumentos e evidências (relatório; não altera o texto)")
    add("PaperOrchestra (Google Research) com Gemini", "XII", "Todo o processo de geração",
        "Orquestração de agentes encadeados; documentação completa no manifesto de proveniência (apêndice)")
    return rows


def uses_by_article(manifest: dict, agents: dict) -> list[tuple[str, str]]:
    """Incisos do Art. 6º acionados (para conferir com a autorização registrada)."""
    seen = []
    for row in usage_rows(manifest, agents):
        if row["inciso"] not in [code for code, _ in seen]:
            seen.append((row["inciso"], row["content"]))
    return seen


def build_declaration(manifest: dict, agents: dict | None = None) -> str:
    request = manifest.get("request", {})
    software = manifest.get("software", {})
    engine = software.get("paper_orchestra", {})
    institutional = manifest.get("institutional") or {}
    authorization = institutional.get("advisor_authorization") or {}
    profile = institutional.get("academic_profile") or {}
    policy = institutional.get("data_policy") or {}
    agents = agents or {}
    auth_mode = request.get("ai_auth_mode") or "admin_vertex"
    rows = usage_rows(manifest, agents)
    authorized = set(authorization.get("scope") or [])
    outside = sorted({r["inciso"] for r in rows if authorization and r["inciso"] not in authorized})
    sources = manifest.get("sources", [])
    inputs = manifest.get("inputs", {})
    outputs = manifest.get("outputs", {})
    writer = request.get("model") or "não registrado"
    reviewer = request.get("reflection_model") or writer
    provider = request.get("provider") or "Google"

    def value(text):
        return text if text else FILL

    if policy:
        data_lines = [f"- **Dados inéditos ou sensíveis no material enviado (declarado na criação):** "
                      f"{'sim' if policy.get('unpublished_data') else 'não'}"]
        if policy.get("unpublished_data"):
            tier = ("não se aplica (IA do projeto)" if policy.get("paid_tier_confirmed") is None
                    else "confirmado pelo(a) autor(a)" if policy.get("paid_tier_confirmed") else "não confirmado")
            data_lines += [
                f"- **Chave em projeto com faturamento ativo (conteúdo não usado para treinar modelos):** {tier}",
                f"- **Dados sem identificação de participantes (LGPD):** "
                f"{'confirmado pelo(a) autor(a)' if policy.get('deidentified_confirmed') else 'não confirmado'}",
            ]
        data_lines.append(f"- **Política do fornecedor:** {policy.get('provider_training_policy', '')}")
    else:
        data_lines = [f"- **Houve envio de dados pessoais, inéditos ou sensíveis? Quais e com que autorização?** {FILL}"]

    models = [f"`{writer}`"] + ([f"`{reviewer}`"] if reviewer != writer else [])
    if request.get("plotting"):
        models.append(f"`{request.get('image_model', '')}`")

    lines = [
        "> Preenchido pelo Scriptorium no modelo do **Anexo I da IN IFRS nº 16/2026** "
        f"(autenticidade em {SIG}: Anexo nº 2/2026, código e712908ba1; IN em {IN_URL}). "
        "**RASCUNHO para revisão:** confira cada linha, complete os campos [PREENCHER] e colete as assinaturas. "
        "O Scriptorium não garante conformidade; a declaração é sua. "
        f"Modelo oficial: {ANNEX_URL}.",
        "",
        "# ANEXO I",
        "## DECLARAÇÃO DE USO DE INTELIGÊNCIA ARTIFICIAL GENERATIVA",
        "",
        "### 1. IDENTIFICAÇÃO DO AUTOR",
        "",
        "| | |",
        "|---|---|",
        f"| **Nome completo** | {value(profile.get('full_name'))} |",
        f"| **Matrícula** | {value(profile.get('enrollment'))} |",
        f"| **Unidade** | {value(profile.get('unit'))} |",
        f"| **Curso / Programa** | {value(profile.get('program'))} |",
        f"| **Servidor responsável** | {value(authorization.get('advisor_name'))} |",
        "",
        "### 2. IDENTIFICAÇÃO DO TRABALHO ACADÊMICO",
        "",
        "| | |",
        "|---|---|",
        f"| **Título do trabalho acadêmico** | {value(manifest.get('title'))} |",
        f"| **Natureza do trabalho acadêmico** | {value(institutional.get('work_type'))} |",
        f"| **Data da declaração** | {FILL} (DD/MM/AAAA) |",
        "",
        "### 3. REGISTRO DO USO DE IAGen — Art. 6º",
        "",
        "| Ferramenta / Modelo | Finalidade do uso (Art. 6º, inciso) | Etapa do trabalho acadêmico | Conteúdo produzido ou modificado pela IAG |",
        "|---|---|---|---|",
        *[f"| {r['tool']} | {_upper_first(ART6.get(r['inciso'], ''))} (inc. {r['inciso']}) | {r['stage']} | {r['content']} |"
          for r in rows],
        "",
        "Acrescente linhas conforme necessário (por exemplo, outros usos de IA fora do Scriptorium). As finalidades "
        "devem corresponder aos incisos do Art. 6º da IN nº 16/2026. Ajuste a coluna \"Etapa\" ao capítulo ou "
        "seção em que o conteúdo foi de fato usado.",
        "",
        "### 4. AUTORIZAÇÃO DO(A) SERVIDOR(A) — Art. 8º",
        "",
        "| | |",
        "|---|---|",
        "| **O(A) servidor(a) declara ter:** | • ciência do uso de IAGen registrado na Seção 3;<br>• autorizado formalmente o uso, conforme o Art. 8º da IN nº 16/2026. |",
        "| **Assinatura** | |",
        f"| **Data** | {_br(authorization.get('authorized_on')) if authorization else 'DD/MM/AAAA'} |",
        "",
        *([f"> Autorização registrada pelo(a) autor(a) no Scriptorium em {_br(authorization.get('recorded_at', ''))}: "
           f"{authorization.get('advisor_name')}, {authorization.get('record_form')}"
           + (f" ({authorization['record_reference']})" if authorization.get("record_reference") else "")
           + f", incisos {', '.join(authorization.get('scope') or [])}. Não substitui a assinatura do(a) servidor(a)."]
          if authorization else
          ["> Nenhuma autorização estava registrada no Scriptorium quando esta pesquisa foi criada. "
           "Autorização prévia (Art. 6º e 8º) precisa ser obtida e assinada pelo(a) servidor(a)."]),
        *([f"> **Atenção:** usos desta execução fora da autorização registrada: incisos {', '.join(outside)}. "
           "Obtenha autorização complementar antes de usar o resultado."] if outside else []),
        "",
        "### 5. COMPROMISSO DO(A) AUTOR(A)",
        "",
        COMMITMENT,
        "",
        NOTE,
        "",
        "",
        "______________________________________ &nbsp;&nbsp;&nbsp; ______________________________________",
        "",
        "Assinatura do(a) autor(a) &nbsp;&nbsp;&nbsp; Local e data",
        "",
        "---",
        "",
        "# Apêndice técnico do Scriptorium (não faz parte do Anexo I)",
        "",
        "Registro de apoio para o(a) autor(a) e o(a) servidor(a). Pode ser guardado com o trabalho, mas não precisa "
        "ser inserido nele.",
        "",
        "## A. Ferramentas e políticas de privacidade (Art. 6º, XII, e Art. 9º)",
        "",
        f"- **PaperOrchestra** (Google Research), commit `{str(engine.get('commit', ''))[:12]}`: {engine.get('repository', '')}",
        f"- **Modelos Gemini usados:** {', '.join(models)}; fornecedor: {provider}",
        f"- **Política de dados do fornecedor de IA:** {POLICIES.get(auth_mode, POLICIES['admin_vertex'])}",
        *[f"- {line}" for line in METADATA_POLICIES],
        "- Verificações automáticas feitas **sem** IA generativa: triagem heurística local do texto; consulta de "
        "metadados em Crossref, OpenAlex e Semantic Scholar; retratações e correções na Crossref (inclui Retraction "
        "Watch). Essas consultas não comprovam que as fontes sustentam o que o texto afirma.",
        "",
        "## B. Dados enviados às ferramentas (Art. 9º e Art. 10)",
        "",
        *data_lines,
        "",
        "## C. Vedações (Art. 7º): confirme antes de usar o resultado",
        "",
        "- [ ] O trabalho não foi desenvolvido integral ou substancialmente pela IA e apresentado como de autoria própria (I).",
        "- [ ] Nenhuma referência falsa foi mantida; todas foram conferidas nas obras originais (II).",
        "- [ ] Nenhum dado sensível, inédito ou sigiloso foi enviado sem autorização e garantias de privacidade (III; Art. 9º).",
        "- [ ] Nenhum conteúdo de desinformação, deepfake ou violação de direitos autorais (V).",
        "- [ ] Imagens geradas por IA, se houver, têm descrição metodológica explícita e respeitam a política da revista (VI).",
        "",
        "## D. Autoria, supervisão e revisão crítica (Art. 3º e Art. 4º)",
        "",
        "- As ferramentas de inteligência artificial listadas não são autoras nem coautoras deste trabalho (Art. 3º).",
        *([f"- **Fontes revisadas e aprovadas pelo(a) autor(a) antes da geração:** {_date(e.get('at', ''))} (checkpoint registrado no Scriptorium)"
           for e in (manifest.get("approvals") or {}).get("events", [])
           if e.get("checkpoint") == "source_approval" and e.get("decision") == "approve"][:1]),
        f"- **Partes reescritas ou revisadas pelo(a) autor(a):** {FILL}",
        f"- **Referências conferidas nas obras originais (todas? quais?):** {FILL}",
        f"- **Dados, números e resultados conferidos:** {FILL}",
        "",
        "## E. Rastreabilidade (documentação completa do processo, Art. 6º, XII)",
        "",
        f"- **Período de uso:** {_date(manifest.get('started_at'))} a {_date(manifest.get('finished_at'))}",
        "- **Etapas executadas pela ferramenta:** "
        + ("; ".join(label for key, label in STAGES if agents.get(key) not in (None, "disabled")) or "não registradas"),
        f"- **Idioma e template:** {request.get('language') or 'en'}, {request.get('template') or 'não registrado'}",
        "- **Materiais do autor entregues à ferramenta:** ideia e registro experimental (SHA-256: "
        + (", ".join(str(v.get('sha256', ''))[:12] for k, v in inputs.items() if k != 'delivered_to_agents') or "não registrado") + ")",
        f"- **Estratégia de uso das fontes:** {(manifest.get('context') or {}).get('strategy', 'não registrada')}",
        f"- **Fontes da biblioteca pessoal:** {len(sources)}"
        + (": " + "; ".join(str(s.get("name", "")) for s in sources) if sources else ""),
        f"- **Execução:** `{manifest.get('run_id', '')}`; **manifesto (SHA-256):** `{manifest.get('content_sha256', '')}`",
        f"- **Instantâneo do corpus:** `{manifest.get('corpus_snapshot', '')}`",
        f"- **Versão do Scriptorium:** `{software.get('scriptorium_release_sha', '')}`",
        f"- **Arquivos gerados:** {', '.join(sorted(outputs)) or 'não registrados'}",
        "",
    ]
    return "\n".join(lines)
