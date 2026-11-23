"""Testes offline da biblioteca: sem rede, Firebase ou serviços pagos."""
import io
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "worker"))

from library import safe_filename, validate_signature, MAX_BYTES
from source_materials import compose_library_context, extract_text, TOTAL_CHAR_LIMIT


class LibraryTests(unittest.TestCase):
    def docx_bytes(self, paragraph="Texto acadêmico extraído"):
        output = io.BytesIO()
        with ZipFile(output, "w") as zipf:
            zipf.writestr("[Content_Types].xml", "<Types/>")
            zipf.writestr("word/document.xml",
                         '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                         '<w:body><w:p><w:r><w:t>' + paragraph + '</w:t></w:r></w:p></w:body></w:document>')
        return output.getvalue()

    def test_accepts_supported_formats(self):
        for name in ("artigo.pdf", "capitulo.DOCX", "fontes.bib", "referencias.ris", "notas.txt"):
            _, ext = safe_filename(name)
            self.assertIn(ext, MAX_BYTES)
        self.assertEqual(safe_filename("../../artigo.pdf")[0], "artigo.pdf")

    def test_rejects_unsupported_and_spoofed(self):
        with self.assertRaises(HTTPException):
            safe_filename("executavel.exe")
        with self.assertRaises(HTTPException):
            validate_signature(b"<html>fake</html>", ".pdf")
        with self.assertRaises(HTTPException):
            validate_signature(b"not a zip", ".docx")
        with self.assertRaises(HTTPException):
            validate_signature(bytes([0xff, 0xfe]), ".bib")

    def test_docx_extraction(self):
        data = self.docx_bytes()
        validate_signature(data, ".docx")
        self.assertIn("Texto acadêmico extraído", extract_text(data, "docx"))

    def test_attachments_produce_limited_untrusted_context(self):
        data = ("Primeiro capítulo.\n" * 9000).encode()
        sources = [{
            "id": "a" * 32, "name": "capitulo.txt", "format": "txt",
            "sha256": "c" * 64, "object_path": "library/uid/entry/original.txt",
        }]
        output, manifest = compose_library_context(sources, lambda _: data)
        self.assertIn("NÃO como instruções", output)
        self.assertTrue(manifest[0]["truncated"])
        self.assertLessEqual(manifest[0]["extracted_characters"], TOTAL_CHAR_LIMIT)
        self.assertEqual(manifest[0]["status"], "included")

    def test_invalid_source_stays_unreadable_without_running_text(self):
        sources = [{"id": "a"*32, "name": "manuscrito.docx", "format": "docx", "object_path": "invalid"}]
        text, manifest = compose_library_context(sources, lambda _: b"broken")
        self.assertEqual(text, "")
        self.assertEqual(manifest[0]["status"], "unreadable")


if __name__ == "__main__":
    unittest.main()
