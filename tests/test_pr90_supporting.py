import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.app.main import create_app
from backend.legacy.services.ai_service import OFFLINE_FALLBACK_MESSAGE


def make_text_pdf(text: str = "Hello EasyExam") -> bytes:
    """Build a tiny, well-formed PDF containing extractable text (no external deps)."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode("utf-8")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    return bytes(out)


class VariantProvider:
    def __init__(self, output: str):
        self.output = output

    def chat_complete(self, messages):
        return self.output


def valid_variant_payload() -> str:
    return json.dumps({
        "stem": "已知直角三角形两直角边长为6和8，求斜边长？",
        "type": "MULTIPLE",
        "options": [{"key": "A", "text": "10"}, {"key": "B", "text": "12"}],
        "answer": "A",
        "explanation": "勾股定理 6^2 + 8^2 = 10^2",
        "difficulty": 3,
        "tags": ["数学", "几何"],
    }, ensure_ascii=False)


def valid_single_variant_payload() -> str:
    return json.dumps({
        "stem": "已知直角三角形两直角边长为6和8，求斜边长？",
        "type": "SINGLE",
        "options": [{"key": "A", "text": "10"}, {"key": "B", "text": "12"}],
        "answer": "A",
        "explanation": "勾股定理 6^2 + 8^2 = 10^2",
        "difficulty": 3,
        "tags": ["数学", "几何"],
    }, ensure_ascii=False)


class Pr90SupportingRegressionTest(unittest.TestCase):
    def setUp(self):
        self._orig_secret = os.environ.get("EASYEXAM_SECRET_KEY")
        os.environ["EASYEXAM_SECRET_KEY"] = "easyexam-ci-secret-32bytes-passphrase!!"
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "easyexam-v1.db")
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.state.services.ai.provider = None
        if self._orig_secret is not None:
            os.environ["EASYEXAM_SECRET_KEY"] = self._orig_secret
        else:
            os.environ.pop("EASYEXAM_SECRET_KEY", None)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # --- AI variant contract / draft isolation / permissions -------------

    def register(self, username: str) -> dict:
        password = "password-123456"
        self.client.post("/api/v1/auth/register", json={"username": username, "password": password})
        token = self.client.post("/api/v1/auth/login", json={"username": username, "password": password}).json()["token"]
        return {"Authorization": f"Bearer {token}"}

    def make_bank_question(self, headers: dict, name: str = "变式题库"):
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": name}).json()
        question = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={
            "stem": "已知直角三角形两直角边长为3和4，求斜边长？",
            "type": "SINGLE",
            "options": [{"key": "A", "text": "5"}, {"key": "B", "text": "6"}],
            "answer": "A",
            "explanation": "勾股定理 3^2 + 4^2 = 5^2",
        }).json()
        return bank, question

    def test_practice_payload_is_normalized_by_real_variant_contract(self):
        headers = self.register("variant_owner")
        bank, question = self.make_bank_question(headers)
        self.app.state.services.ai.provider = VariantProvider(valid_variant_payload())

        # Legacy practice-view payload ({question_id, prompt}) used to produce HTTP 422.
        response = self.client.post("/api/v1/ai/variants", headers=headers, json={
            "question_id": question["id"],
            "prompt": "改成边长为6和8",
        })
        self.assertEqual(response.status_code, 201, response.text)
        draft = response.json()
        self.assertEqual(draft["original_question_id"], question["id"])
        self.assertEqual(draft["target_bank_id"], bank["id"])
        self.assertEqual(draft["type"], "MULTI")

        listed = self.client.get("/api/v1/ai/drafts", headers=headers).json()
        entry = next(item for item in listed if item["id"] == draft["id"])
        self.assertEqual(entry["target_bank_name"], "变式题库")
        self.assertTrue(entry["can_manage"])

        filtered = self.client.get(f"/api/v1/ai/drafts?bank_id={bank['id']}", headers=headers).json()
        self.assertTrue(any(item["id"] == draft["id"] for item in filtered))
        other_bank_id = self.client.post("/api/v1/banks", headers=headers, json={"name": "其他题库"}).json()["id"]
        self.assertEqual(self.client.get(f"/api/v1/ai/drafts?bank_id={other_bank_id}", headers=headers).json(), [])

    def test_variant_target_bank_requires_edit_permission(self):
        owner = self.register("variant_admin")
        member = self.register("variant_member")
        bank, question = self.make_bank_question(owner)
        added = self.client.post(f"/api/v1/banks/{bank['id']}/members", headers=owner, json={
            "username": "variant_member",
            "role": "MEMBER",
        })
        self.assertEqual(added.status_code, 201, added.text)
        self.app.state.services.ai.provider = VariantProvider(valid_variant_payload())

        forbidden = self.client.post("/api/v1/ai/variants", headers=member, json={
            "original_question_id": question["id"],
            "target_bank_id": bank["id"],
        })
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

        self.assertTrue(self.client.get("/api/v1/ai/drafts", headers=member).json() == [])
        member_cannot_add = self.client.post(f"/api/v1/banks/{bank['id']}/members", headers=member, json={
            "username": "variant_admin",
            "role": "EDITOR",
        })
        self.assertEqual(member_cannot_add.status_code, 403)

    def test_variant_accept_requires_permission_and_is_user_scoped(self):
        owner = self.register("variant_accept_owner")
        other = self.register("variant_accept_other")
        bank, question = self.make_bank_question(owner)
        self.app.state.services.ai.provider = VariantProvider(valid_single_variant_payload())
        draft = self.client.post("/api/v1/ai/variants", headers=owner, json={
            "original_question_id": question["id"],
            "target_bank_id": bank["id"],
        }).json()

        self.assertEqual(self.client.get(f"/api/v1/ai/drafts/{draft['id']}", headers=other).status_code, 404)
        self.assertEqual(self.client.post(f"/api/v1/ai/drafts/{draft['id']}/accept", headers=other, json={}).status_code, 404)

        accepted = self.client.post(f"/api/v1/ai/drafts/{draft['id']}/accept", headers=owner, json={})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["status"], "ACCEPTED")

    def test_variant_reports_unconfigured_ai_with_localized_code(self):
        headers = self.register("variant_offline")
        _, question = self.make_bank_question(headers)
        self.app.state.services.ai.provider = VariantProvider(OFFLINE_FALLBACK_MESSAGE)

        response = self.client.post(
            "/api/v1/ai/variants",
            headers={**headers, "Accept-Language": "en-US"},
            json={"original_question_id": question["id"]},
        )
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["error_code"], "AI_NOT_CONFIGURED")

    def test_variant_reports_unusable_model_output(self):
        headers = self.register("variant_badjson")
        _, question = self.make_bank_question(headers)
        self.app.state.services.ai.provider = VariantProvider("这不是 JSON")

        response = self.client.post(
            "/api/v1/ai/variants",
            headers={**headers, "Accept-Language": "en-US"},
            json={"original_question_id": question["id"]},
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error_code"], "AI_GENERATION_FAILED")

    def test_variant_reports_provider_failure(self):
        from unittest.mock import patch

        headers = self.register("variant_provider_failure")
        _, question = self.make_bank_question(headers)
        with patch.object(self.app.state.services.ai, "_get_provider_for_user") as provider:
            provider.return_value.chat_complete.side_effect = RuntimeError("unavailable")
            response = self.client.post(
                "/api/v1/ai/variants",
                headers={**headers, "Accept-Language": "en-US"},
                json={"original_question_id": question["id"]},
            )
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(response.json()["error_code"], "AI_GENERATION_FAILED")

    # --- Notes / assets ---------------------------------------------------

    def test_note_can_be_edited_saved_and_deleted(self):
        headers = self.register("note_editor")
        created = self.client.post("/api/v1/assets", headers=headers, json={
            "asset_type": "NOTE",
            "content": "初始笔记",
        }).json()

        updated = self.client.put(f"/api/v1/assets/{created['id']}", headers=headers, json={
            "content": "更新后的笔记",
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["content"], "更新后的笔记")

        fetched = self.client.get(f"/api/v1/assets/{created['id']}", headers=headers)
        self.assertEqual(fetched.json()["content"], "更新后的笔记")

        empty = self.client.put(f"/api/v1/assets/{created['id']}", headers=headers, json={"content": "   "})
        self.assertEqual(empty.status_code, 422)

        self.assertEqual(self.client.delete(f"/api/v1/assets/{created['id']}", headers=headers).status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/assets/{created['id']}", headers=headers).status_code, 404)

    def test_pdf_upload_is_stored_and_previewable_and_downloadable(self):
        headers = self.register("pdf_owner")
        other = self.register("pdf_other")
        pdf_bytes = make_text_pdf("Hello EasyExam PDF")
        self.assertEqual(PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text().strip(), "Hello EasyExam PDF")

        uploaded = self.client.post(
            "/api/v1/assets/upload",
            headers=headers,
            data={"asset_type": "NOTE"},
            files={"file": ("复习资料.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        asset = uploaded.json()
        self.assertEqual(asset["file_name"], "复习资料.pdf")
        self.assertEqual(asset["mime_type"], "application/pdf")
        self.assertIn("Hello EasyExam PDF", asset["content"])

        preview = self.client.get(f"/api/v1/assets/{asset['id']}/file", headers=headers)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "application/pdf")
        self.assertTrue(preview.headers["content-disposition"].startswith("inline"))
        self.assertEqual(preview.content, pdf_bytes)

        download = self.client.get(f"/api/v1/assets/{asset['id']}/file?download=1", headers=headers)
        self.assertTrue(download.headers["content-disposition"].startswith("attachment"))

        self.assertEqual(self.client.get(f"/api/v1/assets/{asset['id']}/file", headers=other).status_code, 404)

        stored_dir = Path(self.db_path).parent / "asset_files"
        self.assertEqual(len(list(stored_dir.glob("*.pdf"))), 1)
        self.assertEqual(self.client.delete(f"/api/v1/assets/{asset['id']}", headers=headers).status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/assets/{asset['id']}/file", headers=headers).status_code, 404)
        self.assertEqual(len(list(stored_dir.glob("*.pdf"))), 0)

    def test_text_upload_keeps_unicode_filename_for_download(self):
        headers = self.register("note_uploader")
        uploaded = self.client.post(
            "/api/v1/assets/upload",
            headers=headers,
            data={"asset_type": "SUMMARY"},
            files={"file": ("错题总结.md", b"# Summary\nKey point", "text/markdown")},
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        asset = uploaded.json()
        self.assertEqual(asset["file_name"], "错题总结.md")
        self.assertEqual(asset["mime_type"], "text/markdown")

        file_response = self.client.get(f"/api/v1/assets/{asset['id']}/file", headers=headers)
        self.assertEqual(file_response.status_code, 200)
        self.assertEqual(file_response.content, b"# Summary\nKey point")


if __name__ == "__main__":
    unittest.main()
