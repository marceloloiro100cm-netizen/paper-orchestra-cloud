#!/usr/bin/env python3
"""Registro de upstreams do Scriptorium: validar, gerar documentação e vigiar.

Fonte única: docs/upstreams.json (IDs R01-R29 do plano V2; R30+ dependências
já em uso). Usa somente a biblioteca padrão, para rodar no CI sem instalar nada.

  python scripts/upstreams.py check    # valida registro, pins e docs gerados
  python scripts/upstreams.py render   # regrava docs/UPSTREAMS.md e docs/V2-MODULOS.md
  python scripts/upstreams.py watch [--output relatorio.md]
      # consulta GitHub/PyPI/npm e lista novidades, mudanças de licença,
      # repositórios movidos/arquivados e revisões manuais vencidas
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "upstreams.json"
UPSTREAMS_MD = ROOT / "docs" / "UPSTREAMS.md"
MODULES_MD = ROOT / "docs" / "V2-MODULOS.md"

KINDS = {"codigo_proprio", "biblioteca", "api", "artigo", "prototipo",
         "normativo", "ferramenta", "servico"}
FREQUENCIES = {"por_pr": None, "mensal": 31, "trimestral": 92, "semestral": 183}
STATUSES = {"nao_iniciado": "não iniciado", "parcial": "parcial", "implementado": "implementado"}
REQUIRED = ("id", "name", "kind", "canonical_url", "license_spdx", "license_status",
            "adopted", "modules", "update_policy", "review_frequency", "owner", "last_checked")
OPTIONAL = ("release_url", "issues_url", "security_url", "changelog_url",
            "model_weights_license", "pinned", "installed_version", "latest_reviewed",
            "risk", "migration_note", "benchmark_result", "rollback_sha",
            "github", "pypi", "npm", "track", "used_in")
# Valores que não são identificadores SPDX (não comparar com o GitHub).
NON_SPDX = ("a conferir", "a definir", "termos", "não se aplica", "políticas")
ORIGIN_REF = re.compile(r"Origem:.*")
UPSTREAM_ID = re.compile(r"\bR\d{2}\b")


def load(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def derived(entry: dict) -> dict:
    """Completa URLs padrão de repositórios GitHub sem repetir no JSON."""
    out = {key: None for key in OPTIONAL}
    out.update(entry)
    repo = entry.get("github")
    if repo:
        base = f"https://github.com/{repo}"
        out["release_url"] = out["release_url"] or (
            base + "/commits" if entry.get("track") == "commits" else base + "/releases")
        out["issues_url"] = out["issues_url"] or base + "/issues"
        out["security_url"] = out["security_url"] or base + "/security/advisories"
    return out


# --------------------------------------------------------------------- check

def _path_part(used: str) -> str:
    return used.split(" (")[0].strip()


def check(registry: dict, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    ups = registry.get("upstreams", [])
    ids = [u.get("id") for u in ups]
    if len(ids) != len(set(ids)):
        errors.append("IDs de upstream duplicados")
    known = set(ids)
    for u in ups:
        uid = u.get("id", "?")
        if not re.fullmatch(r"R\d{2}", str(uid)):
            errors.append(f"{uid}: ID fora do padrão Rnn")
        for key in REQUIRED:
            if key not in u or u[key] in (None, ""):
                errors.append(f"{uid}: campo obrigatório ausente: {key}")
        for key in u:
            if key not in REQUIRED and key not in OPTIONAL:
                errors.append(f"{uid}: campo desconhecido: {key}")
        if u.get("kind") not in KINDS:
            errors.append(f"{uid}: kind inválido: {u.get('kind')}")
        if u.get("review_frequency") not in FREQUENCIES:
            errors.append(f"{uid}: review_frequency inválida")
        if not str(u.get("canonical_url", "")).startswith("https://"):
            errors.append(f"{uid}: canonical_url deve ser https")
        try:
            date.fromisoformat(str(u.get("last_checked")))
        except ValueError:
            errors.append(f"{uid}: last_checked não é data ISO")
        for used in u.get("used_in") or []:
            if not (root / _path_part(used)).exists():
                errors.append(f"{uid}: used_in aponta para caminho inexistente: {used}")
    modules = registry.get("modules", [])
    expected = {f"M{n:02d}" for n in range(1, 28)}
    found = [m.get("id") for m in modules]
    if sorted(found) != sorted(expected):
        errors.append("A lista de módulos deve conter M01 a M27 exatamente uma vez")
    module_ids = set(found)
    for m in modules:
        mid = m.get("id", "?")
        if m.get("status") not in STATUSES:
            errors.append(f"{mid}: status inválido")
        for ref in m.get("upstreams", []):
            if ref not in known:
                errors.append(f"{mid}: upstream desconhecido {ref}")
        for dep in m.get("depends_on", []):
            if dep not in module_ids:
                errors.append(f"{mid}: dependência desconhecida {dep}")
        if m.get("status") != "nao_iniciado" and not m.get("files"):
            errors.append(f"{mid}: módulo {m.get('status')} precisa listar arquivos")
        for path in m.get("files", []):
            if not (root / path).exists():
                errors.append(f"{mid}: arquivo inexistente: {path}")
    errors += check_pins(registry, root)
    errors += check_origin_comments(known, root)
    return errors


def _entry(registry: dict, uid: str) -> dict:
    return next((u for u in registry["upstreams"] if u["id"] == uid), {})


def check_pins(registry: dict, root: Path) -> list[str]:
    """Versões fixadas no código precisam bater com o registro."""
    errors = []
    dockerfile = (root / "worker" / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"ARG PAPER_ORCHESTRA_COMMIT=([0-9a-f]{40})", dockerfile)
    if not match or match.group(1) != _entry(registry, "R02").get("pinned"):
        errors.append("R02: commit do PaperOrchestra no worker/Dockerfile difere do registro")
    app = (root / "public" / "app.js").read_text(encoding="utf-8")
    versions = set(re.findall(r"gstatic\.com/firebasejs/([0-9.]+)/", app))
    if versions != {_entry(registry, "R39").get("pinned")}:
        errors.append(f"R39: versão do Firebase JS em public/app.js ({sorted(versions)}) difere do registro")
    osv_pin = _entry(registry, "R40").get("pinned")
    for name in ("osv-scanner-pr.yml", "osv-scanner-scheduled.yml"):
        path = root / ".github" / "workflows" / name
        if path.exists():
            refs = set(re.findall(r"osv-scanner-action/[^@\"]+@([^\"\s]+)", path.read_text(encoding="utf-8")))
            if refs != {osv_pin}:
                errors.append(f"R40: {name} usa {sorted(refs)}, registro diz {osv_pin}")
    return errors


def check_origin_comments(known: set[str], root: Path) -> list[str]:
    """Todo 'Origem: Rnn' citado no código precisa existir no registro."""
    errors = []
    for folder in ("api", "worker", "scripts"):
        for path in sorted((root / folder).rglob("*.py")):
            for line in path.read_text(encoding="utf-8").splitlines():
                for match in ORIGIN_REF.finditer(line):
                    for ref in UPSTREAM_ID.findall(match.group()):
                        if ref not in known:
                            errors.append(f"{path.relative_to(root)}: cita {ref}, ausente do registro")
    return errors


# -------------------------------------------------------------------- render

def _cell(value) -> str:
    if value in (None, "", []):
        return "-"
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_upstreams(registry: dict) -> str:
    lines = [
        "# Registro de upstreams (origens externas)",
        "",
        "<!-- Arquivo gerado por scripts/upstreams.py render a partir de docs/upstreams.json. Não edite à mão. -->",
        "",
        f"Atualizado em {registry['updated_at']}. Documento de origem: {registry['source_document']}.",
        "",
    ]
    lines += [f"- {note}" for note in registry.get("notes", [])]
    lines += ["", "## Resumo", "",
              "| ID | Componente | Tipo | Em uso | Licença | Versão fixada | Módulos |",
              "|---|---|---|---|---|---|---|"]
    for u in registry["upstreams"]:
        lines.append(f"| {u['id']} | [{_cell(u['name'])}]({u['canonical_url']}) | {u['kind']} | "
                     f"{'sim' if u['adopted'] else 'não'} | {_cell(u['license_spdx'])} | "
                     f"{_cell(u.get('pinned'))} | {_cell(u['modules'])} |")
    lines += ["", "## Fichas", ""]
    labels = [
        ("canonical_url", "Fonte canônica"), ("release_url", "Versões"), ("issues_url", "Erros e correções"),
        ("security_url", "Avisos de segurança"), ("changelog_url", "Histórico de mudanças"),
        ("license_spdx", "Licença (SPDX)"), ("license_status", "Situação da licença"),
        ("model_weights_license", "Licença dos pesos"), ("pinned", "Versão fixada"),
        ("installed_version", "Versão instalada"), ("latest_reviewed", "Última versão revisada"),
        ("used_in", "Onde é usado"), ("update_policy", "Política de atualização"),
        ("review_frequency", "Frequência de revisão"), ("risk", "Risco"),
        ("migration_note", "Nota de migração"), ("benchmark_result", "Resultado de benchmark"),
        ("rollback_sha", "Rollback"), ("owner", "Responsável"), ("last_checked", "Última checagem"),
    ]
    for raw in registry["upstreams"]:
        u = derived(raw)
        lines += [f"### {u['id']} · {u['name']}", ""]
        for key, label in labels:
            lines.append(f"- **{label}:** {_cell(u.get(key))}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_modules(registry: dict) -> str:
    names = {u["id"]: u["name"] for u in registry["upstreams"]}
    count = {key: sum(m["status"] == key for m in registry["modules"]) for key in STATUSES}
    lines = [
        "# Scriptorium V2: situação dos 27 módulos",
        "",
        "<!-- Arquivo gerado por scripts/upstreams.py render a partir de docs/upstreams.json. Não edite à mão. -->",
        "",
        f"Atualizado em {registry['updated_at']}. Implementados: {count['implementado']}; "
        f"parciais: {count['parcial']}; não iniciados: {count['nao_iniciado']}.",
        "",
        "As ondas seguem o plano V2 (0: base segura; 1: leitura escalável; 2: busca e evidência; "
        "3: auditoria científica; 4: pesquisa guiada; 5: ecossistema editorial).",
        "",
        "| Módulo | Nome | Prioridade | Onda | Situação | Origens | Próximo passo |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in sorted(registry["modules"], key=lambda x: (x["wave"], x["id"])):
        origins = ", ".join(f"{ref} ({names.get(ref, '?')})" for ref in m["upstreams"])
        lines.append(f"| {m['id']} | {_cell(m['name'])} | {m['priority']} | {m['wave']} | "
                     f"{STATUSES[m['status']]} | {_cell(origins)} | {_cell(m.get('next_step'))} |")
    lines += ["", "## Arquivos por módulo", ""]
    for m in registry["modules"]:
        if m.get("files"):
            lines.append(f"- **{m['id']}:** {', '.join('`' + f + '`' for f in m['files'])}")
    return "\n".join(lines).rstrip() + "\n"


def rendered_files(registry: dict) -> dict[Path, str]:
    return {UPSTREAMS_MD: render_upstreams(registry), MODULES_MD: render_modules(registry)}


# --------------------------------------------------------------------- watch

def http_json(url: str, token: str | None = None):
    headers = {"Accept": "application/json", "User-Agent": "scriptorium-upstream-watch"}
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"
    try:
        with urlopen(Request(url, headers=headers), timeout=20) as response:
            return json.loads(response.read(5_000_000).decode("utf-8"))
    except HTTPError as exc:
        return {"_http_error": exc.code}
    except (URLError, TimeoutError, OSError, ValueError):
        return {"_http_error": 0}


def _github_latest(repo: str, track: str | None, default_branch: str, fetch) -> str | None:
    if track != "commits":
        release = fetch(f"https://api.github.com/repos/{repo}/releases/latest")
        if release.get("tag_name"):
            return release["tag_name"]
        tags = fetch(f"https://api.github.com/repos/{repo}/tags?per_page=1")
        if isinstance(tags, list) and tags:
            return tags[0].get("name")
    commit = fetch(f"https://api.github.com/repos/{repo}/commits/{quote(default_branch, safe='')}")
    return commit.get("sha") if isinstance(commit, dict) else None


def _same_license(registered: str, reported: str | None) -> bool:
    return bool(reported) and registered.lower() == reported.lower()


def _one_line(text, limit: int = 80) -> str:
    return " ".join(str(text or "").split())[:limit]


def _range_covered_by_dependabot(entry: dict) -> bool:
    """Dependência pip com faixa de versões: o Dependabot acompanha a faixa."""
    return bool(entry.get("pypi")) and str(entry.get("pinned") or "").lstrip().startswith((">=", "<", "~=", "=="))


def watch_entry(entry: dict, fetch, today: date) -> list[dict]:
    """Retorna achados de um upstream. Nunca lança exceção por falha de rede."""
    findings = []
    uid, reviewed = entry["id"], entry.get("latest_reviewed")
    registered_license = str(entry.get("license_spdx", ""))
    spdx_comparable = not registered_license.lower().startswith(NON_SPDX)

    def add(level, text):
        findings.append({"id": uid, "name": entry["name"], "level": level, "text": text})

    registry_licenses: set[str] = set()
    package_findings: list[tuple[str, str]] = []
    for package in entry.get("pypi") or []:
        data = fetch(f"https://pypi.org/pypi/{quote(package, safe='')}/json")
        info = data.get("info") if isinstance(data, dict) else None
        if not info:
            package_findings.append(("aviso", f"PyPI indisponível para {package}."))
            continue
        license_text = _one_line(info.get("license_expression") or info.get("license"), 60)
        registry_licenses.add(license_text.lower())
        package_findings.append(("info", f"PyPI {package}: versão {info.get('version')}; "
                                         f"licença declarada: {license_text or 'não informada'}."))
    for package in entry.get("npm") or []:
        data = fetch(f"https://registry.npmjs.org/{quote(package, safe='@')}/latest")
        if "_http_error" in data:
            package_findings.append(("aviso", f"npm indisponível para {package}."))
            continue
        version = data.get("version")
        pinned = entry.get("pinned")
        registry_licenses.add(_one_line(data.get("license"), 60).lower())
        level = "alerta" if pinned and version and version != pinned and entry.get("adopted") else "info"
        package_findings.append((level, f"npm {package}: versão {version} (fixada: {pinned or '-'}); "
                                        f"licença: {_one_line(data.get('license'), 60)}."))

    repo = entry.get("github")
    if repo:
        info = fetch(f"https://api.github.com/repos/{repo}")
        if "_http_error" in info:
            add("aviso", f"GitHub indisponível para {repo} (HTTP {info['_http_error']}); conferir manualmente.")
        else:
            full_name = info.get("full_name") or repo
            if full_name.lower() != repo.lower():
                add("alerta", f"Repositório movido: {repo} agora é {full_name}. Atualizar o registro.")
            if info.get("archived"):
                add("alerta", f"Repositório arquivado em {full_name}: sem manutenção.")
            spdx = (info.get("license") or {}).get("spdx_id")
            if spdx in (None, "NOASSERTION"):
                if registered_license.lower() in registry_licenses:
                    add("info", f"GitHub não identifica a licença, mas o pacote publicado declara {registered_license}.")
                elif entry["kind"] != "codigo_proprio":
                    add("aviso", "GitHub não identifica a licença; conferir o arquivo LICENSE.")
            elif spdx_comparable and not _same_license(registered_license, spdx):
                add("alerta", f"Licença divergente: registro diz {registered_license}, GitHub informa {spdx}.")
            elif not spdx_comparable:
                add("info", f"GitHub informa licença {spdx}; registro ainda diz '{registered_license}'.")
            # O próprio projeto é acompanhado por PR e CI, não por versão revisada.
            latest = None if entry["kind"] == "codigo_proprio" else _github_latest(
                full_name, entry.get("track"), info.get("default_branch") or "main", fetch)
            if latest:
                if reviewed and latest != reviewed:
                    add("alerta", f"Nova versão em {full_name}: {latest} (revisada: {reviewed}).")
                elif not reviewed and _range_covered_by_dependabot(entry):
                    add("info", f"Versão atual: {latest}; faixa {entry['pinned']} acompanhada pelo Dependabot.")
                elif not reviewed and entry.get("adopted"):
                    add("aviso", f"Em uso sem versão revisada registrada; versão atual: {latest}.")
                elif not reviewed:
                    add("info", f"Versão atual: {latest} (ainda não adotado).")
    for level, text in package_findings:
        add(level, text)
    days = FREQUENCIES.get(entry.get("review_frequency"))
    if days:
        due = date.fromisoformat(entry["last_checked"]) + timedelta(days=days)
        if today > due:
            add("aviso", f"Revisão {entry['review_frequency']} vencida desde {due.isoformat()}: "
                         f"conferir {entry['canonical_url']} e atualizar last_checked.")
    return findings


def watch(registry: dict, fetch, today: date | None = None) -> tuple[str, list[dict]]:
    today = today or date.today()
    findings = []
    for entry in registry["upstreams"]:
        findings += watch_entry(entry, fetch, today)
    order = {"alerta": 0, "aviso": 1, "info": 2}
    findings.sort(key=lambda f: (order[f["level"]], f["id"]))
    counts = {level: sum(f["level"] == level for f in findings) for level in order}
    lines = [
        f"# Rastreio de upstreams: {today.isoformat()}",
        "",
        f"Alertas: {counts['alerta']} · avisos: {counts['aviso']} · informativos: {counts['info']}.",
        "",
        "Fonte: `docs/upstreams.json`. Para adotar uma atualização, siga o fluxo do plano V2: "
        "issue, branch com versão fixada, testes, homologação e registro do commit adotado.",
        "",
    ]
    titles = {"alerta": "Alertas (ação necessária)", "aviso": "Avisos (conferir)", "info": "Informativo"}
    for level in order:
        group = [f for f in findings if f["level"] == level]
        if not group:
            continue
        lines += [f"## {titles[level]}", ""]
        lines += [f"- **{f['id']} · {f['name']}:** {f['text']}" for f in group]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n", findings


# ---------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("render")
    watch_cmd = sub.add_parser("watch")
    watch_cmd.add_argument("--output")
    args = parser.parse_args(argv)
    registry = load()
    if args.command == "render":
        for path, content in rendered_files(registry).items():
            path.write_text(content, encoding="utf-8")
            print("gerado:", path.relative_to(ROOT))
        return 0
    if args.command == "check":
        errors = check(registry)
        for path, content in rendered_files(registry).items():
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                errors.append(f"{path.relative_to(ROOT)} desatualizado: rode scripts/upstreams.py render")
        for error in errors:
            print("ERRO:", error)
        print("registro válido" if not errors else f"{len(errors)} erro(s)")
        return 1 if errors else 0
    token = os.getenv("GITHUB_TOKEN")
    report, findings = watch(registry, lambda url: http_json(url, token))
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    print(report)
    print(json.dumps({"alertas": sum(f["level"] == "alerta" for f in findings)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
