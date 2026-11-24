"""Separação de custos: infraestrutura no projeto, tokens na chave de quem pesquisa."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BillingSeparationTest(unittest.TestCase):
    """Checagens estáticas: a API e o worker não podem voltar a usar o projeto por engano."""

    def setUp(self):
        self.api = (ROOT / "api" / "main.py").read_text(encoding="utf-8")
        self.worker = (ROOT / "worker" / "runner.py").read_text(encoding="utf-8")

    def test_project_ai_is_opt_in_and_off_by_default(self):
        for source in (self.api, self.worker):
            self.assertIn('os.getenv("SCRIPTORIUM_ALLOW_PROJECT_AI", "false")', source)

    def test_new_research_uses_project_only_with_exception(self):
        self.assertIn('"ai_auth_mode": "admin_vertex" if project_ai else "user_gemini"', self.api)
        # Nenhum outro ponto decide "admin_vertex" só por ser administrador.
        self.assertIsNone(re.search(r'admin_vertex"\s+if\s+access\["admin"\]', self.api))

    def test_admin_can_manage_own_key(self):
        self.assertNotIn("A conta administradora usa a configuração existente", self.api)
        self.assertNotIn("A credencial do administrador não é gerenciada aqui", self.api)

    def test_worker_fails_closed_for_project_ai(self):
        self.assertIn('if auth_mode == "admin_vertex" and not ALLOW_PROJECT_AI:', self.worker)

    def test_neon_uses_personal_key(self):
        self.assertIn('genai.Client(api_key=agent_env["GEMINI_API_KEY"])', self.worker)
        self.assertIn("client=neon_client", self.worker)

    def test_embeddings_follow_research_identity(self):
        embeddings = (ROOT / "worker" / "embeddings.py").read_text(encoding="utf-8")
        self.assertIn('if auth_mode == "user_gemini":', embeddings)
        self.assertIn("genai.Client(api_key=key)", embeddings)


if __name__ == "__main__":
    unittest.main()
