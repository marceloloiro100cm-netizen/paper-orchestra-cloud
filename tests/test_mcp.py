"""Modo sem API (MCP): fluxo de etapas, cabeças, passes, validações e servidor.

Roda sem rede e sem FastAPI: usa o SDK oficial do MCP com transporte ASGI em memória.
"""
import asyncio
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

import mcp_flow as flow  # noqa: E402

try:
    import httpx2  # noqa: E402
    import mcp_server  # noqa: E402
    from mcp import ClientSession  # noqa: E402
    from mcp.client.streamable_http import streamable_http_client  # noqa: E402
    HAVE_SDK = True
except ImportError:  # o SDK do MCP é dependência da API; sem ele, só a lógica pura roda
    HAVE_SDK = False


# ------------------------------------------------------------------ fakes
class Snap:
    def __init__(self, data):
        self.data, self.exists = data, data is not None

    def to_dict(self):
        return None if self.data is None else json.loads(json.dumps(self.data))


class Ref:
    def __init__(self, store, path):
        self.store, self.path = store, path

    def get(self):
        return Snap(self.store.get(self.path))

    def set(self, value):
        self.store[self.path] = json.loads(json.dumps(value))

    def create(self, value):
        assert self.path not in self.store
        self.set(value)

    def update(self, fields):
        self.store[self.path] = {**self.store[self.path], **json.loads(json.dumps(fields))}


class Query:
    def __init__(self, store, name, conds=()):
        self.store, self.name, self.conds = store, name, conds

    def where(self, field, op, value):
        return Query(self.store, self.name, self.conds + ((field, value),))

    def limit(self, n):
        return self

    def stream(self):
        for (name, _), value in list(self.store.items()):
            if name == self.name and all(value.get(f) == v for f, v in self.conds):
                yield Snap(value)


class Collection(Query):
    def document(self, key):
        return Ref(self.store, (self.name, key))


class DB:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return Collection(self.store, name)


class Blob:
    def __init__(self, bucket, name):
        self.bucket, self.name = bucket, name
        self.generation, self.updated = 1, datetime(2026, 11, 25, tzinfo=timezone.utc)

    def exists(self):
        return self.name in self.bucket.objects

    def upload_from_string(self, data, content_type=None):
        self.bucket.objects[self.name] = data.encode() if isinstance(data, str) else data

    def upload_from_filename(self, path, content_type=None):
        self.bucket.objects[self.name] = Path(path).read_bytes()

    def download_as_bytes(self):
        return self.bucket.objects[self.name]

    def download_to_filename(self, path):
        Path(path).write_bytes(self.bucket.objects[self.name])


class Bucket:
    def __init__(self):
        self.objects = {}

    def blob(self, name):
        return Blob(self, name)

    def list_blobs(self, prefix=""):
        return [Blob(self, n) for n in sorted(self.objects) if n.startswith(prefix)]


UID = "u" * 28
SOURCE_TEXT = [
    "A gamificação aumentou o engajamento dos estudantes em cursos introdutórios de programação, "
    "segundo os dados coletados ao longo de dois semestres letivos.",
    "Os autores relatam que a motivação intrínseca não se manteve depois que as recompensas foram "
    "retiradas, o que sugere efeito de novidade.",
    "A revisão sistemática seguiu o protocolo de Kitchenham, com busca em quatro bases e critérios de "
    "inclusão definidos antes da triagem.",
]


def seed_project(db, bucket, status="pronto"):
    """Projeto já preparado pelo worker: manifesto, referências e trechos derivados."""
    pid = "a" * 32
    sources, manifest, refs = [], [], []
    for n in range(3):
        item_id = f"{n:032x}"
        sha = f"{n:064x}"
        derived = f"library/{UID}/derived/pymupdf-1/sec-para-1200/{sha}.json"
        chunks = [{"chunk_id": f"{item_id[:12]}-{k:04d}-abcd1234", "text": SOURCE_TEXT[(n + k) % 3] +
                   f" Trecho {k} da fonte {n}.", "pages": [k + 1, k + 1], "heading_path": ["Resultados"],
                   "char_count": 200} for k in range(4)]
        bucket.blob(derived).upload_from_string(json.dumps({"schema": "scriptorium.derived/1", "chunks": chunks,
                                                            "document": {"parser": "pymupdf"}}))
        key = f"fonte_Autor{n}2024"
        sources.append({"id": item_id, "name": f"fonte{n}.pdf", "format": "pdf", "sha256": sha,
                        "object_path": f"library/{UID}/{item_id}/fonte{n}.pdf"})
        manifest.append({"id": item_id, "name": f"fonte{n}.pdf", "format": "pdf", "sha256": sha,
                         "key": key, "derived": derived, "chunks": 4})
        refs.append({"type": "article", "key": key, "source_id": item_id,
                     "fields": {"author": f"Autor{n}, Ana", "title": f"Estudo {n}", "year": "2024"}})
    db.collection("mcp_projects").document(pid).set({
        "id": pid, "owner_uid": UID, "title": "Gamificação no ensino", "question": "Q" * 30,
        "language": "pt-BR", "template": "abnt-artigo", "sources": sources, "status": status,
        "stages": {}, "heads": {}, "created_at": "2026-11-25T00:00:00+00:00", "files": []})
    prefix = f"mcp/{UID}/{pid}"
    bucket.blob(prefix + "/sources.json").upload_from_string(json.dumps(manifest))
    bucket.blob(prefix + "/references.json").upload_from_string(json.dumps(refs))
    return pid, manifest, refs


def evidence_json(manifest, count=8, bad=False):
    items = []
    for n in range(count):
        entry = manifest[n % 3]
        quote = SOURCE_TEXT[n % 3][:90] if not bad else "frase inventada que não está em fonte alguma do projeto"
        items.append({"afirmacao": f"Afirmação {n}", "chave": entry["key"], "chunk_id": "x",
                      "citacao_literal": quote})
    return json.dumps(items, ensure_ascii=False)


def latex_body(keys, extra=""):
    paragraphs = " ".join(f"Texto de apoio número {n} sobre o tema, com análise cuidadosa." for n in range(40))
    sections = "".join(f"\\section{{Seção {n}}}\n{paragraphs} Conforme \\cite{{{keys[n % len(keys)]}}}.\n\n"
                       for n in range(4))
    return "\\begin{resumo}\nResumo do artigo.\n\\end{resumo}\n" + sections + extra


# ------------------------------------------------------------------ lógica pura
class FlowLogicTest(unittest.TestCase):
    def test_quote_normalization_tolerates_pdf_breaks(self):
        text = "A gamifi-\ncação aumentou o   engajamento dos estudantes."
        self.assertTrue(flow.quote_in("A gamificação aumentou o engajamento", text))
        self.assertFalse(flow.quote_in("A gamificação reduziu o engajamento", text))

    def test_forbidden_latex_is_refused(self):
        keys = {"k1"}
        for bad in ("\\input{/etc/passwd}", "\\immediate\\write18{ls}", "\\csname input\\endcsname",
                    "\\def\\x{y}", "^^5cinput", "\\usepackage{shellesc}", "\\end{document}"):
            report = flow.validate_latex(latex_body(["k1"], bad), keys, 100, "abnt-artigo")
            self.assertFalse(report["ok"], bad)
        self.assertTrue(flow.validate_latex(latex_body(["k1"]), keys, 100, "abnt-artigo")["ok"])

    def test_unknown_citation_key_is_refused(self):
        report = flow.validate_latex(latex_body(["inventada2020"]), {"k1"}, 100, "abnt-artigo")
        self.assertFalse(report["ok"])
        self.assertIn("inventada2020", " ".join(report["erros"]))

    def test_reference_fix_must_match_the_document(self):
        first = "Eles já nascem sabendo! Desmistificando o conceito de nativos digitais\nMagda Pischetola e Bruna Heinsfeld"
        full = first + "\nRENOTE V. 16 Nº 1, julho, 2018. DOI 10.22456/1679-1916.85929"
        fix = {"autores": ["Pischetola, Magda", "Heinsfeld, Bruna Damiana"],
               "titulo": "Eles já nascem sabendo! Desmistificando o conceito de nativos digitais",
               "ano": "2018", "tipo": "article", "veiculo": "RENOTE", "doi": "10.22456/1679-1916.85929"}
        fields, errors = flow.check_reference_fix(fix, first, full)
        self.assertEqual(errors, [])
        self.assertEqual(fields["journal"], "RENOTE")
        for bad in ({"autores": ["Inventado, Autor"]}, {"titulo": "Um título que não está no documento"},
                    {"ano": "2012"}, {"veiculo": "Revista X"}, {"doi": "10.1234/falso"}, {"titulo": "a}b{c" * 4}):
            _, errors = flow.check_reference_fix({**fix, **bad}, first, full)
            self.assertTrue(errors, bad)

    def test_reviewer_head_rules(self):
        writer = {"id": "cab_w", "kind": "redatora", "model": "Claude Opus 5.5"}
        reviewer = {"id": "cab_r", "kind": "revisora", "stage": "revisao", "model": "Gemini 3 Pro"}
        revisao = flow.stage("revisao")
        self.assertIsNotNone(flow.check_head(revisao, writer, {}))
        self.assertIsNone(flow.check_head(revisao, reviewer, {"redacao": {"head": writer}}))
        self.assertEqual(flow.independence(writer, reviewer)["nivel"], "outra_ia")
        same = {**reviewer, "model": "Claude Sonnet"}
        self.assertEqual(flow.independence(writer, same)["nivel"], "outra_conversa")
        # Revisora não pode escrever.
        self.assertIsNotNone(flow.check_head(flow.stage("redacao"), reviewer, {}))

    def test_tokens_are_hashed(self):
        token, digest = flow.new_token()
        self.assertTrue(flow.looks_like_token(token))
        self.assertEqual(flow.token_hash(token), digest)
        self.assertNotIn(token, digest)


# ------------------------------------------------------------------ servidor
class McpHarness(unittest.TestCase):
    """Servidor MCP em memória com um projeto já preparado (sem testes próprios)."""
    def setUp(self):
        self.db, self.bucket, self.jobs = DB(), Bucket(), []
        self.store = mcp_server.Store(self.db, self.bucket, lambda *a: self.jobs.append(a), lambda i: True)
        self.token = self.store.create_token(UID, "pesquisador@example.org", "Teste")["token"]
        self.pid, self.manifest, self.refs = seed_project(self.db, self.bucket)
        self.keys = [r["key"] for r in self.refs]

    @property
    def app(self):
        # O gerenciador de sessões do SDK roda uma vez por instância: um app por chamada.
        return mcp_server.Dispatcher(api_app=self._api, mcp_app=mcp_server.build_app(
            self.store, "https://scriptorium.example"))

    async def _api(self, scope, receive, send):
        await send({"type": "http.response.start", "status": 418, "headers": []})
        await send({"type": "http.response.body", "body": b"api"})

    def run_calls(self, calls, token=None, path="/api/mcp"):
        app = self.app

        async def go():
            inner = app.mcp_app
            async with inner.router.lifespan_context(inner):
                headers = {"authorization": f"Bearer {token or self.token}"} if path == "/api/mcp" else {}
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),
                                              base_url="http://test", headers=headers) as http:
                    async with streamable_http_client("http://test" + path, http_client=http) as streams:
                        read, write = streams[0], streams[1]
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            out = []
                            for name, args in calls:
                                result = await session.call_tool(name, args)
                                text = result.content[0].text if result.content else ""
                                try:
                                    payload = json.loads(text)
                                except ValueError:
                                    payload = {"_texto": text}
                                out.append((result.is_error, payload))
                            return out
        return asyncio.run(go())



@unittest.skipUnless(HAVE_SDK, "SDK do MCP ausente")
class McpServerTest(McpHarness):
    def test_rejects_without_token(self):
        app = self.app

        async def go():
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),
                                          base_url="http://test") as http:
                return await http.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                       headers={"accept": "application/json, text/event-stream"})
        inner = app.mcp_app

        async def wrapped():
            async with inner.router.lifespan_context(inner):
                return await go()
        self.assertEqual(asyncio.run(wrapped()).status_code, 401)

    def test_other_paths_go_to_api(self):
        async def go():
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=self.app),
                                          base_url="http://test") as http:
                return await http.get("/api/research")
        self.assertEqual(asyncio.run(go()).status_code, 418)

    def test_token_in_path_works_and_lists_sources(self):
        self.db.collection("library_items").document("b" * 32).set(
            {"id": "b" * 32, "owner_uid": UID, "status": "active", "format": "pdf", "name": "x.pdf"})
        [(err, payload)] = self.run_calls([("listar_fontes", {})], path=f"/api/mcp/t/{self.token}")
        self.assertFalse(err, payload)
        self.assertEqual(payload["fontes"][0]["id"], "b" * 32)

    def test_revoked_token_stops_working(self):
        token_id = self.store.list_tokens(UID)[0]["id"]
        self.assertTrue(self.store.revoke_token(UID, token_id))
        with self.assertRaises(Exception):
            self.run_calls([("listar_fontes", {})])

    def test_full_flow_with_independent_heads(self):
        pid = self.pid
        [(e1, step)] = self.run_calls([("proxima_etapa", {"projeto": pid, "modelo_declarado": "Claude Opus 5.5"})])
        self.assertFalse(e1, step)
        self.assertEqual(step["etapa"], "planejamento")
        writer = step["cabeca"]
        plan = "# Plano\n" + ("Seção usa " + " e ".join(self.keys) + ". ") * 20
        search_and_read = self.run_calls([
            ("buscar_trechos", {"projeto": pid, "consulta": "engajamento gamificação"}),
            ("entregar_etapa", {"projeto": pid, "etapa": "planejamento", "conteudo": plan, "cabeca": writer}),
        ])
        hits = search_and_read[0][1]["resultados"]
        self.assertTrue(hits and hits[0]["chave"] in self.keys)
        self.assertTrue(search_and_read[1][1]["aceita"], search_and_read[1][1])
        chunk = self.run_calls([("ler_trecho", {"projeto": pid, "chunk_id": hits[0]["chunk_id"]})])[0][1]
        self.assertIn("Trecho", chunk["texto"])
        # Evidência inventada volta com erro; a correta passa.
        bad, good = self.run_calls([
            ("entregar_etapa", {"projeto": pid, "etapa": "evidencias", "cabeca": writer,
                                "conteudo": evidence_json(self.manifest, bad=True)}),
            ("entregar_etapa", {"projeto": pid, "etapa": "evidencias", "cabeca": writer,
                                "conteudo": evidence_json(self.manifest)}),
        ])
        self.assertFalse(bad[1]["aceita"])
        self.assertTrue(good[1]["aceita"], good[1])
        draft = self.run_calls([("entregar_etapa", {"projeto": pid, "etapa": "redacao", "cabeca": writer,
                                                     "conteudo": latex_body(self.keys)})])[0][1]
        self.assertTrue(draft["aceita"], draft)
        # Revisão exige conversa nova: a cabeça redatora recebe só o passe.
        handoff = self.run_calls([("proxima_etapa", {"projeto": pid, "cabeca": writer})])[0][1]
        self.assertTrue(handoff["precisa_de_conversa_nova"])
        self.assertNotIn("material", handoff)
        refused = self.run_calls([("entregar_etapa", {"projeto": pid, "etapa": "revisao", "cabeca": writer,
                                                       "conteudo": "{}"})])[0]
        self.assertTrue(refused[0])
        opened = self.run_calls([("abrir_passe", {"codigo": handoff["passe"], "modelo_declarado": "Gemini 3 Pro"})])[0][1]
        reviewer = opened["cabeca"]
        self.assertIn("rascunho", opened["material"])
        review = json.dumps({"nota_geral": 6, "resumo": "ok", "problemas": [
            {"trecho": "Texto", "tipo": "lacuna", "gravidade": "media", "sugestao": "Ampliar"}] * 3}, ensure_ascii=False)
        review = review + " " * 300
        accepted = self.run_calls([("entregar_etapa", {"projeto": pid, "etapa": "revisao", "cabeca": reviewer,
                                                        "conteudo": review})])[0][1]
        self.assertTrue(accepted["aceita"], accepted)
        self.assertEqual(accepted["independencia"]["nivel"], "outra_ia")
        rewrite = self.run_calls([("entregar_etapa", {"projeto": pid, "etapa": "reescrita", "cabeca": writer,
                                                       "conteudo": latex_body(self.keys, "% revisado")})])[0][1]
        self.assertTrue(rewrite["aceita"], rewrite)
        handoff2 = self.run_calls([("proxima_etapa", {"projeto": pid, "cabeca": writer})])[0][1]
        verifier = self.run_calls([("abrir_passe", {"codigo": handoff2["passe"],
                                                    "modelo_declarado": "GPT-5"})])[0][1]["cabeca"]
        # A revisora não pode verificar (já entregou outra etapa).
        checks = [{"afirmacao": f"A{n}", "chave": self.manifest[n % 3]["key"], "veredito": "sustentada",
                   "chunk_id": "x", "citacao_literal": SOURCE_TEXT[n % 3][:80]} for n in range(10)]
        wrong = self.run_calls([("entregar_etapa", {"projeto": pid, "etapa": "verificacao", "cabeca": reviewer,
                                                     "conteudo": json.dumps(checks)})])[0]
        self.assertTrue(wrong[0])
        done = self.run_calls([("entregar_etapa", {"projeto": pid, "etapa": "verificacao", "cabeca": verifier,
                                                    "conteudo": json.dumps(checks, ensure_ascii=False)})])[0][1]
        self.assertTrue(done["aceita"], done)
        compiled = self.run_calls([("compilar", {"projeto": pid})])[0][1]
        self.assertEqual(compiled["status"], "compilando")
        self.assertEqual(self.jobs[-1][2], "mcp_compile")
        state = self.run_calls([("estado_do_projeto", {"projeto": pid})])[0][1]
        self.assertEqual([s["status"] for s in state["etapas"]], ["aceita"] * 6)

    def test_reference_fix_tool_keeps_key_and_rewrites_bib(self):
        [(e1, step)] = self.run_calls([("proxima_etapa", {"projeto": self.pid, "modelo_declarado": "Claude"})])
        key = self.keys[0]
        path = self.manifest[0]["derived"]
        payload = json.loads(self.bucket.objects[path])
        payload["chunks"][-1]["text"] += " Publicado em 2024."
        self.bucket.objects[path] = json.dumps(payload).encode()
        ok, bad = self.run_calls([
            ("corrigir_referencia", {"projeto": self.pid, "chave": key, "cabeca": step["cabeca"],
                                     "autores": ["Gamificação, X"], "titulo": "A gamificação aumentou o engajamento",
                                     "ano": "2024", "tipo": "article"}),
            ("corrigir_referencia", {"projeto": self.pid, "chave": key, "cabeca": step["cabeca"],
                                     "autores": ["Silva, Ana"], "titulo": "Título inventado pela IA",
                                     "ano": "2024", "tipo": "article"}),
        ])
        self.assertFalse(ok[0], ok[1])
        self.assertTrue(bad[0])
        bib = self.bucket.objects[f"mcp/{UID}/{self.pid}/references.bib"].decode()
        self.assertIn("@article{" + key, bib)
        self.assertIn("A gamificação aumentou o engajamento", bib)
        project = self.db.collection("mcp_projects").document(self.pid).get().to_dict()
        self.assertEqual(project["reference_fixes"][0]["chave"], key)

    def test_other_users_project_is_invisible(self):
        other = self.store.create_token("o" * 28, "outra@example.org", "Outra")["token"]
        [(err, payload)] = self.run_calls([("estado_do_projeto", {"projeto": self.pid})], token=other)
        self.assertTrue(err)
        self.assertIn("não encontrado", payload["_texto"])


try:
    import fastapi  # noqa: F401
    import mcp_site_api  # noqa: E402
    HAVE_FASTAPI = HAVE_SDK
except ImportError:
    HAVE_FASTAPI = False


@unittest.skipUnless(HAVE_FASTAPI, "FastAPI ausente")
class SiteRoutesTest(unittest.TestCase):
    def setUp(self):
        self.db, self.bucket = DB(), Bucket()
        self.store = mcp_server.Store(self.db, self.bucket, lambda *a: None, lambda i: True)
        self.router = mcp_site_api.make_mcp_site_router(self.store, lambda: None, "https://s.example")
        self.user = {"uid": UID, "email": "p@example.org"}

    def route(self, suffix, method):
        return next(r.endpoint for r in self.router.routes if r.path.endswith(suffix) and method in r.methods)

    def test_token_shown_once_and_revocable(self):
        created = self.route("/tokens", "POST")(mcp_site_api.NewToken(label="Claude"), self.user)
        self.assertTrue(created["endereco_com_token"].endswith(created["token"]))
        listed = self.route("/tokens", "GET")(self.user)["tokens"]
        self.assertNotIn("token", listed[0])
        self.assertNotIn("hash", listed[0])
        self.route("/tokens/{token_id}", "DELETE")(created["id"], self.user)
        self.assertIsNone(self.store.token_owner(created["token"]))

    def test_download_only_known_files_of_own_project(self):
        pid, _, _ = seed_project(self.db, self.bucket)
        self.bucket.blob(f"mcp/{UID}/{pid}/final/scriptorium.pdf").upload_from_string(b"%PDF")
        download = self.route("/arquivos/{name}", "GET")
        self.assertEqual(download(pid, "scriptorium.pdf", self.user).body, b"%PDF")
        with self.assertRaises(fastapi.HTTPException):
            download(pid, "../../segredo", self.user)
        with self.assertRaises(fastapi.HTTPException):
            download(pid, "scriptorium.pdf", {"uid": "o" * 28})


if __name__ == "__main__":
    unittest.main()
