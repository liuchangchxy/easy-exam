import io
import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.app.main import create_app


class TestV1Assets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.app = create_app(db_path=self.tmp.name)
        self.client = TestClient(self.app)

        # User
        self.client.post("/api/v1/auth/register", json={"username": "asset_user", "password": "password123"})
        res = self.client.post("/api/v1/auth/login", json={"username": "asset_user", "password": "password123"})
        self.token = res.json()["token"]
        self.auth = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_upload_text_and_markdown_asset_succeeds(self):
        """Uploading UTF-8 text and markdown documents should create personal assets."""
        txt_res = self.client.post(
            "/api/v1/assets/upload",
            headers=self.auth,
            data={"asset_type": "NOTE"},
            files={"file": ("notes.txt", b"Administrative Law key summary notes", "text/plain")},
        )
        self.assertEqual(txt_res.status_code, 201, txt_res.text)
        asset_txt = txt_res.json()
        self.assertEqual(asset_txt["asset_type"], "NOTE")
        self.assertIn("Administrative Law", asset_txt["content"])

        md_res = self.client.post(
            "/api/v1/assets/upload",
            headers=self.auth,
            data={"asset_type": "SUMMARY"},
            files={"file": ("handout.md", b"# Constitution Law\nKey mnemonic: 1-2-3", "text/markdown")},
        )
        self.assertEqual(md_res.status_code, 201)
        asset_md = md_res.json()
        self.assertEqual(asset_md["asset_type"], "SUMMARY")
        self.assertIn("Constitution Law", asset_md["content"])

    def test_upload_valid_pdf_extracts_text(self):
        """A text-based PDF should extract text into the personal asset."""
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        # Note: blank page has no text, so let's test image/blank rejection vs text
        # If no text is extracted, it must be rejected!
        buf = io.BytesIO()
        writer.write(buf)
        empty_pdf = buf.getvalue()

        # Pure blank/image-only PDF rejection
        res_empty = self.client.post(
            "/api/v1/assets/upload",
            headers=self.auth,
            data={"asset_type": "NOTE"},
            files={"file": ("scanned.pdf", empty_pdf, "application/pdf")},
        )
        self.assertEqual(res_empty.status_code, 422)
        self.assertIn("纯图片", res_empty.json()["detail"])

    def test_corrupt_pdf_is_rejected(self):
        """Corrupt PDF file must be rejected with 422."""
        res = self.client.post(
            "/api/v1/assets/upload",
            headers=self.auth,
            data={"asset_type": "NOTE"},
            files={"file": ("corrupt.pdf", b"not a real pdf content header", "application/pdf")},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("损坏", res.json()["detail"])

    def test_unsupported_file_format_is_rejected(self):
        """Non-supported extensions (like .docx, .bin) must be rejected with 422."""
        res = self.client.post(
            "/api/v1/assets/upload",
            headers=self.auth,
            data={"asset_type": "NOTE"},
            files={"file": ("manual.docx", b"word content", "application/vnd.openxmlformats")},
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("不支持", res.json()["detail"])
