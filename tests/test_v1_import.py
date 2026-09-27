import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestV1Import(unittest.TestCase):
    def test_xlsx_upload_is_parsed_into_versioned_questions(self):
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "表格题库"}).json()
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["题干", "答案", "题型", "解析"])
            sheet.append(["Excel 题", "A", "SINGLE", "表格解析"])
            buffer = BytesIO()
            workbook.save(buffer)
            response = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("questions.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["imported_count"], 1)

    def test_duplicate_import_requires_explicit_strategy_then_can_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "重复预检"}).json()
            payload = {"format": "text", "content": "1. 1+1=?\nA. 1\nB. 2\n【答案】B"}
            first = client.post(f"/api/v1/imports/banks/{bank['id']}", headers=headers, json=payload)
            self.assertEqual(first.status_code, 201)
            preview = client.post(f"/api/v1/imports/banks/{bank['id']}/preview", headers=headers, json=payload)
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()["accepted"], False)
            self.assertEqual(len(preview.json()["duplicates"]), 1)
            blocked = client.post(f"/api/v1/imports/banks/{bank['id']}", headers=headers, json=payload)
            self.assertEqual(blocked.status_code, 409)
            skipped = client.post(
                f"/api/v1/imports/banks/{bank['id']}",
                headers=headers,
                json={**payload, "duplicate_strategy": "skip"},
            )
            self.assertEqual(skipped.status_code, 201)
            self.assertEqual(skipped.json()["imported_count"], 0)

    def test_text_import_creates_versioned_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "导入题库"}).json()
            response = client.post(
                f"/api/v1/imports/banks/{bank['id']}", headers=headers,
                json={"format": "text", "content": "1. 1+1=?\nA. 1\nB. 2\n【答案】B"},
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["imported_count"], 1)
            self.assertTrue(response.json()["job_id"])
            self.assertEqual(client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()[0]["answer"], "B")


    def test_exameow_column_mapping_aliases_and_preview(self):
        """Test Exameow-adapted column alias detection, options splitting, difficulty normalization, and preview endpoint."""
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "映射题库"}).json()

            # Create an XLSX with Exameow-style headers: 题目, 正确答案, 难度, 选项A, 选项B, 答案解析, 章节
            wb = Workbook()
            ws = wb.active
            ws.append(["题目", "选项A", "选项B", "正确答案", "答案解析", "难度", "章节"])
            ws.append(["光速是多少？", "30万公里/秒", "100万公里/秒", "A", "真空光速约为30万千米每秒", "简单", "物理篇"])
            buf = BytesIO()
            wb.save(buf)
            xlsx_bytes = buf.getvalue()

            # 1. Call preview endpoint for spreadsheet
            preview_res = client.post(
                f"/api/v1/imports/banks/{bank['id']}/preview-file",
                headers=headers,
                files={"file": ("physics.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            self.assertEqual(preview_res.status_code, 200, preview_res.text)
            preview_data = preview_res.json()
            self.assertTrue(preview_data["accepted"])
            self.assertEqual(preview_data["headers"], ["题目", "选项A", "选项B", "正确答案", "答案解析", "难度", "章节"])
            mapping = preview_data["mapping"]
            self.assertEqual(mapping["stem"], 0)
            self.assertEqual(mapping["options"], [1, 2])
            self.assertEqual(mapping["answer"], 3)
            self.assertEqual(mapping["explanation"], 4)
            self.assertEqual(mapping["difficulty"], 5)
            self.assertEqual(mapping["tags"], 6)

            # 2. Upload with auto-detected mapping
            import_res = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("physics.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            self.assertEqual(import_res.status_code, 201)
            self.assertEqual(import_res.json()["imported_count"], 1)

            qs = client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
            self.assertEqual(len(qs), 1)
            self.assertEqual(qs[0]["stem"], "光速是多少？")
            self.assertEqual(qs[0]["answer"], "A")
            self.assertEqual(qs[0]["difficulty"], 1)  # "简单" -> 1
            self.assertEqual(qs[0]["options"][0]["content"], "30万公里/秒")

    def test_combined_options_delimiter_and_manual_mapping(self):
        """Test Exameow-style combined options splitting and manual user column mapping correction."""
        import json
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "组合选项题库"}).json()

            # CSV with combined options delimited by semicolon and non-standard column order
            csv_content = (
                "ColX,ColY,ColZ,ColW\n"
                "A,这是题干内容,A. 苹果; B. 香蕉; C. 橘子,这是详细解析\n"
            )

            # Preview should identify columns but mark missing stem/answer without mapping
            prev = client.post(
                f"/api/v1/imports/banks/{bank['id']}/preview-file",
                headers=headers,
                files={"file": ("test.csv", csv_content.encode("utf-8"), "text/csv")},
            )
            self.assertEqual(prev.status_code, 200)
            self.assertFalse(prev.json()["accepted"])
            self.assertIn("stem", prev.json()["missing"])

            # User corrects the column mapping manually: ColX -> answer, ColY -> stem, ColZ -> combined_options, ColW -> explanation
            custom_mapping = {
                "stem": 1,
                "answer": 0,
                "combined_options": 2,
                "options_delimiter": ";",
                "explanation": 3,
                "type": None,
                "difficulty": None,
                "tags": None,
                "options": [],
            }

            import_res = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("test.csv", csv_content.encode("utf-8"), "text/csv")},
                data={"column_mapping": json.dumps(custom_mapping)},
            )
            self.assertEqual(import_res.status_code, 201, import_res.text)
            self.assertEqual(import_res.json()["imported_count"], 1)

            qs = client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
            self.assertEqual(len(qs), 1)
            self.assertEqual(qs[0]["stem"], "这是题干内容")
            self.assertEqual(qs[0]["answer"], "A")
            self.assertEqual(len(qs[0]["options"]), 3)
            self.assertEqual(qs[0]["options"][0]["content"], "苹果")

    def test_batch_import_atomic_rollback_on_failure(self):
        """Test EXAM-MASTER pattern: when question 2 fails during real SQLite write, question 1 must be rolled back with 0 leftover records."""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "db.sqlite")
            client = TestClient(create_app(db_path))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "原子回滚测试"}).json()

            # Create a real SQLite trigger that physically aborts the transaction ONLY when inserting the 2nd question
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TRIGGER fail_mid_batch_on_second_question
                BEFORE INSERT ON question_versions
                WHEN NEW.stem LIKE '%第二题触发异常%'
                BEGIN
                    SELECT RAISE(ABORT, 'Physical SQLite constraint abort on second question');
                END;
            """)
            conn.commit()
            conn.close()

            # Batch of 2 questions: question 1 is completely valid, question 2 triggers the real SQLite ABORT
            payload = {
                "format": "text",
                "content": (
                    "1. 第一题通过？\nA. 对\nB. 错\n【答案】A\n\n"
                    "2. 第二题触发异常？\nA. 是\nB. 否\n【答案】B\n"
                ),
            }

            response = client.post(f"/api/v1/imports/banks/{bank['id']}", headers=headers, json=payload)
            self.assertEqual(response.status_code, 422)

            # Physically query database to verify that ZERO questions, ZERO versions, and ZERO bank items exist
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM questions")
            q_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM question_versions")
            qv_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM bank_question_items")
            bqi_count = cursor.fetchone()[0]

            # Verify import job is recorded as FAILED
            cursor.execute("SELECT status, imported_count, reason FROM import_jobs WHERE bank_id = ?", (bank["id"],))
            job = cursor.fetchone()
            conn.close()

            self.assertEqual(q_count, 0, "Question 1 must be rolled back by SQLite transaction")
            self.assertEqual(qv_count, 0, "Question version 1 must be rolled back by SQLite transaction")
            self.assertEqual(bqi_count, 0, "Bank item 1 must be rolled back by SQLite transaction")

            self.assertIsNotNone(job)
            self.assertEqual(job[0], "FAILED")
            self.assertEqual(job[1], 0)
            self.assertIn("Physical SQLite constraint abort", job[2])

    def test_empty_spreadsheet_preview_is_rejected(self):
        """Preview of a spreadsheet with valid headers but 0 data rows must be rejected with accepted=False."""
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "空表题库"}).json()

            empty_csv = "question,answer\n"
            res = client.post(
                f"/api/v1/imports/banks/{bank['id']}/preview-file",
                headers=headers,
                files={"file": ("empty.csv", empty_csv.encode("utf-8"), "text/csv")},
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertFalse(data["accepted"])
            self.assertEqual(data["question_count"], 0)
            self.assertIn("未识别到有效题目", data["reason"])

    def test_duplicate_strategy_new_and_merge(self):
        """Test duplicate strategies 'new' and 'merge'."""
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "策略题库"}).json()

            payload = {"format": "text", "content": "1. 题目一\nA. 1\nB. 2\n【答案】A"}
            client.post(f"/api/v1/imports/banks/{bank['id']}", headers=headers, json=payload)

            # Strategy 'new': should create a second question entity
            res_new = client.post(
                f"/api/v1/imports/banks/{bank['id']}",
                headers=headers,
                json={**payload, "duplicate_strategy": "new"},
            )
            self.assertEqual(res_new.status_code, 201)
            qs = client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
            self.assertEqual(len(qs), 2)

            # Strategy 'merge': should create a new version for the first question
            res_merge = client.post(
                f"/api/v1/imports/banks/{bank['id']}",
                headers=headers,
                json={**payload, "duplicate_strategy": "merge"},
            )
            self.assertEqual(res_merge.status_code, 201)
            # Total unique questions in bank should still be 2, but one question has version 2
            qs2 = client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
            self.assertEqual(len(qs2), 2)

    def test_manual_mapping_extended_options_up_to_h(self):
        """Test that manual mapping supports 8 options (A through H) completely."""
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "八选项题库"}).json()

            csv_content = (
                "q_col,o1,o2,o3,o4,o5,o6,o7,o8,ans_col\n"
                "八选项题目,选项一,选项二,选项三,选项四,选项五,选项六,选项七,选项八,H\n"
            )

            custom_mapping = {
                "stem": 0,
                "answer": 9,
                "options": [1, 2, 3, 4, 5, 6, 7, 8],
                "combined_options": None,
                "options_delimiter": "",
                "type": None,
                "difficulty": None,
                "tags": None,
                "explanation": None,
            }

            import_res = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("test8.csv", csv_content.encode("utf-8"), "text/csv")},
                data={"mapping": __import__("json").dumps(custom_mapping)},
            )
            self.assertEqual(import_res.status_code, 201)
            self.assertEqual(import_res.json()["imported_count"], 1)

            qs = client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
            self.assertEqual(len(qs), 1)
            self.assertEqual(qs[0]["stem"], "八选项题目")
            self.assertEqual(len(qs[0]["options"]), 8)
            self.assertEqual(qs[0]["options"][0]["content"], "选项一")
            self.assertEqual(qs[0]["options"][7]["content"], "选项八")
            self.assertEqual(qs[0]["answer"], "H")

    def test_sparse_manual_mapping_preserves_option_keys_without_renumbering(self):
        """Test that mapping sparse options (e.g. only B and E, or B/E/H) preserves their keys without renumbering to A/B/C."""
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "稀疏题库"}).json()

            # CSV with unmapped headers where only B, E, H are provided
            csv_content = (
                "q_col,col_b,col_e,col_h,ans_col\n"
                "稀疏选项题目,这是选项B内容,这是选项E内容,这是选项H内容,E\n"
            )

            # 1. Test sparse slot list: Slot 1 is B (col 1), Slot 4 is E (col 2), Slot 7 is H (col 3)
            sparse_slot_mapping = {
                "stem": 0,
                "answer": 4,
                "options": [None, 1, None, None, 2, None, None, 3],
                "combined_options": None,
                "options_delimiter": "",
                "type": None,
                "difficulty": None,
                "tags": None,
                "explanation": None,
            }

            import_res = client.post(
                f"/api/v1/imports/banks/{bank['id']}/file",
                headers=headers,
                files={"file": ("sparse.csv", csv_content.encode("utf-8"), "text/csv")},
                data={"mapping": __import__("json").dumps(sparse_slot_mapping)},
            )
            self.assertEqual(import_res.status_code, 201)
            self.assertEqual(import_res.json()["imported_count"], 1)

            qs = client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
            self.assertEqual(len(qs), 1)
            self.assertEqual(qs[0]["stem"], "稀疏选项题目")
            self.assertEqual(qs[0]["answer"], "E")
            opts = qs[0]["options"]
            self.assertEqual(len(opts), 3)
            # Crucial assertion: keys must NOT be renumbered to A, B, C!
            self.assertEqual(opts[0]["key"], "B")
            self.assertEqual(opts[0]["content"], "这是选项B内容")
            self.assertEqual(opts[1]["key"], "E")
            self.assertEqual(opts[1]["content"], "这是选项E内容")
            self.assertEqual(opts[2]["key"], "H")
            self.assertEqual(opts[2]["content"], "这是选项H内容")

            # 2. Test auto-detection on headers with explicit sparse option letters
            bank2 = client.post("/api/v1/banks", headers=headers, json={"name": "自动稀疏题库"}).json()
            csv_sparse_headers = (
                "题目,选项B,选项E,正确答案\n"
                "自动识别稀疏题目,B内容,E内容,B\n"
            )
            prev_res = client.post(
                f"/api/v1/imports/banks/{bank2['id']}/preview-file",
                headers=headers,
                files={"file": ("auto_sparse.csv", csv_sparse_headers.encode("utf-8"), "text/csv")},
            )
            self.assertEqual(prev_res.status_code, 200)
            self.assertEqual(prev_res.json()["mapping"]["options"], [None, 1, None, None, 2])

            import_res2 = client.post(
                f"/api/v1/imports/banks/{bank2['id']}/file",
                headers=headers,
                files={"file": ("auto_sparse.csv", csv_sparse_headers.encode("utf-8"), "text/csv")},
            )
            self.assertEqual(import_res2.status_code, 201)
            qs2 = client.get(f"/api/v1/banks/{bank2['id']}/questions", headers=headers).json()
            self.assertEqual(len(qs2), 1)
            opts2 = qs2[0]["options"]
            self.assertEqual(len(opts2), 2)
            self.assertEqual(opts2[0]["key"], "B")
            self.assertEqual(opts2[0]["content"], "B内容")
            self.assertEqual(opts2[1]["key"], "E")
            self.assertEqual(opts2[1]["content"], "E内容")


if __name__ == "__main__":
    unittest.main()



