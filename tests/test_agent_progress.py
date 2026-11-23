"""Testes offline: não fazem chamadas de IA nem modificam o Firebase."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from agent_progress import inspect_agents, current_stage  # noqa: E402


class AgentProgressTests(unittest.TestCase):
    def create(self, root: Path, relative: str):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artefato de teste", encoding="utf-8")

    def test_agent_stages_without_plotting(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            states = inspect_agents(output, plotting=False)
            self.assertEqual(states["outline"], "running")
            self.assertEqual(states["plotting"], "disabled")
            self.assertEqual(states["writing"], "waiting")

            self.create(output, "outline.json")
            states = inspect_agents(output, plotting=False)
            self.assertEqual(states["outline"], "completed")
            self.assertEqual(states["literature"], "running")
            self.assertEqual(current_stage(states), "Agente de revisão bibliográfica")

            self.create(output, "literature_agent_output/references.bib")
            self.create(output, "literature_agent_output/citation_map.json")
            states = inspect_agents(output, plotting=False)
            self.assertEqual(states["writing"], "running")

            self.create(output, "latex_writeup/raw_draft_paper.tex")
            states = inspect_agents(output, plotting=False)
            self.assertEqual(states["writing"], "completed")
            self.assertEqual(states["refinement"], "running")

            self.create(output, "final_paper.pdf")
            states = inspect_agents(output, plotting=False)
            self.assertEqual(states["refinement"], "completed")
            self.assertEqual(states["plotting"], "disabled")
            self.assertNotIn("running", states.values())

    def test_plotting_waits_for_both_parallel_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            self.create(output, "outline.json")
            self.create(output, "literature_agent_output/references.bib")
            self.create(output, "literature_agent_output/citation_map.json")
            states = inspect_agents(output, plotting=True)
            self.assertEqual(states["plotting"], "running")
            self.assertEqual(states["literature"], "completed")
            self.assertEqual(states["writing"], "waiting")
            self.create(output, "plotting_results.json")
            self.assertEqual(inspect_agents(output, plotting=True)["writing"], "running")


if __name__ == "__main__":
    unittest.main()
