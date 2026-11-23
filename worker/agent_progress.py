"""Etapas observáveis do pipeline, baseadas em ARQUIVOS reais de saída.

Não apresenta progresso fictício em porcentagem nem comprovação de qualidade
científica. Um agente "concluído" significa somente que sua etapa gerou artefatos.
"""
from pathlib import Path

AGENT_NAMES = ("outline", "literature", "plotting", "writing", "refinement")


def inspect_agents(output_dir: str | Path, plotting: bool = False) -> dict[str, str]:
    out = Path(output_dir)
    states = {name: "waiting" for name in AGENT_NAMES}
    if not plotting:
        states["plotting"] = "disabled"

    # O PDF final é produzido somente após o refinamento de conteúdo.
    if (out / "final_paper.pdf").is_file():
        return {name: ("disabled" if name == "plotting" and not plotting else "completed")
                for name in AGENT_NAMES}

    if not (out / "outline.json").is_file():
        states["outline"] = "running"
        return states
    states["outline"] = "completed"

    references = out / "literature_agent_output" / "references.bib"
    mapping = out / "literature_agent_output" / "citation_map.json"
    if references.is_file() and mapping.is_file():
        states["literature"] = "completed"
    else:
        states["literature"] = "running"

    if plotting:
        if (out / "plotting_results.json").is_file():
            states["plotting"] = "completed"
        else:
            states["plotting"] = "running"

    if states["literature"] != "completed" or (plotting and states["plotting"] != "completed"):
        return states

    draft = out / "latex_writeup" / "raw_draft_paper.tex"
    if not draft.is_file():
        states["writing"] = "running"
        return states

    states["writing"] = "completed"
    states["refinement"] = "running"
    return states


def current_stage(states: dict[str, str]) -> str:
    captions = {
        "outline": "Agente de planejamento",
        "literature": "Agente de revisão bibliográfica",
        "plotting": "Agente de gráficos",
        "writing": "Agente de redação",
        "refinement": "Agente de refinamento",
    }
    for name in AGENT_NAMES:
        if states.get(name) == "running":
            return captions[name]
    return "Finalizando os arquivos"
