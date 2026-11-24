"""M14 (manifesto de proveniência) e M11 (rascunho de declaração de uso de IA)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from ai_declaration import ANNEX_URL, FILL, build_declaration
from run_manifest import RunManifest, canonical_hash

WORKER = Path(__file__).resolve().parents[1] / "worker"
RECORD = {
    "title": "Sala de aula invertida no ensino técnico", "created_at": "2026-11-24T10:00:00+00:00",
    "template": "abnt-artigo", "language": "pt-BR", "plotting": False,
    "model": "gemini-3-flash-preview", "reflection_model": "gemini-3.1-pro-preview",
    "neon_review_requested": False, "ai_auth_mode": "user_gemini",
}
SECRET = "AQ.chave-super-secreta-que-nunca-pode-vazar-123"
ENV = {"SCRIPTORIUM_RELEASE_SHA": "abc123", "PAPER_ORCHESTRA_COMMIT": "d9bae99",
       "GEMINI_API_KEY": SECRET, "GOOGLE_API_KEY": SECRET}


def clock():
    clock.n += 1
    return f"2026-11-24T10:{clock.n:02d}:00+00:00"


clock.n = 0


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "idea_sparse.md").write_text("ideia original", encoding="utf-8")
        (self.tmp / "out.pdf").write_bytes(b"%PDF-1.7 teste")
        self.manifest = RunManifest("a" * 32, "uid1", RECORD, ENV, WORKER, clock=clock)

    def build(self):
        m = self.manifest
        m.add_input("idea_sparse.md", self.tmp / "idea_sparse.md")
        m.add_sources([{"id": "s1", "name": "Bergmann.pdf", "format": "pdf", "sha256": "f" * 64,
                        "status": "included", "risk_level": "attention",
                        "risk_flags": [{"code": "ignore_instructions", "count": 1}],
                        "object_path": "library/uid1/s1/original.pdf"}])
        m.event("Agente de redação")
        m.add_output("final_paper.pdf", self.tmp / "out.pdf")
        return m.finish("completed")

    def test_never_contains_secrets_or_storage_paths(self):
        text = json.dumps(self.build(), ensure_ascii=False)
        self.assertNotIn(SECRET, text)
        self.assertNotIn("library/uid1", text)

    def test_records_versions_models_and_hashes(self):
        data = self.build()
        self.assertEqual(data["software"]["paper_orchestra"]["commit"], "d9bae99")
        self.assertEqual(data["software"]["paper_orchestra"]["upstream_id"], "R02")
        self.assertEqual(data["software"]["scriptorium_release_sha"], "abc123")
        self.assertIn("runner.py", data["software"]["worker_modules_sha256"])
        self.assertEqual(data["request"]["reflection_model"], "gemini-3.1-pro-preview")
        self.assertIn("chave pessoal", data["request"]["provider"])
        self.assertEqual(len(data["inputs"]["idea_sparse.md"]["sha256"]), 64)
        self.assertEqual(data["outputs"]["final_paper.pdf"]["size"], len(b"%PDF-1.7 teste"))
        self.assertEqual(data["sources"][0]["risk_flags"][0]["code"], "ignore_instructions")
        self.assertEqual(data["costs"]["status"], "not_measured")
        self.assertTrue(data["corpus_snapshot"].startswith("sha256:"))

    def test_content_hash_detects_tampering(self):
        data = self.build()
        body = {k: v for k, v in data.items() if k != "content_sha256"}
        self.assertEqual(canonical_hash(body), data["content_sha256"])
        body["final_status"] = "adulterado"
        self.assertNotEqual(canonical_hash(body), data["content_sha256"])

    def test_snapshot_changes_when_source_changes(self):
        first = self.build()["corpus_snapshot"]
        other = RunManifest("b" * 32, "uid1", RECORD, ENV, WORKER, clock=clock)
        other.add_input("idea_sparse.md", self.tmp / "idea_sparse.md")
        other.add_sources([{"id": "s1", "sha256": "0" * 64}])
        self.assertNotEqual(first, other.finish("completed")["corpus_snapshot"])

    def test_plotting_records_image_model(self):
        data = RunManifest("c" * 32, "u", {**RECORD, "plotting": True}, ENV, WORKER, clock=clock).finish("completed")
        self.assertEqual(data["request"]["image_model"], "gemini-3-pro-image-preview")


class DeclarationTest(unittest.TestCase):
    def test_draft_lists_models_and_leaves_human_fields(self):
        manifest = RunManifest("d" * 32, "u", RECORD, ENV, WORKER, clock=clock).finish("completed")
        text = build_declaration(manifest, {"outline": "completed", "literature": "completed",
                                            "plotting": "disabled", "writing": "completed",
                                            "refinement": "completed"})
        self.assertIn("RASCUNHO", text)
        self.assertIn(ANNEX_URL, text)
        self.assertIn("gemini-3-flash-preview", text)
        self.assertIn("gemini-3.1-pro-preview", text)
        self.assertNotIn("Geração de gráficos", text)
        self.assertIn("não são autoras nem coautoras", text)
        self.assertIn("Autorização prévia", text)
        self.assertGreaterEqual(text.count(FILL), 8)
        self.assertNotIn(SECRET, text)
        # Não pode afirmar conformidade com a norma.
        self.assertNotIn("está em conformidade", text.lower())
        self.assertIn("não garante conformidade", text)

    def test_neon_and_plotting_listed_only_when_used(self):
        record = {**RECORD, "plotting": True, "neon_review_requested": True, "reflection_model": RECORD["model"]}
        manifest = RunManifest("e" * 32, "u", record, ENV, WORKER, clock=clock).finish("completed")
        text = build_declaration(manifest, {"plotting": "completed"})
        self.assertIn("gemini-4-neon", text)
        self.assertIn("gemini-3-pro-image-preview", text)
        self.assertIn("redação e refinamento", text)


if __name__ == "__main__":
    unittest.main()
