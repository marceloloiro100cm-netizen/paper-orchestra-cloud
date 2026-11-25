"""Orçamento por etapa e cancelamento cooperativo de uma execução (M15).

Origem: R01 (Scriptorium). Plano V2, módulo M15 "Orçamento, telemetria e
regressão": "orçamento por etapa e cancelamento de Job pelo navegador".

Como funciona:
- cada etapa tem um teto de tempo (segundos) e, quando chama modelo, o teto de
  chamadas que o próprio módulo já respeita (FIRE, divergências, embeddings);
- antes de uma etapa OPCIONAL (auditorias, parecer), a execução confere quanto
  tempo resta no orçamento total; se não couber, a etapa é pulada e registrada
  como "pulada_por_orcamento" (o manuscrito já entregue não é afetado);
- o navegador pede o cancelamento gravando cancel_requested no Firestore; o
  worker confere a marca a cada ciclo de acompanhamento e entre as etapas, e
  encerra o motor com SIGTERM (depois SIGKILL). Nada é apagado: arquivos já
  publicados e o manifesto continuam disponíveis.

Os tempos medidos vão para o manifesto (run_manifest.json, seção stage_budget).
"""
from __future__ import annotations

import os
import time

# Tempo total que uma execução pode usar. O task-timeout do Cloud Run Job é de
# 180 min; a reconciliação da API considera 200 min. Margem de 10 min.
EXECUTION_BUDGET_SECONDS = int(os.getenv("SCRIPTORIUM_EXECUTION_BUDGET_SECONDS", str(170 * 60)))

# Teto por etapa (segundos) e se a etapa pode ser pulada sem afetar o manuscrito.
STAGES = {
    "preparo_das_fontes": {"max_seconds": 15 * 60, "optional": False},
    "agentes_de_redacao": {"max_seconds": 10400, "optional": False},
    "triagem_cientifica": {"max_seconds": 3 * 60, "optional": True},
    "conferencia_de_referencias": {"max_seconds": 12 * 60, "optional": True},
    "citacoes_e_evidencias": {"max_seconds": 10 * 60, "optional": True},
    "verificacao_fire": {"max_seconds": 15 * 60, "optional": True, "max_model_calls": 40},
    "divergencias_entre_fontes": {"max_seconds": 10 * 60, "optional": True, "max_model_calls": 12},
    "parecer_neon": {"max_seconds": 8 * 60, "optional": True, "max_model_calls": 1},
    "registro_final": {"max_seconds": 3 * 60, "optional": False},
}


class Cancelled(Exception):
    """O pesquisador pediu o cancelamento pelo navegador."""


class StageBudget:
    def __init__(self, is_cancel_requested=None, clock=time.monotonic,
                 total_seconds: int = EXECUTION_BUDGET_SECONDS):
        self.clock = clock
        self.started = clock()
        self.total = total_seconds
        self.is_cancel_requested = is_cancel_requested or (lambda: False)
        self.records: dict[str, dict] = {}
        self._current: tuple[str, float] | None = None

    # --------------------------------------------------------------- consultas
    def elapsed(self) -> float:
        return self.clock() - self.started

    def remaining(self) -> float:
        return self.total - self.elapsed()

    def check_cancel(self) -> None:
        try:
            requested = bool(self.is_cancel_requested())
        except Exception:
            requested = False  # Firestore indisponível não cancela por suposição.
        if requested:
            raise Cancelled("Cancelada pelo pesquisador")

    def allows(self, stage: str) -> bool:
        """Etapa opcional só roda se o teto dela cabe no que resta do orçamento."""
        spec = STAGES.get(stage, {"max_seconds": 0, "optional": True})
        if not spec["optional"]:
            return True
        if self.remaining() >= spec["max_seconds"]:
            return True
        self.records[stage] = {"status": "pulada_por_orcamento", "max_seconds": spec["max_seconds"],
                               "remaining_seconds": round(max(self.remaining(), 0))}
        return False

    # ----------------------------------------------------------------- registro
    def start(self, stage: str, check_cancel: bool = True) -> None:
        if check_cancel:
            self.check_cancel()
        self._current = (stage, self.clock())

    def finish(self, stage: str, status: str = "concluida", **details) -> None:
        began = self._current[1] if self._current and self._current[0] == stage else self.clock()
        seconds = round(self.clock() - began, 1)
        spec = STAGES.get(stage, {})
        self.records[stage] = {
            "status": status, "seconds": seconds, "max_seconds": spec.get("max_seconds"),
            "over_budget": bool(spec.get("max_seconds") and seconds > spec["max_seconds"]),
            **{k: v for k, v in details.items() if isinstance(v, (str, int, float, bool)) or v is None},
        }
        self._current = None

    def report(self) -> dict:
        return {
            "schema": "scriptorium.stage_budget/1",
            "execution_budget_seconds": self.total,
            "elapsed_seconds": round(self.elapsed(), 1),
            "limits": STAGES,
            "stages": self.records,
            "note": ("Etapas opcionais são puladas quando o tempo restante não cabe no teto delas; "
                     "o custo em tokens do motor original continua não medido (ver costs)."),
        }
