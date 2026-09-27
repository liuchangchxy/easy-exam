import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestV1Sync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.app = create_app(db_path=self.tmp.name)
        self.client = TestClient(self.app)

        # User (shared across Device A and Device B)
        self.client.post("/api/v1/auth/register", json={"username": "sync_user", "password": "password123"})
        res = self.client.post("/api/v1/auth/login", json={"username": "sync_user", "password": "password123"})
        self.token = res.json()["token"]
        self.auth = {"Authorization": f"Bearer {self.token}"}

        # Create bank and initial question
        bank_res = self.client.post("/api/v1/banks", headers=self.auth, json={"name": "Sync Test Bank"})
        self.bank_id = bank_res.json()["id"]

        q_res = self.client.post(
            f"/api/v1/banks/{self.bank_id}/questions",
            headers=self.auth,
            json={
                "stem": "初始题目题干",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "A",
                "explanation": "初始解析",
                "difficulty": 1,
            },
        )
        self.question = q_res.json()
        self.question_id = self.question["id"]

    def tearDown(self):
        try:
            if os.path.exists(self.tmp.name):
                os.unlink(self.tmp.name)
        except Exception:
            pass

    def test_multi_device_events_append_and_idempotent_replay(self):
        """
        SPEC §2.1 & §6:
        Learning events from multiple devices are appended, idempotent on retry,
        and replayed in server chronological order.
        """
        # Device A generates event 1 and 2
        events_dev_a = [
            {
                "id": "evt-devA-001",
                "event_type": "SESSION_OPEN",
                "aggregate_type": "SESSION",
                "aggregate_id": "sess-001",
                "payload": {"client_device": "DeviceA_Laptop", "timestamp": "2026-09-24T10:00:00Z"},
            },
            {
                "id": "evt-devA-002",
                "event_type": "ATTEMPT_SUBMIT",
                "aggregate_type": "QUESTION",
                "aggregate_id": self.question_id,
                "payload": {"client_device": "DeviceA_Laptop", "answer": "A"},
            },
        ]

        # Device B generates event 3 concurrently
        events_dev_b = [
            {
                "id": "evt-devB-001",
                "event_type": "FLAG_WEAK",
                "aggregate_type": "QUESTION",
                "aggregate_id": self.question_id,
                "payload": {"client_device": "DeviceB_Phone", "reason": "marked weak on mobile"},
            },
        ]

        # Sync Device A events
        res_a = self.client.post("/api/v1/sync/events", headers=self.auth, json={"events": events_dev_a})
        self.assertEqual(res_a.status_code, 201)
        self.assertEqual(res_a.json()["accepted"], 2)

        # Retry Device A events (idempotence check)
        res_a_retry = self.client.post("/api/v1/sync/events", headers=self.auth, json={"events": events_dev_a})
        self.assertEqual(res_a_retry.status_code, 201)
        self.assertEqual(res_a_retry.json()["accepted"], 0)  # 0 new accepted

        # Sync Device B events
        res_b = self.client.post("/api/v1/sync/events", headers=self.auth, json={"events": events_dev_b})
        self.assertEqual(res_b.status_code, 201)
        self.assertEqual(res_b.json()["accepted"], 1)

        # Query all events
        all_events = self.client.get("/api/v1/sync/events", headers=self.auth).json()
        self.assertEqual(len(all_events), 3)
        evt_ids = [e["id"] for e in all_events]
        self.assertEqual(evt_ids, ["evt-devA-001", "evt-devA-002", "evt-devB-001"])

    def test_concurrent_edit_conflict_preserves_both_versions_without_silent_overwrite(self):
        """
        SPEC §2.1 & §8:
        When multiple devices modify a question or explanations concurrently,
        both versions are preserved and visible to the user rather than silently overwritten.
        """
        # Device A updates question content (creates version 2)
        res_v2 = self.client.put(
            f"/api/v1/questions/{self.question_id}",
            headers=self.auth,
            json={
                "stem": "Device A 修改题干：增加考点说明",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "A",
                "explanation": "Device A 补充解析",
                "difficulty": 2,
            },
        )
        self.assertEqual(res_v2.status_code, 200)
        v2_data = res_v2.json()
        self.assertEqual(v2_data["version_number"], 2)

        # Device B also updates question content from its perspective (creates version 3)
        res_v3 = self.client.put(
            f"/api/v1/questions/{self.question_id}",
            headers=self.auth,
            json={
                "stem": "Device B 并发修改题干：补充案例背景",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "A",
                "explanation": "Device B 案例解析",
                "difficulty": 2,
            },
        )
        self.assertEqual(res_v3.status_code, 200)
        v3_data = res_v3.json()
        self.assertEqual(v3_data["version_number"], 3)

        # Verify all versions exist and neither was silently deleted or replaced
        versions_res = self.client.get(f"/api/v1/questions/{self.question_id}/versions", headers=self.auth)
        self.assertEqual(versions_res.status_code, 200)
        versions = versions_res.json()
        self.assertEqual(len(versions), 3)
        version_stems = [v["stem"] for v in versions]
        self.assertIn("初始题目题干", version_stems)
        self.assertIn("Device A 修改题干：增加考点说明", version_stems)
        self.assertIn("Device B 并发修改题干：补充案例背景", version_stems)

    def test_server_detects_conflict_and_allows_resolution(self):
        """
        Verify server detects concurrent edits based on stale base_version_number,
        flags active conflict, and allows user resolution.
        """
        # Initial question is v1
        # Device A updates based on v1 -> becomes v2
        res_a = self.client.put(
            f"/api/v1/questions/{self.question_id}",
            headers=self.auth,
            json={
                "stem": "Device A update",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "base_version_number": 1,
            },
        )
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.json()["version_number"], 2)

        # Device B updates based on v1 (stale base!) -> creates v3 with conflict detected
        res_b = self.client.put(
            f"/api/v1/questions/{self.question_id}",
            headers=self.auth,
            json={
                "stem": "Device B concurrent update",
                "type": "SINGLE",
                "options": [{"key": "B", "content": "2"}],
                "base_version_number": 1,
            },
        )
        self.assertEqual(res_b.status_code, 200)
        self.assertEqual(res_b.json()["version_number"], 3)

        # Server reports active conflict
        conflict_res = self.client.get(f"/api/v1/questions/{self.question_id}/conflict", headers=self.auth)
        self.assertEqual(conflict_res.status_code, 200)
        c_data = conflict_res.json()
        self.assertTrue(c_data["has_conflict"])
        self.assertEqual(c_data["conflict"]["base_version_number"], 1)
        self.assertEqual(c_data["conflict"]["server_version_number"], 2)
        self.assertEqual(c_data["conflict"]["client_version_number"], 3)

        # User resolves conflict by adopting version 2
        resolve_res = self.client.post(
            f"/api/v1/questions/{self.question_id}/resolve-conflict",
            headers=self.auth,
            json={"adopt_version_number": 2},
        )
        self.assertEqual(resolve_res.status_code, 200)
        resolved_q = resolve_res.json()
        self.assertEqual(resolved_q["version_number"], 4)
        self.assertEqual(resolved_q["stem"], "Device A update")

        # Conflict is now marked resolved
        after_conflict = self.client.get(f"/api/v1/questions/{self.question_id}/conflict", headers=self.auth).json()
        self.assertFalse(after_conflict["has_conflict"])

    def test_abandon_active_session_and_abandon_all(self):
        """Active unfinished sessions can be individually abandoned or batch abandoned."""
        # Create 3 active sessions
        sess1 = self.client.post("/api/v1/practice/sessions", headers=self.auth, json={"bank_id": self.bank_id, "mode": "PRACTICE"}).json()
        sess2 = self.client.post("/api/v1/practice/sessions", headers=self.auth, json={"bank_id": self.bank_id, "mode": "PRACTICE"}).json()
        sess3 = self.client.post("/api/v1/practice/sessions", headers=self.auth, json={"bank_id": self.bank_id, "mode": "PRACTICE"}).json()

        active = self.client.get("/api/v1/practice/sessions/active", headers=self.auth).json()
        self.assertEqual(len(active), 3)

        # Abandon individual session 1
        res = self.client.post(f"/api/v1/practice/sessions/{sess1['id']}/abandon", headers=self.auth)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "abandoned")

        active_after = self.client.get("/api/v1/practice/sessions/active", headers=self.auth).json()
        self.assertEqual(len(active_after), 2)
        active_ids = [s["id"] for s in active_after]
        self.assertNotIn(sess1["id"], active_ids)

        # Abandon all remaining sessions
        res_all = self.client.post("/api/v1/practice/sessions/abandon-all", headers=self.auth)
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(res_all.json()["count"], 2)

        active_empty = self.client.get("/api/v1/practice/sessions/active", headers=self.auth).json()
        self.assertEqual(len(active_empty), 0)
