import tempfile
import unittest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.infrastructure.db.connection import migrate

class TestBatch1Remediation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_batch1.db"
        migrate(self.db_path)
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_p1_1_password_hash_not_exposed_in_auth_apis(self):
        """P1-1: 注册、登录和 /auth/me 均不得在 JSON 响应中透出 password_hash"""
        reg_res = self.client.post("/api/v1/auth/register", json={"username": "alice_sec", "password": "Password123!"})
        self.assertEqual(reg_res.status_code, 201)
        reg_data = reg_res.json()
        self.assertNotIn("password_hash", reg_data)
        self.assertEqual(reg_data["username"], "alice_sec")

        login_res = self.client.post("/api/v1/auth/login", json={"username": "alice_sec", "password": "Password123!"})
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.json()
        self.assertNotIn("password_hash", login_data["user"])
        token = login_data["token"]

        me_res = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertNotIn("password_hash", me_data)

    def test_p1_2_p1_3_exam_active_desensitizes_practice_and_mistakes(self):
        """P1-2 & P1-3: 用户模考进行中，普通练习会话和错题列表必须遮蔽受保护考题的答案与解析"""
        self.client.post("/api/v1/auth/register", json={"username": "exam_user", "password": "Password123!"})
        login_res = self.client.post("/api/v1/auth/login", json={"username": "exam_user", "password": "Password123!"})
        token = login_res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 创建题库与题目 (包含 options 格式)
        bank_res = self.client.post("/api/v1/banks", json={"name": "安全模考测试题库"}, headers=headers)
        self.assertEqual(bank_res.status_code, 201)
        bank_id = bank_res.json()["id"]

        q_res = self.client.post(f"/api/v1/banks/{bank_id}/questions", json={
            "type": "SINGLE",
            "stem": "机密考试题目1",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            "answer": "A",
            "explanation": "机密解析：选A"
        }, headers=headers)
        self.assertEqual(q_res.status_code, 201)
        q_id = q_res.json()["id"]

        # 产生一个错题记录 (通过错误答题)
        prac_start = self.client.post("/api/v1/practice/sessions", json={"bank_id": bank_id, "mode": "ALL"}, headers=headers)
        prac_session_id = prac_start.json()["id"]
        self.client.post(f"/api/v1/practice/sessions/{prac_session_id}/attempts", json={
            "question_id": q_id,
            "user_answer": ["B"],
            "time_spent": 5
        }, headers=headers)
        self.client.post(f"/api/v1/practice/sessions/{prac_session_id}/complete", headers=headers)

        # 验证此时错题列表能正常查看解析 (调用 /api/v1/mistakes)
        mistakes_res1 = self.client.get(f"/api/v1/mistakes?bank_id={bank_id}", headers=headers)
        self.assertEqual(mistakes_res1.status_code, 200)
        m_list1 = mistakes_res1.json()
        self.assertTrue(len(m_list1) >= 1)
        self.assertEqual(m_list1[0]["answer"], "A")

        # 开启模考会话 (EXAM 模式)
        exam_start = self.client.post("/api/v1/practice/sessions", json={"bank_id": bank_id, "mode": "EXAM"}, headers=headers)
        exam_session_id = exam_start.json()["id"]

        # 1. 验证在模考进行中，错题列表不得暴露考题答案
        mistakes_res2 = self.client.get(f"/api/v1/mistakes?bank_id={bank_id}", headers=headers)
        self.assertEqual(mistakes_res2.status_code, 200)
        m_list2 = mistakes_res2.json()
        target_m = [m for m in m_list2 if m["question_id"] == q_id][0]
        self.assertEqual(target_m["answer"], "", "模考进行中，错题列表泄露了考题标准答案！")

        # 2. 验证开启另一个普通练习会话查看同一题目，也必须脱敏
        prac_start2 = self.client.post("/api/v1/practice/sessions", json={"bank_id": bank_id, "mode": "ALL"}, headers=headers)
        prac_session_id2 = prac_start2.json()["id"]
        prac2_detail = self.client.get(f"/api/v1/practice/sessions/{prac_session_id2}", headers=headers).json()
        target_q = [q for q in prac2_detail["questions"] if q["id"] == q_id][0]
        self.assertEqual(target_q.get("answer") or "", "", "模考进行中，普通练习接口泄露了考题标准答案！")
        self.assertEqual(target_q.get("explanation") or "", "", "模考进行中，普通练习接口泄露了考题解析！")

        # 完成模考
        self.client.post(f"/api/v1/practice/sessions/{exam_session_id}/complete", headers=headers)

        # 模考结束后，普通练习恢复答案可见
        prac2_after = self.client.get(f"/api/v1/practice/sessions/{prac_session_id2}", headers=headers).json()
        target_q_after = [q for q in prac2_after["questions"] if q["id"] == q_id][0]
        self.assertEqual(target_q_after.get("answer"), "A")

    def test_p2_4_conflict_requires_bank_member_permission(self):
        """P2-4: 查询题目冲突信息 get_active_conflict 必须校验用户在所属题库的成员权限，非成员拒绝访问"""
        self.client.post("/api/v1/auth/register", json={"username": "owner_a", "password": "Password123!"})
        login_a = self.client.post("/api/v1/auth/login", json={"username": "owner_a", "password": "Password123!"}).json()["token"]
        headers_a = {"Authorization": f"Bearer {login_a}"}

        bank_id = self.client.post("/api/v1/banks", json={"name": "冲突权限测试库"}, headers=headers_a).json()["id"]
        q_id = self.client.post(f"/api/v1/banks/{bank_id}/questions", json={
            "type": "SINGLE",
            "stem": "冲突测试题目",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            "answer": "A"
        }, headers=headers_a).json()["id"]

        self.client.post("/api/v1/auth/register", json={"username": "outsider_b", "password": "Password123!"})
        login_b = self.client.post("/api/v1/auth/login", json={"username": "outsider_b", "password": "Password123!"}).json()["token"]
        headers_b = {"Authorization": f"Bearer {login_b}"}

        res_b = self.client.get(f"/api/v1/questions/{q_id}/conflict", headers=headers_b)
        self.assertIn(res_b.status_code, (403, 404), f"局外人能够窥探题目冲突信息: {res_b.status_code}")
