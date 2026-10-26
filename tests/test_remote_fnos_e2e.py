"""Physical end-to-end test suite against a deployed fnOS EasyExam instance.

This entry point exercises the real product over HTTP. It never uses mocks or
localhost: the target must be a deployed fnOS instance reachable at
``FNOS_BASE_URL`` (for example ``http://<NAS_IP>:3000``).

Two-phase run (the second phase is what proves persistence across a restart):

1. ``FNOS_E2E_PHASE=chain`` (default) creates a throwaway user and question bank,
   drives login/register -> bank -> import -> practice -> mistakes -> mock exam ->
   export, then writes the observed state to ``FNOS_E2E_STATE_FILE``.
2. Restart the EasyExam app on the NAS (for an FPK install: ``cmd/main stop``
   followed by ``cmd/main start`` in the package directory).
3. ``FNOS_E2E_PHASE=post-restart`` logs in again with the same credentials and
   asserts every entity created in phase 1 is still readable and unchanged.

The suite deliberately does not delete the bank it creates: the data left behind
*is* the evidence for the restart check. Bank names are timestamped per run.

Required environment:
    FNOS_BASE_URL        deployed instance base URL, e.g. http://<NAS_IP>:3000
    FNOS_E2E_EXPECTED_SHA  the revision the deployed build was made from; the
                         instance's reported ``commit_sha`` must equal it, so the
                         result is attributable to that revision and not to
                         whatever happened to be running
Optional environment:
    FNOS_E2E_PHASE       "chain" (default) or "post-restart"
    FNOS_E2E_STATE_FILE  where phase 1 writes the state phase 2 reads
    FNOS_E2E_USER        username to reuse instead of generating one
    FNOS_E2E_PASSWORD    password for FNOS_E2E_USER (default: generated per run)
"""

import json
import os
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = (os.environ.get("FNOS_BASE_URL") or "").strip().rstrip("/")
API_BASE = f"{BASE_URL}/api/v1" if BASE_URL else ""

PHASE = (os.environ.get("FNOS_E2E_PHASE") or "chain").strip().lower()
STATE_FILE = Path(
    os.environ.get("FNOS_E2E_STATE_FILE")
    or (Path(tempfile.gettempdir()) / "easyexam_fnos_e2e_state.json")
)

# The revision the deployed instance is expected to run. Accepting an unlabelled
# build here is how a previous run ended up reporting a *different* revision as
# acceptance evidence, so the running ``commit_sha`` is asserted against it.
EXPECTED_SHA = (os.environ.get("FNOS_E2E_EXPECTED_SHA") or "").strip().lower()

SINGLE_STEM = "fnOS 物理验收：题库系统使用什么存储引擎？"
MULTI_STEM = "fnOS 物理验收：核心刷题能力包含哪些？"
SECOND_SINGLE_STEM = "fnOS 物理验收：错题需要连续答对几次才出库？"

IMPORT_CONTENT = f"""1. (单选) {SINGLE_STEM}
A. PostgreSQL
B. 单文件 SQLite
C. MongoDB
D. Redis
答案：B
解析：单文件 SQLite 便于私有云单机持久化。
标签：架构

2. (多选) {MULTI_STEM}
A. 点选即判
B. 断点续答
C. 错题归因
D. 强制白屏刷新
答案：ABC
解析：核心能力不含强制白屏刷新。
标签：体验

3. (单选) {SECOND_SINGLE_STEM}
A. 1 次
B. 2 次
C. 3 次
D. 永不
答案：B
解析：连续答对两次即从错题本出库。
标签：体验
"""


class FnOsApi:
    """Minimal authenticated JSON client for the deployed fnOS API."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token = None

    def call(self, method: str, path: str, payload: dict | None = None, raw: bool = False):
        url = f"{self.base_url}{path}"
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read()
                if raw:
                    return response.status, body
                return response.status, (json.loads(body.decode("utf-8")) if body else None)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            if raw:
                return exc.code, body
            try:
                return exc.code, json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return exc.code, body.decode("utf-8", errors="replace")


class TestRemoteFnOsE2E(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        if not BASE_URL:
            raise unittest.SkipTest(
                "FNOS_BASE_URL is not set; point it at a deployed fnOS instance "
                "(e.g. FNOS_BASE_URL=http://<NAS_IP>:3000)"
            )
        cls.api = FnOsApi(API_BASE)
        try:
            status, health = cls.api.call("GET", "/health")
        except (urllib.error.URLError, OSError) as exc:
            raise unittest.SkipTest(f"Cannot reach fnOS at {BASE_URL}: {exc}")
        if status != 200 or not isinstance(health, dict):
            raise AssertionError(f"fnOS health check failed: HTTP {status} {health!r}")
        cls.health = health

    def _require_phase(self, phase: str):
        if PHASE != phase:
            raise unittest.SkipTest(
                f"phase {phase!r} not active (FNOS_E2E_PHASE={PHASE!r}); "
                "restart EasyExam on the NAS and rerun with FNOS_E2E_PHASE=post-restart"
            )

    def _assert_running_revision(self):
        """Fail unless the deployed build reports ``FNOS_E2E_EXPECTED_SHA``.

        Both SHAs are printed so the run itself carries the target/revision pair.
        """
        running = str(self.health.get("commit_sha") or "").strip()
        print(f"\n[revision] target={EXPECTED_SHA or '<unset>'} running={running or '<empty>'}")
        if not EXPECTED_SHA:
            raise AssertionError(
                "FNOS_E2E_EXPECTED_SHA is required: set it to the revision this build was made "
                f"from, otherwise the result cannot be attributed to that revision (running={running!r})"
            )
        self.assertEqual(
            running.lower(), EXPECTED_SHA,
            f"deployed revision {running!r} is not the target revision {EXPECTED_SHA!r}; "
            "the evidence would not belong to this revision",
        )

    def _login(self, username: str, password: str) -> None:
        status, body = self.api.call("POST", "/auth/login", {"username": username, "password": password})
        self.assertEqual(status, 200, f"login failed for {username}: {body}")
        self.assertIsInstance(body, dict)
        self.assertTrue(body.get("token"), "login response must carry a bearer token")
        self.api.token = body["token"]

    def _questions_by_stem(self, bank_id: str) -> dict[str, dict]:
        status, questions = self.api.call("GET", f"/banks/{bank_id}/questions")
        self.assertEqual(status, 200, f"question list failed: {questions}")
        self.assertIsInstance(questions, list)
        return {q["stem"]: q for q in questions}

    @staticmethod
    def _question(questions: dict[str, dict], marker: str) -> dict:
        """Find the one question whose stem contains ``marker``.

        The source stem keeps whatever prefix the author typed (e.g. ``(单选) ``),
        so matching on a stable substring is more robust than an exact stem.
        """
        matched = [q for stem, q in questions.items() if marker in stem]
        if len(matched) != 1:
            raise AssertionError(
                f"expected exactly one question containing {marker!r}, found {len(matched)}: "
                f"{sorted(stem for stem in questions if marker in stem)}"
            )
        return matched[0]

    # ------------------------------------------------------------------ phase 1

    def test_01_health_and_pwa_web_shell(self):
        """The deployed instance answers /api/v1/health and serves the PWA shell."""
        self._require_phase("chain")
        self._assert_running_revision()

        self.assertEqual(self.health.get("status"), "ok", self.health)
        self.assertEqual(self.health.get("app"), "easy-exam", self.health)

        request = urllib.request.Request(f"{BASE_URL}/")
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertEqual(response.status, 200)
            html = response.read().decode("utf-8", errors="replace")
            cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("EasyExam", html)
        self.assertIn("viewport", html)
        self.assertIn("apple-mobile-web-app-capable", html)
        self.assertIn("no-store", cache_control, "SPA entry must not be client-cached")

    def test_02_core_chain_and_state_capture(self):
        """register/login -> bank -> import -> practice -> mistakes -> exam -> export."""
        self._require_phase("chain")

        username = os.environ.get("FNOS_E2E_USER") or f"fnos_e2e_{int(time.time())}"
        password = os.environ.get("FNOS_E2E_PASSWORD") or f"Fn0sE2E!{int(time.time())}"
        bank_name = f"fnOS物理验收题库-{int(time.time())}"

        status, _ = self.api.call("POST", "/auth/register", {"username": username, "password": password})
        self.assertIn(status, (201, 409), "register must create the account or report it already exists")
        self._login(username, password)

        status, me = self.api.call("GET", "/auth/me")
        self.assertEqual(status, 200, f"/auth/me failed: {me}")
        self.assertEqual(me.get("username"), username)

        # 1. Bank
        status, bank = self.api.call("POST", "/banks", {
            "name": bank_name,
            "description": "fnOS 物理验收自动创建",
            "category": "物理验收",
        })
        self.assertEqual(status, 201, f"create bank failed: {bank}")
        bank_id = bank["id"]
        self.assertTrue(bank_id)

        # 2. Import through the real text importer
        status, imported = self.api.call("POST", f"/imports/banks/{bank_id}", {
            "format": "text",
            "content": IMPORT_CONTENT,
        })
        self.assertEqual(status, 201, f"import failed: {imported}")
        self.assertEqual(imported.get("imported_count"), 3, imported)

        questions = self._questions_by_stem(bank_id)
        self.assertEqual(len(questions), 3, sorted(questions))
        single = self._question(questions, SINGLE_STEM)
        multi = self._question(questions, MULTI_STEM)
        second_single = self._question(questions, SECOND_SINGLE_STEM)
        self.assertEqual(single["type"], "SINGLE")
        self.assertEqual(single["answer"], "B")
        self.assertEqual(len(single["options"]), 4)
        self.assertEqual(multi["type"], "MULTI")
        self.assertEqual(second_single["type"], "SINGLE")
        self.assertEqual(second_single["answer"], "B")

        # 3. Practice session
        status, session = self.api.call("POST", "/practice/sessions", {
            "bank_id": bank_id,
            "mode": "PRACTICE",
            "total_questions": 3,
            "time_limit": 0,
        })
        self.assertEqual(status, 201, f"start practice failed: {session}")
        practice_id = session["id"]

        status, wrong = self.api.call("POST", f"/practice/sessions/{practice_id}/answer", {
            "question_id": single["id"],
            "user_answer": "A",
            "mistake_cause": "CONCEPT_GAP",
        })
        self.assertEqual(status, 201, f"wrong answer rejected: {wrong}")
        self.assertEqual(wrong["correctness"], "INCORRECT")
        self.assertFalse(wrong["is_correct"])
        self.assertEqual(wrong["score_ratio"], 0.0)

        status, partial = self.api.call("POST", f"/practice/sessions/{practice_id}/answer", {
            "question_id": multi["id"],
            "user_answer": "A,B",
        })
        self.assertEqual(status, 201, f"partial answer rejected: {partial}")
        self.assertEqual(partial["correctness"], "PARTIAL", "a subset of a MULTI answer scores partially")
        self.assertEqual(partial["score_ratio"], 0.5)

        status, correct = self.api.call("POST", f"/practice/sessions/{practice_id}/answer", {
            "question_id": second_single["id"],
            "user_answer": "B",
        })
        self.assertEqual(status, 201, f"correct answer rejected: {correct}")
        self.assertEqual(correct["correctness"], "CORRECT")

        status, synced = self.api.call("POST", f"/practice/sessions/{practice_id}/sync", {
            "current_index": 2,
            "answers": {single["id"]: "A", multi["id"]: "A,B"},
            "flags": [multi["id"]],
            "time_spent": 20,
        })
        self.assertEqual(status, 200, f"draft sync failed: {synced}")
        self.assertEqual(synced["current_index"], 2)
        self.assertIn(multi["id"], synced["flags"])

        # 4. Mistakes: wrong answers enter the book, two consecutive correct clear it
        status, mistakes = self.api.call("GET", f"/mistakes?bank_id={bank_id}")
        self.assertEqual(status, 200, f"mistake list failed: {mistakes}")
        mistake_by_qid = {m["question_id"]: m for m in mistakes}
        self.assertIn(single["id"], mistake_by_qid)
        self.assertEqual(mistake_by_qid[single["id"]]["mistake_cause"], "CONCEPT_GAP")
        self.assertEqual(mistake_by_qid[single["id"]]["consecutive_correct"], 0)
        self.assertEqual(mistake_by_qid[single["id"]]["is_cleared"], 0)

        for expected in (1, 2):
            status, review = self.api.call("POST", f"/mistakes/{single['id']}/review", {
                "user_answer": "B",
                "rating": 3,
            })
            self.assertEqual(status, 201, f"review #{expected} failed: {review}")
            self.assertEqual(review["correctness"], "CORRECT")

        status, remaining = self.api.call("GET", f"/mistakes?bank_id={bank_id}")
        self.assertEqual(status, 200)
        remaining_ids = {m["question_id"] for m in remaining}
        self.assertNotIn(single["id"], remaining_ids, "two consecutive correct answers must clear the mistake")
        self.assertIn(multi["id"], remaining_ids, "an untouched partial-credit mistake must stay in the book")

        # 5. Mock exam, then idempotent submission
        status, exam = self.api.call("POST", "/exams/sessions", {
            "bank_id": bank_id,
            "total_questions": 3,
            "time_limit": 1800,
        })
        self.assertEqual(status, 201, f"start exam failed: {exam}")
        exam_id = exam["id"]

        status, exam_answer = self.api.call("POST", f"/practice/sessions/{exam_id}/answer", {
            "question_id": second_single["id"],
            "user_answer": "B",
        })
        self.assertEqual(status, 201, f"exam answer failed: {exam_answer}")
        self.assertFalse(exam_answer.get("feedback_available"), "exam answers must not leak verdicts mid-exam")

        status, report = self.api.call("POST", f"/exams/sessions/{exam_id}/complete")
        self.assertEqual(status, 200, f"complete exam failed: {report}")
        for key in ("is_completed", "score", "accuracy", "total_questions",
                    "answered_count", "correct_count", "partial_count",
                    "incorrect_count", "unanswered_count", "type_stats", "tag_stats"):
            self.assertIn(key, report, f"exam report is missing {key!r}")
        self.assertTrue(report["is_completed"])
        self.assertEqual(report["answered_count"], 1)
        self.assertEqual(report["correct_count"], 1)
        self.assertEqual(report["unanswered_count"], 2)

        status, again = self.api.call("POST", f"/exams/sessions/{exam_id}/complete")
        self.assertEqual(status, 200, "a submitted exam must stay readable")
        self.assertEqual(again["score"], report["score"])
        self.assertEqual(again["accuracy"], report["accuracy"])

        # 6. Export in every format the API really implements
        for fmt in ("json", "csv", "xlsx", "txt"):
            url = f"/banks/{bank_id}/export?format={urllib.parse.quote(fmt)}"
            status, body = self.api.call("GET", url, raw=True)
            self.assertEqual(status, 200, f"export format {fmt} failed")
            self.assertTrue(body, f"export format {fmt} returned an empty body")

        # 7. Persist what phase 2 must find unchanged after the NAS restart
        state = {
            "base_url": BASE_URL,
            "username": username,
            "password": password,
            "bank_id": bank_id,
            "bank_name": bank_name,
            "question_answers": {
                single["id"]: single["answer"],
                multi["id"]: multi["answer"],
                second_single["id"]: second_single["answer"],
            },
            "question_types": {
                single["id"]: "SINGLE",
                multi["id"]: "MULTI",
                second_single["id"]: "SINGLE",
            },
            "cleared_mistake_id": single["id"],
            "remaining_mistake_id": multi["id"],
            "practice_session_id": practice_id,
            "exam_session_id": exam_id,
            "exam_score": report["score"],
            "exam_accuracy": report["accuracy"],
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[phase chain] state written to {STATE_FILE}")
        print(f"[phase chain] next: restart EasyExam on the NAS, then rerun with FNOS_E2E_PHASE=post-restart")

    # ------------------------------------------------------------------ phase 2

    def test_03_data_survives_restart(self):
        """Everything created before the restart is still readable and unchanged."""
        self._require_phase("post-restart")
        self._assert_running_revision()
        if not STATE_FILE.exists():
            self.skipTest(
                f"no captured state at {STATE_FILE}; run FNOS_E2E_PHASE=chain first"
            )
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        self.assertEqual(state["base_url"], BASE_URL, "state file belongs to a different instance")

        self._login(state["username"], state["password"])

        status, bank = self.api.call("GET", f"/banks/{state['bank_id']}")
        self.assertEqual(status, 200, f"bank disappeared after restart: {bank}")
        self.assertEqual(bank["name"], state["bank_name"])

        questions = self._questions_by_stem(state["bank_id"])
        self.assertEqual(len(questions), 3, sorted(questions))
        answer_by_id = {q["id"]: q["answer"] for q in questions.values()}
        self.assertEqual(answer_by_id, state["question_answers"],
                         "question content changed across the restart")
        type_by_id = {q["id"]: q["type"] for q in questions.values()}
        self.assertEqual(type_by_id, state["question_types"])

        status, mistakes = self.api.call("GET", f"/mistakes?bank_id={state['bank_id']}")
        self.assertEqual(status, 200, f"mistake list failed after restart: {mistakes}")
        mistake_ids = {m["question_id"] for m in mistakes}
        self.assertNotIn(state["cleared_mistake_id"], mistake_ids,
                         "a cleared mistake must stay cleared after the restart")
        self.assertIn(state["remaining_mistake_id"], mistake_ids,
                      "an open mistake must survive the restart")

        status, replayed = self.api.call("POST", f"/exams/sessions/{state['exam_session_id']}/complete")
        self.assertEqual(status, 200, f"completed exam is not readable after restart: {replayed}")
        self.assertEqual(replayed["score"], state["exam_score"])
        self.assertEqual(replayed["accuracy"], state["exam_accuracy"])
        self.assertEqual(replayed["answered_count"], 1)
        self.assertTrue(replayed["is_completed"])

        status, practice = self.api.call("GET", f"/practice/sessions/{state['practice_session_id']}")
        self.assertEqual(status, 200, f"practice session disappeared after restart: {practice}")
        self.assertEqual(practice["bank_id"], state["bank_id"])

        print(f"\n[phase post-restart] all entities captured at {state['captured_at']} survived the restart")


if __name__ == "__main__":
    unittest.main()
