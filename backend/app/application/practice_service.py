from backend.app.domain.learning.scoring import score_answer


class PracticeService:
    def __init__(self, practices, questions, banks=None, exams=None):
        self.practices = practices
        self.questions = questions
        self.banks = banks
        self.exams = exams

    def start_session(
        self,
        user_id: str,
        bank_id: str,
        mode: str = "PRACTICE",
        total_questions: int = 0,
        time_limit: int = 0,
        exam_profile_id: str | None = None,
        blueprint_id: str | None = None,
        question_ids: list[str] | None = None,
        config: dict | None = None,
        record_mistakes: bool | None = None,
    ) -> dict:
        if self.banks and not self.banks.get_for_user(bank_id, user_id):
            raise LookupError("question bank not found")
        if mode == "ELIMINATION":
            candidate_questions = self.questions.list_for_elimination(bank_id, user_id)
        elif mode == "MISTAKE":
            mistakes = self.practices.list_mistakes(user_id, bank_id)
            mistake_qids = {m["question_id"] for m in mistakes if not m.get("is_cleared")}
            candidate_questions = [q for q in self.questions.list_for_bank(bank_id, user_id) if q["id"] in mistake_qids]
        elif mode == "FSRS":
            dues = self.practices.list_due_reviews(user_id, bank_id)
            due_qids = {d["question_id"] for d in dues}
            candidate_questions = [q for q in self.questions.list_for_bank(bank_id, user_id) if q["id"] in due_qids]
        else:
            candidate_questions = self.questions.list_for_bank(bank_id, user_id)

        # EE-001: Dynamic exam blueprint assembly and section-based question selection
        if blueprint_id and self.exams:
            saved_bp = self.exams.get_blueprint(user_id, blueprint_id)
            if saved_bp and saved_bp.get("blueprint"):
                from backend.app.domain.exams.blueprint import select_questions_by_blueprint
                candidate_questions = select_questions_by_blueprint(candidate_questions, saved_bp["blueprint"], total_questions)

        if question_ids is not None:
            allowed_map = {q["id"]: q for q in candidate_questions}
            questions = [allowed_map[qid] for qid in question_ids if qid in allowed_map]
        else:
            questions = candidate_questions

        if not questions and (mode in ("MISTAKE", "FSRS", "ELIMINATION") or question_ids is not None):
            raise ValueError(f"当前题库没有符合条件的题目")

        selected = questions if blueprint_id else (questions[:total_questions] if total_questions > 0 else questions)
        question_refs = [{"question_id": item["id"], "version_id": item["version_id"]} for item in selected]

        session_config = dict(config or {})
        if record_mistakes is not None:
            session_config["record_mistakes"] = record_mistakes

        return self.practices.create_session(
            user_id, bank_id, mode, len(selected), time_limit, exam_profile_id, blueprint_id, question_refs,
            config=session_config,
        )

    def list_active_sessions(self, user_id: str, mode: str | None = None) -> list[dict]:
        import json
        raw = self.practices.list_active_sessions(user_id, mode)
        sessions = []
        for s in raw:
            answers = json.loads(s.get("answers_json") or "{}")
            questions = json.loads(s.get("questions_json") or "[]")
            bank = self.banks.get_for_user(s["bank_id"], user_id) if self.banks else None
            sessions.append({
                "id": s["id"],
                "bank_id": s["bank_id"],
                "bank_name": bank.get("name") if bank else "未知题库",
                "mode": s["mode"],
                "total_questions": s["total_questions"] or len(questions),
                "answered_count": len(answers),
                "time_spent": s.get("time_spent", 0),
                "time_limit": s.get("time_limit", 0),
                "current_index": s.get("current_index", 0),
                "created_at": s.get("created_at"),
                "updated_at": s.get("updated_at"),
            })
        return sessions

    def abandon_session(self, user_id: str, session_id: str) -> dict:
        success = self.practices.abandon_session(session_id, user_id)
        if not success:
            raise LookupError("practice session not found or already completed")
        return {"status": "abandoned", "session_id": session_id}

    def abandon_all_sessions(self, user_id: str) -> dict:
        count = self.practices.abandon_all_sessions(user_id)
        return {"status": "abandoned_all", "count": count}

    def _check_exam_timeout(self, session: dict):
        if session.get("mode") == "EXAM" and int(session.get("time_limit") or 0) > 0:
            created_at_str = session.get("created_at")
            if created_at_str:
                from datetime import datetime, timezone
                try:
                    created_dt = datetime.fromisoformat(str(created_at_str).replace("Z", "+00:00"))
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    now_dt = datetime.now(timezone.utc)
                    elapsed_sec = (now_dt - created_dt).total_seconds()
                    limit_sec = int(session["time_limit"]) * 60
                    if elapsed_sec > limit_sec + 60:
                        raise ValueError("模考时间已到，已超时，请交卷")
                except ValueError:
                    raise
                except Exception:
                    pass

    def submit_attempt(
        self,
        user_id: str,
        session_id: str,
        question_id: str,
        user_answer,
        fsrs_rating: int | None = None,
        mistake_cause: str | None = None,
    ):
        session = self.practices.get_session(session_id, user_id)
        if not session:
            raise LookupError("practice session not found")
        if session.get("is_completed"):
            raise ValueError("session already completed")
        self._check_exam_timeout(session)
        snapshot = __import__("json").loads(session.get("questions_json") or "[]")
        version_ref = next((item for item in snapshot if item["question_id"] == question_id), None)
        if not version_ref:
            raise LookupError("question not in this session")
        question = self.questions.get_version_for_user(question_id, version_ref["version_id"], user_id)
        if not question or question["bank_id"] != session["bank_id"]:
            raise LookupError("question not found in session bank")
        result = score_answer(question["type"], user_answer, question["answer"])
        if fsrs_rating is not None:
            if fsrs_rating not in {1, 2, 3, 4}:
                raise ValueError("rating must be Again(1), Hard(2), Good(3), or Easy(4)")
            if result["correctness"] == "INCORRECT" and fsrs_rating != 1:
                raise ValueError("答错时 FSRS 评级必须为 Again(1)")
            if result["correctness"] == "PARTIAL" and fsrs_rating > 2:
                raise ValueError("部分得分最多只能选择 Hard(2)")
        saved = self.practices.save_attempt(user_id, session, question, user_answer, result, fsrs_rating, mistake_cause)
        if session["mode"] == "EXAM":
            return {
                "id": saved["id"],
                "session_id": session_id,
                "question_id": question_id,
                "user_answer": user_answer,
                "feedback_available": False,
            }
        return {**saved, "feedback_available": True}

    def review_answer(self, user_id: str, question_id: str, user_answer, rating: int, mistake_cause: str | None = None) -> dict:
        if rating not in {1, 2, 3, 4}:
            raise ValueError("rating must be Again(1), Hard(2), Good(3), or Easy(4)")
        question = self.questions.get_for_user(question_id, user_id)
        if not question:
            raise LookupError("question not found")
        result = score_answer(question["type"], user_answer, question["answer"])
        if result["correctness"] == "INCORRECT" and rating != 1:
            raise ValueError("答错时 FSRS 评级必须为 Again(1)")
        if result["correctness"] == "PARTIAL" and rating > 2:
            raise ValueError("部分得分最多只能选择 Hard(2)")
        session = self.practices.create_session(
            user_id,
            question["bank_id"],
            "FSRS",
            1,
            question_refs=[{"question_id": question["id"], "version_id": question["version_id"]}],
        )
        attempt_res = self.submit_attempt(user_id, session["id"], question_id, user_answer, rating, mistake_cause)
        self.complete_session(user_id, session["id"])
        return attempt_res

    def update_mistake_cause(self, user_id: str, question_id: str, mistake_cause: str) -> dict:
        return self.practices.update_mistake_cause(user_id, question_id, mistake_cause)

    def get_session(self, user_id: str, session_id: str) -> dict:
        session = self.practices.get_session(session_id, user_id)
        if not session:
            raise LookupError("practice session not found")
        session["answers"] = __import__("json").loads(session.get("answers_json") or "{}")
        session["flags"] = __import__("json").loads(session.get("flags_json") or "[]")
        session["is_completed"] = bool(session.get("is_completed"))
        snapshot = __import__("json").loads(session.get("questions_json") or "[]")
        session.pop("user_id", None)
        session.pop("answers_json", None)
        session.pop("flags_json", None)
        session.pop("questions_json", None)
        session["questions"] = self.questions.list_for_snapshot(snapshot, user_id)
        session["question_ids"] = [q["id"] for q in session["questions"]]
        if session["mode"] == "EXAM" and not session["is_completed"]:
            for question in session["questions"]:
                question.pop("answer", None)
                question.pop("explanation", None)
            session["answers"] = {
                question_id: (
                    {key: value for key, value in answer.items() if key in {"answer", "user_answer"}}
                    if isinstance(answer, dict)
                    else answer
                )
                for question_id, answer in session["answers"].items()
            }
        return session

    def sync_draft(self, user_id: str, session_id: str, payload: dict) -> dict:
        sess = self.practices.get_session(session_id, user_id)
        if sess:
            self._check_exam_timeout(sess)
        updated = self.practices.update_draft(user_id, session_id, payload.get("current_index"), payload.get("answers"), payload.get("flags"), payload.get("time_spent"))
        if not updated:
            raise LookupError("practice session not found")
        session = self.get_session(user_id, session_id)
        session["has_conflict"] = updated.get("has_conflict", False)
        session["conflicts"] = updated.get("conflicts", [])
        return session

    def toggle_flag(self, user_id: str, session_id: str, question_id: str) -> list[str]:
        sess = self.practices.get_session(session_id, user_id)
        if sess:
            self._check_exam_timeout(sess)
        flags = self.practices.toggle_flag(user_id, session_id, question_id)
        if flags is None:
            raise LookupError("practice session not found")
        return flags

    def complete_session(self, user_id: str, session_id: str) -> dict:
        session = self.practices.complete(user_id, session_id)
        if not session:
            raise LookupError("practice session not found")
        attempts = self.practices.list_attempts(user_id, session_id)
        latest = {}
        for attempt in attempts:
            latest[attempt["question_id"]] = attempt
        attempts = list(latest.values())
        blueprint = None
        if session["mode"] == "EXAM" and session.get("blueprint_id") and self.exams:
            saved_blueprint = self.exams.get_blueprint(user_id, session["blueprint_id"])
            blueprint = saved_blueprint.get("blueprint") if saved_blueprint else None
        if session["mode"] == "EXAM":
            from backend.app.domain.exams.grading import grade_report
            total_score = grade_report(attempts, blueprint)
        else:
            total_score = round(sum(float(value.get("score_ratio") or 0) for value in attempts), 2)
        correct_count = sum(1 for value in attempts if value.get("correctness") == "CORRECT")
        partial_count = sum(1 for value in attempts if value.get("correctness") == "PARTIAL")
        incorrect_count = sum(1 for value in attempts if value.get("correctness") == "INCORRECT")
        unanswered_count = max(0, int(session["total_questions"]) - len(attempts))
        type_stats = {}
        tag_stats = {}
        for attempt in attempts:
            bucket = type_stats.setdefault(attempt["type"], {"attempted": 0, "correct": 0, "partial": 0, "incorrect": 0})
            bucket["attempted"] += 1
            status = attempt["correctness"].lower()
            if status in bucket:
                bucket[status] += 1
            for tag in attempt.get("tags", []):
                tag_bucket = tag_stats.setdefault(tag, {"attempted": 0, "correct": 0, "partial": 0, "incorrect": 0})
                tag_bucket["attempted"] += 1
                if status in tag_bucket:
                    tag_bucket[status] += 1
        answers = {
            item["question_id"]: {
                "user_answer": item["user_answer"],
                "correct_answer": item["correct_answer"],
                "score_ratio": item["score_ratio"],
                "correctness": item["correctness"],
                "mastery_status": item["mastery_status"],
                "explanation": item["explanation"],
            }
            for item in attempts
        }
        snapshot = __import__("json").loads(session.get("questions_json") or "[]")
        questions_in_session = self.questions.list_for_snapshot(snapshot, user_id) if hasattr(self.questions, "list_for_snapshot") else []
        if questions_in_session:
            objective_total = sum(1 for q in questions_in_session if str(q.get("type", "SINGLE")).upper() not in {"ESSAY", "SHORT_ANSWER", "SUBJECTIVE"})
        else:
            subjective_attempts = sum(1 for a in attempts if str(a.get("type", "SINGLE")).upper() in {"ESSAY", "SHORT_ANSWER", "SUBJECTIVE"})
            objective_total = max(0, int(session.get("total_questions", 0)) - subjective_attempts)

        accuracy = round(correct_count / max(1, objective_total) * 100, 2) if objective_total > 0 else 0.0
        return {
            "session_id": session_id,
            "bank_id": session["bank_id"],
            "mode": session["mode"],
            "exam_profile_id": session.get("exam_profile_id"),
            "blueprint_id": session.get("blueprint_id"),
            "is_completed": True,
            "total_questions": session["total_questions"],
            "objective_total": objective_total,
            "answered_count": len(answers),
            "correct_count": correct_count,
            "partial_count": partial_count,
            "incorrect_count": incorrect_count,
            "unanswered_count": unanswered_count,
            "score": total_score,
            "accuracy": accuracy,
            "type_stats": type_stats,
            "tag_stats": tag_stats,
            "answers": answers,
        }
