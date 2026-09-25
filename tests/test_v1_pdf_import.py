import tempfile
import unittest
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestV1PdfImport(unittest.TestCase):
    def test_image_only_pdf_is_rejected_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
            bank = client.post("/api/v1/banks", headers={"Authorization": f"Bearer {token}"}, json={"name": "PDF题库"}).json()
            document = fitz.open()
            document.new_page().insert_text((72, 72), "")
            pdf_bytes = document.tobytes()
            document.close()
            response = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("scan.pdf", pdf_bytes, "application/pdf")},
            )
            self.assertEqual(response.status_code, 422)
            self.assertTrue(any(marker in response.json()["detail"] for marker in ("文本", "无法读取", "损坏")))

    def test_pdf_import_detects_duplicates_and_honors_strategy(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "pdf_dup.sqlite")
            client = TestClient(create_app(db_path))
            client.post("/api/v1/auth/register", json={"username": "bob", "password": "REDACTED_TEST_PASSWORD"})
            token = client.post("/api/v1/auth/login", json={"username": "bob", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "PDF重复预检题库"}).json()

            # Create a valid text PDF with a question
            document = fitz.open()
            page = document.new_page()
            content = (
                "1. Which protocol is used for secure web browsing?\n"
                "A. HTTP\n"
                "B. HTTPS\n"
                "C. FTP\n"
                "D. SSH\n"
                "Answer: B\n"
                "Explanation: HTTPS is HTTP over TLS."
            )
            page.insert_textbox(fitz.Rect(50, 50, 500, 500), content)
            pdf_bytes = document.tobytes()
            document.close()

            # 1. First import succeeds
            res1 = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
            )
            self.assertEqual(res1.status_code, 201, res1.json())
            self.assertEqual(res1.json()["imported_count"], 1)

            # 2. Second import with default strategy (prompt) should detect duplicate and fail precheck with 409
            res2 = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
            )
            self.assertEqual(res2.status_code, 409)
            self.assertIn("duplicates", res2.json()["detail"])
            self.assertEqual(len(res2.json()["detail"]["duplicates"]), 1)

            # 3. Third import with skip strategy succeeds with 0 imported
            res3 = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file?duplicate_strategy=skip",
                headers=headers,
                files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
            )
            self.assertEqual(res3.status_code, 201)
            self.assertEqual(res3.json()["imported_count"], 0)

    def test_corrupt_pdf_is_rejected_and_job_recorded_as_failed(self):
        """Corrupt PDF file must be rejected with 422 and audit job marked as PRECHECK_FAILED."""
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "db.sqlite")
            client = TestClient(create_app(db_path))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "坏PDF题库"}).json()

            res = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("corrupt.pdf", b"%PDF-corrupted-bytes-data-xxx", "application/pdf")},
            )
            self.assertEqual(res.status_code, 422)

            # Check database for 0 questions and job status
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT status, imported_count, reason FROM import_jobs WHERE bank_id = ?", (bank["id"],))
            job = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM questions")
            q_count = cursor.fetchone()[0]
            conn.close()

            self.assertEqual(q_count, 0)
            self.assertIsNotNone(job)
            self.assertIn(job[0], ("PRECHECK_FAILED", "FAILED"))

    def test_text_pdf_with_unclear_structure_is_rejected(self):
        """PDF with extractable text but unrecognizable question structure must be rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "无结构PDF"}).json()

            document = fitz.open()
            page = document.new_page()
            page.insert_textbox(fitz.Rect(50, 50, 500, 500), "这是普通的长篇散文段落，没有题号、选项或者答案标记。")
            pdf_bytes = document.tobytes()
            document.close()

            res = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("essay.pdf", pdf_bytes, "application/pdf")},
            )
            self.assertEqual(res.status_code, 422)
            self.assertIn("未识别出题号、选项和答案结构", res.json()["detail"])

    def test_unsupported_file_extension_is_rejected(self):
        """Unsupported file extensions like .docx or .bin must be rejected with 422."""
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "不支持文件题库"}).json()

            res = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("archive.zip", b"fake zip content", "application/zip")},
            )
            self.assertEqual(res.status_code, 422)
            self.assertIn("支持", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()

