"""PR 90 learning-state integrity regressions.

Covers the review findings around:
- kill state: only a wrong answer inside the elimination queue revives a killed
  question; stale/offline sessions from any other mode must never do so;
- regrade: no fabricated FSRS ratings and no mistakes for sessions that opted
  out of mistake recording;
- archiving: archived questions leave due/mistake/kill queues and statistics
  without destroying the underlying learning data;
- moving: other members' in-progress sessions keep working and historical
  statistics stay attributed to the bank they were practiced in.
"""
import json
import sqlite3
import tempfile
import unittest

from backend.app.application.auth_service import AuthService
from backend.app.application.bank_service import BankService
from backend.app.application.practice_service import PracticeService
from backend.app.infrastructure.db.connection import migrate
from backend.app.infrastructure.db.repositories.bank_repository import BankRepository
from backend.app.infrastructure.db.repositories.practice_repository import PracticeRepository
from backend.app.infrastructure.db.repositories.question_repository import QuestionRepository
from backend.app.infrastructure.db.repositories.user_repository import UserRepository, UserSessionRepository


class _Base(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_pr90_state.db"
        migrate(self.db_path)
        self.users = UserRepository(self.db_path)
        self.user_sessions = UserSessionRepository(self.db_path)
        self.banks = BankRepository(self.db_path)
        self.questions = QuestionRepository(self.db_path)
        self.practices = PracticeRepository(self.db_path)

        self.auth = AuthService(self.users, self.user_sessions)
        self.bank_service = BankService(self.banks, self.questions)
        self.practice_service = PracticeService(self.practices, self.questions, self.banks)

        self.user_id = self.auth.register("state_owner", "Password123")["id"]
        self.bank_id = self.bank_service.create_bank(self.user_id, {"name": "State Bank"})["id"]

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _question(self, bank_id=None, stem="State question", answer="A", owner_id=None):
        owner_id = owner_id or self.user_id
        return self.bank_service.create_question(owner_id, bank_id or self.bank_id, {
            "stem": stem,
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}, {"key": "B", "content": "B"}],
            "answer": answer,
        })

    def _killed_ids(self, user_id=None):
        return {row["question_id"] for row in self.practices.list_killed(user_id or self.user_id)}


class KillStateSafetyTests(_Base):
    def test_wrong_answer_outside_elimination_never_revives_a_killed_question(self):
        q = self._question()
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )
        # Kill happens while the practice session is still open (e.g. on another
        # device); the queued/offline answer arrives afterwards.
        self.practices.kill(self.user_id, q["id"])
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")

        self.assertIn(q["id"], self._killed_ids(), "普通刷题答错不得解除斩杀")

    def test_wrong_answer_in_stale_fsrs_session_never_revives_a_killed_question(self):
        q = self._question()
        self.practices.mark_weak(self.user_id, q["id"])
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="FSRS", question_ids=[q["id"]],
        )
        self.practices.kill(self.user_id, q["id"])
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")

        self.assertIn(q["id"], self._killed_ids(), "FSRS 复习答错不得解除斩杀")

    def test_correct_answer_in_elimination_keeps_the_question_killed(self):
        q = self._question()
        self.practices.kill(self.user_id, q["id"])
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="ELIMINATION", question_ids=[q["id"]],
        )
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "A")

        self.assertIn(q["id"], self._killed_ids(), "查漏补缺答对不应解除斩杀")

    def test_wrong_answer_in_elimination_revives_and_reenters_review_queues(self):
        q = self._question()
        self.practices.kill(self.user_id, q["id"])
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="ELIMINATION", question_ids=[q["id"]],
        )
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")

        self.assertNotIn(q["id"], self._killed_ids(), "查漏补缺答错必须解除斩杀")
        mistake_ids = {row["question_id"] for row in self.practices.list_mistakes(self.user_id)}
        self.assertIn(q["id"], mistake_ids, "解除斩杀后题目应重新进入错题队列")


class RegradeIntegrityTests(_Base):
    def _card(self, question_id, user_id=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return dict(conn.execute(
                "SELECT state, stability, difficulty, due_at, last_review_at FROM fsrs_cards WHERE user_id = ? AND question_id = ?",
                (user_id or self.user_id, question_id),
            ).fetchone())

    def test_regrade_does_not_fabricate_an_fsrs_rating_for_an_unrated_attempt(self):
        # The attempt is submitted without an explicit rating. save_attempt may
        # auto-schedule the card, but the attempt itself has fsrs_rating = NULL.
        q = self._question(answer="A")
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")
        self.practice_service.complete_session(self.user_id, session["id"])

        with sqlite3.connect(self.db_path) as conn:
            rating = conn.execute(
                "SELECT fsrs_rating FROM answer_attempts WHERE user_id = ? AND question_id = ?",
                (self.user_id, q["id"]),
            ).fetchone()[0]
        self.assertIsNone(rating)

        card_before = self._card(q["id"])
        # The answer changes to B, so the old answer now scores CORRECT. A
        # fabricated "Good(3)" replay would visibly reschedule the card; the
        # truthful behaviour is to leave the existing card untouched.
        self.questions.create_next_version(self.user_id, q["id"], {
            "stem": "State question",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}, {"key": "B", "content": "B"}],
            "answer": "B",
            "regrade_history": True,
            "apply_fsrs": True,
        })
        self.assertEqual(self._card(q["id"]), card_before, "无评级作答重判不得伪造 FSRS 评级或重排卡片")

    def test_regrade_still_replays_rated_history(self):
        q = self._question(answer="A")
        self.practices.mark_weak(self.user_id, q["id"])
        review = self.practice_service.review_answer(self.user_id, q["id"], "A", 3)
        self.assertEqual(review["fsrs_rating"], 3)

        # Move the stored card off its truthful state so the replay is visible:
        # a rated history regrade must rebuild it from the pre-attempt snapshot.
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE fsrs_cards SET state = 0, stability = 99.0, difficulty = 5.0, last_review_at = NULL "
                "WHERE user_id = ? AND question_id = ?",
                (self.user_id, q["id"]),
            )

        self.questions.regrade_question_history(self.user_id, q["id"], apply_fsrs=True)
        card = self._card(q["id"])
        self.assertIsNotNone(card["last_review_at"], "有评级的历史重判仍应能够正常重放")
        self.assertNotEqual(card["stability"], 99.0, "有评级的历史必须基于真实快照重新调度")

    def test_regrade_never_creates_mistakes_for_record_mistakes_false_sessions(self):
        q = self._question()
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="EXAM", total_questions=1,
            question_ids=[q["id"]], record_mistakes=False,
        )
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")
        self.practice_service.complete_session(self.user_id, session["id"])

        with sqlite3.connect(self.db_path) as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM mistake_records WHERE user_id = ? AND question_id = ?",
                (self.user_id, q["id"]),
            ).fetchone()[0]
        self.assertEqual(before, 0)

        self.questions.regrade_question_history(self.user_id, q["id"], apply_fsrs=True)
        with sqlite3.connect(self.db_path) as conn:
            after = conn.execute(
                "SELECT COUNT(*) FROM mistake_records WHERE user_id = ? AND question_id = ?",
                (self.user_id, q["id"]),
            ).fetchone()[0]
        self.assertEqual(after, 0, "record_mistakes=False 的会话重判后仍不得产生错题")

    def test_practice_record_mistakes_false_does_not_create_mistake_records(self):
        q = self._question()
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
            record_mistakes=False,
        )
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")

        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM mistake_records WHERE user_id = ? AND question_id = ?",
                (self.user_id, q["id"]),
            ).fetchone()[0]
        self.assertEqual(count, 0, "record_mistakes=False 时刷题不得产生错题")


class ArchivedQuestionVisibilityTests(_Base):
    def _archive(self, question_ids, bank_id=None):
        return self.bank_service.batch_questions(
            self.user_id,
            bank_id or self.bank_id,
            {"question_ids": question_ids, "operation": "archive"},
        )

    def _restore(self, question_ids, bank_id=None):
        return self.bank_service.batch_questions(
            self.user_id,
            bank_id or self.bank_id,
            {"question_ids": question_ids, "operation": "restore"},
        )

    def test_archived_question_leaves_due_mistake_and_kill_queues_and_stats(self):
        mistaken = self._question(stem="Mistaken archived")
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[mistaken["id"]],
        )
        self.practice_service.submit_attempt(self.user_id, session["id"], mistaken["id"], "B")
        self.practice_service.complete_session(self.user_id, session["id"])

        due = self._question(stem="Due archived")
        self.practices.mark_weak(self.user_id, due["id"])

        killed = self._question(stem="Killed archived")
        self.practices.kill(self.user_id, killed["id"])

        archived_ids = [mistaken["id"], due["id"], killed["id"]]
        summary_before = self.practices.summary(self.user_id)
        trends_before = self.practices.trends(self.user_id, self.bank_id)

        self._archive(archived_ids)

        self.assertNotIn(mistaken["id"], {r["question_id"] for r in self.practices.list_mistakes(self.user_id)})
        self.assertNotIn(due["id"], {r["question_id"] for r in self.practices.list_due_reviews(self.user_id)})
        self.assertNotIn(killed["id"], self._killed_ids())

        summary_after = self.practices.summary(self.user_id)
        trends_after = self.practices.trends(self.user_id, self.bank_id)
        self.assertLess(summary_after["attempts"], summary_before["attempts"], "归档题不得计入作答统计")
        self.assertLess(summary_after["tracked_questions"], summary_before["tracked_questions"], "归档题不得计入掌握题数")
        self.assertLess(trends_after["total_questions"], trends_before["total_questions"], "归档题不得计入题库覆盖总数")
        self.assertLess(
            trends_after["recent"]["attempts"], trends_before["recent"]["attempts"],
            "归档题不得计入近期作答统计",
        )

        # Restoring must bring the same real data back, not recreate a blank state.
        self._restore(archived_ids)
        self.assertIn(mistaken["id"], {r["question_id"] for r in self.practices.list_mistakes(self.user_id)})
        self.assertIn(due["id"], {r["question_id"] for r in self.practices.list_due_reviews(self.user_id)})
        self.assertIn(killed["id"], self._killed_ids())
        self.assertEqual(self.practices.summary(self.user_id), summary_before)
        self.assertEqual(self.practices.trends(self.user_id, self.bank_id), trends_before)


class MoveSessionContinuityTests(_Base):
    def test_move_keeps_other_members_session_alive_and_keeps_history_attribution(self):
        admin_id = self.auth.register("move_admin", "Password123")["id"]
        member_id = self.auth.register("move_member", "Password123")["id"]
        source = self.bank_service.create_bank(admin_id, {"name": "Source"})["id"]
        target = self.bank_service.create_bank(admin_id, {"name": "Target"})["id"]
        self.banks.add_member(source, admin_id, "move_member", "MEMBER")

        q = self._question(bank_id=source, stem="Moved mid-session", owner_id=admin_id)
        session = self.practice_service.start_session(
            member_id, source, mode="PRACTICE", question_ids=[q["id"]],
        )

        self.bank_service.batch_questions(
            admin_id, source,
            {"question_ids": [q["id"]], "operation": "move", "target_bank_id": target},
        )

        reopened = self.practice_service.get_session(member_id, session["id"])
        self.assertEqual(
            [item["id"] for item in reopened["questions"]], [q["id"]],
            "移动题不得让其他成员进行中的练习丢失题目",
        )
        self.assertEqual(reopened["questions"][0]["bank_id"], source)

        attempt = self.practice_service.submit_attempt(member_id, session["id"], q["id"], "A")
        self.assertEqual(attempt["correctness"], "CORRECT")
        report = self.practice_service.complete_session(member_id, session["id"])
        self.assertEqual(report["answered_count"], 1)

        with sqlite3.connect(self.db_path) as conn:
            attribution = conn.execute(
                "SELECT bank_id FROM answer_attempts WHERE id = ?", (attempt["id"],)
            ).fetchone()[0]
            learning = conn.execute(
                "SELECT COUNT(*) FROM learning_records WHERE user_id = ? AND question_id = ?",
                (member_id, q["id"]),
            ).fetchone()[0]
        self.assertEqual(attribution, source, "历史作答必须归属作答时所在题库")
        self.assertEqual(learning, 1, "移动题不得删除成员真实学习记录")

        # The member's historical statistics still belong to the source bank.
        self.assertEqual(self.practices.summary(member_id)["attempts"], 1)
        self.assertEqual(self.practices.trends(member_id, source)["recent"]["attempts"], 1)
        self.assertEqual(self.practices.trends(member_id, target)["recent"]["attempts"], 0)

    def test_move_into_a_shared_target_keeps_attempts_in_the_practice_bank_context(self):
        admin_id = self.auth.register("shared_admin", "Password123")["id"]
        member_id = self.auth.register("shared_member", "Password123")["id"]
        source = self.bank_service.create_bank(admin_id, {"name": "Shared source"})["id"]
        target = self.bank_service.create_bank(admin_id, {"name": "Shared target"})["id"]
        self.banks.add_member(source, admin_id, "shared_member", "MEMBER")
        self.banks.add_member(target, admin_id, "shared_member", "MEMBER")

        q = self._question(bank_id=source, stem="Shared move", owner_id=admin_id)
        session = self.practice_service.start_session(
            member_id, source, mode="PRACTICE", question_ids=[q["id"]],
        )
        self.bank_service.batch_questions(
            admin_id, source,
            {"question_ids": [q["id"]], "operation": "move", "target_bank_id": target},
        )

        attempt = self.practice_service.submit_attempt(member_id, session["id"], q["id"], "B")
        with sqlite3.connect(self.db_path) as conn:
            bank_id = conn.execute(
                "SELECT bank_id FROM answer_attempts WHERE id = ?", (attempt["id"],)
            ).fetchone()[0]
        self.assertEqual(bank_id, source, "即使成员也在目标库，历史作答仍归属原练习上下文")


class AttemptIdempotencyTests(_Base):
    """Response-loss retries and offline replays must collapse into one attempt."""

    def _attempt_rows(self, session_id, question_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(
                "SELECT id, user_answer_json, correctness, fsrs_rating FROM answer_attempts "
                "WHERE session_id = ? AND question_id = ? ORDER BY created_at ASC, rowid ASC",
                (session_id, question_id),
            ).fetchall()]

    def test_equivalent_multi_answer_replay_is_a_single_attempt(self):
        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "Multi order",
            "type": "MULTI",
            "options": [{"key": "A", "content": "a"}, {"key": "B", "content": "b"}, {"key": "C", "content": "c"}],
            "answer": "A,B",
        })
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )

        first = self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], ["A", "B"])
        retry = self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], ["B", "A"])

        self.assertEqual(first["id"], retry["id"])
        self.assertTrue(retry["duplicate"])
        self.assertTrue(retry["idempotent_replay"])
        self.assertEqual(len(self._attempt_rows(session["id"], q["id"])), 1)

    def test_identical_retry_does_not_double_count_mistakes_or_events(self):
        q = self._question()
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")

        with sqlite3.connect(self.db_path) as conn:
            attempts = conn.execute(
                "SELECT COUNT(*) FROM answer_attempts WHERE session_id = ? AND question_id = ?",
                (session["id"], q["id"]),
            ).fetchone()[0]
            mistakes = conn.execute(
                "SELECT mistake_count FROM learning_records WHERE user_id = ? AND question_id = ?",
                (self.user_id, q["id"]),
            ).fetchone()[0]
            events = conn.execute(
                "SELECT COUNT(*) FROM learning_events WHERE user_id = ? AND event_type = 'ANSWER_ATTEMPTED' AND aggregate_id = ?",
                (self.user_id, q["id"]),
            ).fetchone()[0]
        self.assertEqual(attempts, 1)
        self.assertEqual(mistakes, 1)
        self.assertEqual(events, 1, "重试不得重复追加作答事件")

    def test_stale_offline_replay_does_not_roll_back_a_newer_answer(self):
        q = self._question()
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )
        # An offline replay is only expressible when the client carries a stable
        # attempt key: without one, an identical answer after a different one is
        # a legitimate A→B→A edit, not a replay (see the unkeyed tests below).
        stale = self.practice_service.submit_attempt(
            self.user_id, session["id"], q["id"], "B", client_attempt_id="offline-stale",
        )
        newer = self.practice_service.submit_attempt(
            self.user_id, session["id"], q["id"], "A", client_attempt_id="online-newer",
        )
        self.assertEqual(newer["correctness"], "CORRECT")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            learning_before = dict(conn.execute(
                "SELECT mistake_count, consecutive_correct, mastery_status FROM learning_records "
                "WHERE user_id = ? AND question_id = ?", (self.user_id, q["id"]),
            ).fetchone())
            card_before = dict(conn.execute(
                "SELECT state, stability, difficulty, due_at FROM fsrs_cards WHERE user_id = ? AND question_id = ?",
                (self.user_id, q["id"]),
            ).fetchone())

        replay = self.practice_service.submit_attempt(
            self.user_id, session["id"], q["id"], "B", client_attempt_id="offline-stale",
        )

        self.assertEqual(replay["id"], newer["id"], "过期重放应返回服务端最新状态")
        self.assertEqual(replay["replayed_attempt_id"], stale["id"])
        self.assertEqual(replay["correctness"], "CORRECT")
        rows = self._attempt_rows(session["id"], q["id"])
        self.assertEqual(len(rows), 2, "过期重放不得插入第三条作答")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            learning_after = dict(conn.execute(
                "SELECT mistake_count, consecutive_correct, mastery_status FROM learning_records "
                "WHERE user_id = ? AND question_id = ?", (self.user_id, q["id"]),
            ).fetchone())
            card_after = dict(conn.execute(
                "SELECT state, stability, difficulty, due_at FROM fsrs_cards WHERE user_id = ? AND question_id = ?",
                (self.user_id, q["id"]),
            ).fetchone())
        self.assertEqual(learning_after, learning_before, "过期重放不得回滚学习记录")
        self.assertEqual(card_after, card_before, "过期重放不得回滚 FSRS 卡片")

    def test_client_attempt_key_collapses_a_retry_even_when_the_payload_changed(self):
        q = self._question()
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )
        first = self.practice_service.submit_attempt(
            self.user_id, session["id"], q["id"], "A", client_attempt_id="offline-123",
        )
        retry = self.practice_service.submit_attempt(
            self.user_id, session["id"], q["id"], "B", client_attempt_id="offline-123",
        )

        self.assertEqual(first["id"], retry["id"], "同一客户端幂等键必须映射到同一条作答")
        self.assertTrue(retry["duplicate"])
        rows = self._attempt_rows(session["id"], q["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0]["user_answer_json"]), "A", "幂等键重放应返回首次结果")

    def test_concurrent_identical_attempts_collapse_to_one_row(self):
        import concurrent.futures

        q = self._question()
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )

        def submit(_):
            return self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "A")["id"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(submit, range(8)))

        self.assertEqual(len(set(ids)), 1, "并发重试必须收敛到同一条作答")
        self.assertEqual(len(self._attempt_rows(session["id"], q["id"])), 1)

    def test_concurrent_same_client_key_collapse_to_one_row(self):
        import concurrent.futures

        q = self._question()
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )

        def submit(_):
            return self.practice_service.submit_attempt(
                self.user_id, session["id"], q["id"], "A", client_attempt_id="offline-race",
            )["id"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(submit, range(8)))

        self.assertEqual(len(set(ids)), 1, "同一幂等键的并发重试必须收敛到同一条作答")
        rows = self._attempt_rows(session["id"], q["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], ids[0])

    def test_unkeyed_answer_reverted_after_a_different_answer_is_a_new_attempt(self):
        """A→B→A is three real answers, not a historical-answer replay.

        The legacy client sends no attempt key. Deduplicating by canonical
        answer across the whole session used to swallow the third answer and
        return the middle (stale) result, so the user could never change back.
        """
        q = self._question(answer="A")
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )

        first = self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "A")
        middle = self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")
        third = self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "A")
        fourth = self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")

        rows = self._attempt_rows(session["id"], q["id"])
        self.assertEqual(
            [json.loads(row["user_answer_json"]) for row in rows], ["A", "B", "A", "B"],
            "无键旧客户端连续改答案必须逐次落库，不得被历史答案去重吞掉",
        )
        self.assertEqual(len({first["id"], middle["id"], third["id"], fourth["id"]}), 4)
        self.assertEqual(rows[-1]["id"], fourth["id"])
        self.assertEqual(third["correctness"], "CORRECT", "第三次作答必须按 A 计算最新结果")
        self.assertFalse(third["duplicate"])
        self.assertFalse(third["idempotent_replay"])
        self.assertEqual(third["fsrs_rating"], 3, "改回正确答案后必须按真实历史重新评级")
        self.assertEqual(fourth["correctness"], "INCORRECT")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            learning = dict(conn.execute(
                "SELECT mistake_count, consecutive_correct FROM learning_records "
                "WHERE user_id = ? AND question_id = ?", (self.user_id, q["id"]),
            ).fetchone())
            card = conn.execute(
                "SELECT last_review_at FROM fsrs_cards WHERE user_id = ? AND question_id = ?",
                (self.user_id, q["id"]),
            ).fetchone()
            third_row = conn.execute(
                "SELECT card_snapshot_json FROM answer_attempts WHERE id = ?", (third["id"],),
            ).fetchone()
        self.assertEqual(learning, {"mistake_count": 2, "consecutive_correct": 0},
                         "学习记录必须反映最后一次真实作答")
        self.assertIsNotNone(card["last_review_at"], "每次真实作答都必须参与 FSRS 调度")
        snapshot = json.loads(third_row["card_snapshot_json"])
        self.assertIsNotNone(snapshot["last_review_at"],
                             "改回答案的 FSRS 必须从作答前快照出发，而不是历史重放")

    def test_unkeyed_consecutive_retry_stays_idempotent_after_a_switch(self):
        """Consecutive identical retries still collapse, even after an A→B→A switch."""
        q = self._question(answer="A")
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )
        self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")
        switched = self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "A")
        retry = self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "A")

        self.assertTrue(retry["duplicate"], "切换后的连续重试仍应识别为同一作答")
        self.assertTrue(retry["idempotent_replay"])
        self.assertEqual(retry["id"], switched["id"])
        rows = self._attempt_rows(session["id"], q["id"])
        self.assertEqual([json.loads(row["user_answer_json"]) for row in rows], ["B", "A"])

    def test_distinct_client_keys_keep_a_b_a_as_three_attempts(self):
        q = self._question(answer="A")
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )
        first = self.practice_service.submit_attempt(
            self.user_id, session["id"], q["id"], "A", client_attempt_id="a-1",
        )
        middle = self.practice_service.submit_attempt(
            self.user_id, session["id"], q["id"], "B", client_attempt_id="b-1",
        )
        third = self.practice_service.submit_attempt(
            self.user_id, session["id"], q["id"], "A", client_attempt_id="a-2",
        )

        rows = self._attempt_rows(session["id"], q["id"])
        self.assertEqual([json.loads(row["user_answer_json"]) for row in rows], ["A", "B", "A"])
        self.assertEqual(len({first["id"], middle["id"], third["id"]}), 3)
        self.assertEqual(third["correctness"], "CORRECT", "不同幂等键必须产生新的最新结果")
        self.assertFalse(third["duplicate"])


    def test_client_attempt_id_validation(self):
        q = self._question()
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]],
        )
        with self.assertRaises(ValueError):
            self.practice_service.submit_attempt(
                self.user_id, session["id"], q["id"], "A", client_attempt_id="   ",
            )
        with self.assertRaises(ValueError):
            self.practice_service.submit_attempt(
                self.user_id, session["id"], q["id"], "A", client_attempt_id="x" * 201,
            )


class ExamTimeoutRecoveryTests(_Base):
    def _expired_exam(self, answer="A", limit=1):
        q = self._question(stem="Timed exam")
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="EXAM", total_questions=1,
            time_limit=limit, question_ids=[q["id"]],
        )
        if answer is not None:
            self.practice_service.sync_draft(
                self.user_id, session["id"], {"answers": {q["id"]: answer}, "time_spent": 5},
            )
        return q, session

    def _age_session(self, session_id, seconds):
        from datetime import datetime, timedelta, timezone
        created = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE practice_sessions SET created_at = ? WHERE id = ?", (created, session_id))

    def test_late_draft_is_rejected_with_a_stable_terminal_code(self):
        from backend.app.application.practice_service import ExamTimeExpiredError

        q, session = self._expired_exam(answer="A")
        self._age_session(session["id"], 10 * 60)

        with self.assertRaises(ExamTimeExpiredError) as ctx:
            self.practice_service.sync_draft(
                self.user_id, session["id"], {"answers": {q["id"]: "B"}},
            )
        self.assertEqual(ctx.exception.code, "EXAM_TIME_EXPIRED")
        self.assertIn("EXAM_TIME_EXPIRED", str(ctx.exception))

        reopened = self.practice_service.get_session(self.user_id, session["id"])
        self.assertTrue(reopened["is_expired"])
        self.assertFalse(reopened["is_completed"], "读取不能静默替用户交卷")
        self.assertEqual(reopened["answers"][q["id"]], "A", "迟到的本机答案不得被静默采用")

    def test_late_attempt_is_rejected_with_the_same_code(self):
        from backend.app.application.practice_service import ExamTimeExpiredError

        q, session = self._expired_exam(answer="A")
        self._age_session(session["id"], 10 * 60)
        with self.assertRaises(ExamTimeExpiredError):
            self.practice_service.submit_attempt(self.user_id, session["id"], q["id"], "B")

    def test_late_attempt_with_a_client_key_is_still_terminal(self):
        from backend.app.application.practice_service import ExamTimeExpiredError

        q, session = self._expired_exam(answer="A")
        self._age_session(session["id"], 10 * 60)
        with self.assertRaises(ExamTimeExpiredError):
            self.practice_service.submit_attempt(
                self.user_id, session["id"], q["id"], "B", client_attempt_id="offline-late",
            )

        with sqlite3.connect(self.db_path) as conn:
            attempts = conn.execute(
                "SELECT COUNT(*) FROM answer_attempts WHERE session_id = ? AND question_id = ?",
                (session["id"], q["id"]),
            ).fetchone()[0]
        self.assertEqual(attempts, 0, "超时后即使带幂等键也不得落库")


    def test_expired_exam_can_still_be_completed_from_server_state(self):
        q, session = self._expired_exam(answer="A")
        self._age_session(session["id"], 10 * 60)

        report = self.practice_service.complete_session(self.user_id, session["id"])
        self.assertTrue(report["is_completed"])
        self.assertEqual(report["answered_count"], 1)
        self.assertEqual(report["correct_count"], 1, "交卷只使用截止前已同步到服务端的答案")
        self.assertEqual(report["answers"][q["id"]]["user_answer"], "A")

        again = self.practice_service.complete_session(self.user_id, session["id"])
        self.assertEqual(again["score"], report["score"], "超时后的交卷必须保持幂等")

    def test_grace_window_at_the_boundary_remains_unchanged(self):
        q, session = self._expired_exam(answer="A")
        # 1 minute limit: 90s elapsed is past the limit but inside the existing
        # 60s grace, so it must still be accepted (the deadline is not extended
        # beyond the documented grace, nor shortened).
        self._age_session(session["id"], 90)
        saved = self.practice_service.sync_draft(
            self.user_id, session["id"], {"answers": {q["id"]: "B"}},
        )
        self.assertEqual(saved["answers"][q["id"]], "B")

        self._age_session(session["id"], 60 + 61)
        with self.assertRaises(ValueError):
            self.practice_service.sync_draft(
                self.user_id, session["id"], {"answers": {q["id"]: "A"}},
            )


if __name__ == "__main__":
    unittest.main()
