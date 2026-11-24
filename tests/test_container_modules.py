"""Garante que as imagens Docker contêm todos os módulos locais importados.

Teste estático (sem Docker e sem dependências externas): lê as instruções COPY
de cada Dockerfile e percorre os imports a partir do ponto de entrada. Um módulo
local importado e não copiado faria o contêiner falhar com ModuleNotFoundError.
"""
import ast
import re
import unittest
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPY_LINE = re.compile(r"^\s*COPY\s+(.+)$", re.IGNORECASE)


def copied_modules(service_dir: Path) -> set[str]:
    """Nomes de módulos .py do diretório que o Dockerfile copia para a imagem."""
    local = {p.name for p in service_dir.glob("*.py")}
    copied: set[str] = set()
    for line in (service_dir / "Dockerfile").read_text(encoding="utf-8").splitlines():
        match = COPY_LINE.match(line)
        if not match:
            continue
        parts = [p for p in match.group(1).split() if not p.startswith("--")]
        for source in parts[:-1]:
            source = source.removeprefix("./")
            copied.update(name for name in local if fnmatch(name, source))
    return {name[:-3] for name in copied}


def local_imports(path: Path, local: set[str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split(".")[0]]
        else:
            continue
        found.update(name for name in names if name in local)
    return found


def required_modules(service_dir: Path, entrypoint: str) -> set[str]:
    local = {p.stem for p in service_dir.glob("*.py")}
    pending, seen = [entrypoint], set()
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        pending.extend(local_imports(service_dir / f"{module}.py", local))
    return seen


class ContainerModulesTest(unittest.TestCase):
    def check(self, service: str, entrypoint: str):
        service_dir = ROOT / service
        missing = required_modules(service_dir, entrypoint) - copied_modules(service_dir)
        self.assertFalse(
            missing,
            f"{service}/Dockerfile não copia módulos importados: {sorted(missing)}",
        )

    def test_api_image_has_all_modules(self):
        self.check("api", "main")

    def test_worker_image_has_all_modules(self):
        self.check("worker", "runner")

    def test_detects_missing_module(self):
        # Regressão: a lista antiga da API não incluía estes módulos.
        old_copy = {"library", "access", "credentials", "main"}
        missing = required_modules(ROOT / "api", "main") - old_copy
        self.assertIn("model_access", missing)
        self.assertIn("access_requests", missing)


if __name__ == "__main__":
    unittest.main()
