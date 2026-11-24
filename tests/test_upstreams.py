"""Registro de upstreams: validade, pins no código, docs gerados e vigia sem rede."""
import copy
import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("upstreams", ROOT / "scripts" / "upstreams.py")
up = importlib.util.module_from_spec(spec)
spec.loader.exec_module(up)

TODAY = date(2026, 11, 30)


def fake_fetch(responses):
    def fetch(url):
        for prefix, body in responses.items():
            if url.startswith(prefix):
                return body
        return {"_http_error": 404}
    return fetch


def entry(**extra):
    base = {"id": "R99", "name": "Teste", "kind": "biblioteca", "adopted": True,
            "license_spdx": "MIT", "review_frequency": "mensal", "last_checked": "2026-11-24",
            "canonical_url": "https://github.com/org/lib", "github": "org/lib"}
    base.update(extra)
    return base


def texts(findings, level):
    return " ".join(f["text"] for f in findings if f["level"] == level)


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = up.load()

    def test_registry_is_valid_and_docs_are_current(self):
        self.assertEqual(up.check(self.registry), [])
        for path, content in up.rendered_files(self.registry).items():
            self.assertEqual(path.read_text(encoding="utf-8"), content,
                             f"{path.name} desatualizado: rode scripts/upstreams.py render")

    def test_all_plan_ids_and_modules_present(self):
        ids = {u["id"] for u in self.registry["upstreams"]}
        self.assertTrue({f"R{n:02d}" for n in range(1, 30)} <= ids)
        self.assertEqual(len(self.registry["modules"]), 27)

    def test_every_module_points_to_origins(self):
        for module in self.registry["modules"]:
            self.assertTrue(module["upstreams"], module["id"])

    def test_wrong_paper_orchestra_pin_is_detected(self):
        broken = copy.deepcopy(self.registry)
        next(u for u in broken["upstreams"] if u["id"] == "R02")["pinned"] = "0" * 40
        self.assertTrue(any("R02" in e for e in up.check(broken)))

    def test_unknown_origin_comment_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("api", "worker", "scripts"):
                (root / folder).mkdir()
            (root / "worker" / "novo.py").write_text('"""Origem: R03 e R98."""\n', encoding="utf-8")
            errors = up.check_origin_comments({"R03"}, root)
        self.assertEqual(len(errors), 1)
        self.assertIn("R98", errors[0])

    def test_missing_required_field_is_detected(self):
        broken = copy.deepcopy(self.registry)
        del broken["upstreams"][3]["update_policy"]
        self.assertTrue(any("update_policy" in e for e in up.check(broken)))


class WatchTest(unittest.TestCase):
    def test_new_release_and_license_change_raise_alerts(self):
        fetch = fake_fetch({
            "https://api.github.com/repos/org/lib/releases/latest": {"tag_name": "v2.0.0"},
            "https://api.github.com/repos/org/lib": {"full_name": "org/lib", "default_branch": "main",
                                                     "license": {"spdx_id": "GPL-3.0"}},
        })
        findings = up.watch_entry(entry(latest_reviewed="v1.0.0"), fetch, TODAY)
        alerts = texts(findings, "alerta")
        self.assertIn("v2.0.0", alerts)
        self.assertIn("GPL-3.0", alerts)

    def test_moved_and_archived_repository(self):
        fetch = fake_fetch({
            "https://api.github.com/repos/org/lib": {"full_name": "nova-org/lib", "archived": True,
                                                     "license": {"spdx_id": "MIT"}},
            "https://api.github.com/repos/nova-org/lib/releases/latest": {"tag_name": "v1"},
        })
        alerts = texts(up.watch_entry(entry(latest_reviewed="v1"), fetch, TODAY), "alerta")
        self.assertIn("movido", alerts)
        self.assertIn("arquivado", alerts)

    def test_commit_tracking_compares_sha(self):
        fetch = fake_fetch({
            "https://api.github.com/repos/org/lib/commits/main": {"sha": "b" * 40},
            "https://api.github.com/repos/org/lib": {"full_name": "org/lib", "default_branch": "main",
                                                     "license": {"spdx_id": "MIT"}},
        })
        findings = up.watch_entry(entry(track="commits", latest_reviewed="a" * 40), fetch, TODAY)
        self.assertIn("b" * 40, texts(findings, "alerta"))

    def test_network_failure_never_raises(self):
        fetch = fake_fetch({})
        findings = up.watch_entry(entry(pypi=["lib"], npm=["lib"]), fetch, TODAY)
        self.assertTrue(findings)
        self.assertEqual(texts(findings, "alerta"), "")

    def test_overdue_manual_review(self):
        manual = entry(github=None, last_checked="2026-01-01", review_frequency="semestral")
        self.assertIn("vencida", texts(up.watch_entry(manual, fake_fetch({}), TODAY), "aviso"))

    def test_npm_version_differs_from_pin(self):
        fetch = fake_fetch({"https://registry.npmjs.org/firebase/latest": {"version": "12.0.0", "license": "Apache-2.0"}})
        findings = up.watch_entry(entry(github=None, npm=["firebase"], pinned="11.10.0"), fetch, TODAY)
        self.assertIn("12.0.0", texts(findings, "alerta"))

    def test_report_groups_by_level(self):
        registry = {"upstreams": [entry(github=None, last_checked="2026-01-01")]}
        report, findings = up.watch(registry, fake_fetch({}), TODAY)
        self.assertIn("Avisos (conferir)", report)
        self.assertTrue(report.startswith("# Rastreio de upstreams: 2026-11-30"))


if __name__ == "__main__":
    unittest.main()
