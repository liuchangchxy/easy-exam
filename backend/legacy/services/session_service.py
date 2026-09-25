"""Session service managing examination and practice lifecycles, draft syncing, and answer scoring."""
import json
from typing import Any, Dict, List, Optional, Union

from backend.models import MistakeCause, SessionMode
from backend.repositories import QuestionRepository, SessionRepository
from backend.services.mistake_service import MistakeService
from backend.services.scoring import Scorer


class SessionService:
    """Service handling practice and exam sessions, answer submission, and client draft synchronization."""

    def __init__(
        self,
        session_repo: SessionRepository,
        question_repo: Optional[QuestionRepository] = None,
        mistake_service: Optional[MistakeService] = None,
    ):
        self.session_repo = session_repo
        self.question_repo = question_repo
        self.mistake_service = mistake_service

    @staticmethod
    def shuffle_question_options(question: Dict[str, Any]) -> Dict[str, Any]:
        """Shuffle options of a single/multi choice question and remap correct answer."""
        import random
        import re
        q_type = str(question.get("type", "")).upper()
        if q_type not in ("SINGLE", "MULTI"):
            return dict(question)

        raw_options = question.get("options") or []
        if len(raw_options) <= 1:
            return dict(question)

        # Normalize options format: [(key, content)]
        options_list = []
        for idx, opt in enumerate(raw_options):
            if isinstance(opt, dict):
                k = str(opt.get("key", chr(65 + idx))).upper().strip()
                c = opt.get("content", opt.get("text", ""))
            else:
                k = chr(65 + idx)
                c = str(opt)
            options_list.append((k, c))

        old_answer = str(question.get("answer", "")).upper().strip()
        old_correct_keys = set(re.findall(r'[A-H]', old_answer)) if old_answer else set()

        # Find the contents that correspond to correct keys
        correct_contents = set()
        for k, c in options_list:
            if k in old_correct_keys:
                correct_contents.add(c)

        # Shuffle the option contents
        shuffled_contents = [c for _, c in options_list]
        random.shuffle(shuffled_contents)

        # Re-assign keys A, B, C, D...
        new_options = []
        new_correct_keys = []
        for idx, c in enumerate(shuffled_contents):
            new_k = chr(65 + idx)
            new_options.append({"key": new_k, "content": c})
            if c in correct_contents:
                new_correct_keys.append(new_k)

        new_correct_keys.sort()
        new_answer = "".join(new_correct_keys) if new_correct_keys else old_answer

        shuffled_q = dict(question)
        shuffled_q["options"] = new_options
        shuffled_q["answer"] = new_answer
        shuffled_q["original_answer"] = old_answer
        return shuffled_q

    def start_session(
        self,
        bank_id: str,
        mode: Union[str, SessionMode],
        total_questions: int = 0,
        time_limit: int = 0,
        shuffle_questions: bool = False,
        shuffle_options: bool = False,
        mistake_cause: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a new practice or exam session with optional question/option shuffling."""
        import random
        questions = []
        if self.question_repo is not None:
            questions = list(self.question_repo.list_questions_by_bank(bank_id))
            mode_str = mode.value if hasattr(mode, "value") else str(mode).upper()

            if mode_str == "ELIMINATION" and self.mistake_service is not None and self.mistake_service.mistake_repo is not None:
                mistakes = self.mistake_service.mistake_repo.get_mistakes(bank_id=bank_id, only_uncleared=True)
                if mistake_cause:
                    mistakes = [m for m in mistakes if m.get("mistake_cause") == mistake_cause]
                mistake_qids = {m["question_id"] for m in mistakes}
                if mistake_qids:
                    questions = [q for q in questions if q.get("id") in mistake_qids]
            elif mode_str == "FSRS" and self.mistake_service is not None:
                dues = self.mistake_service.get_due_reviews(bank_id)
                due_qids = {m["question_id"] for m in dues}
                if due_qids:
                    questions = [q for q in questions if q.get("id") in due_qids]

            if shuffle_questions and questions:
                random.shuffle(questions)

            if total_questions > 0 and len(questions) > total_questions:
                questions = questions[:total_questions]

            if shuffle_options and questions:
                questions = [self.shuffle_question_options(q) for q in questions]

        questions_json = json.dumps(questions, ensure_ascii=False)
        total = len(questions) if questions else total_questions

        session_id = self.session_repo.create_session(
            bank_id=bank_id,
            mode=mode,
            total_questions=total,
            time_limit=time_limit,
            questions_json=questions_json,
            shuffle_questions=shuffle_questions,
            shuffle_options=shuffle_options,
        )
        session = self.session_repo.get_session(session_id)
        if not session:
            raise RuntimeError(f"Failed to create session for bank {bank_id}")

        session["answers"] = json.loads(session.get("answers_json") or "{}")
        session["flags"] = json.loads(session.get("flags_json") or "[]")
        session["is_completed"] = bool(session.get("is_completed", 0))
        session["questions"] = questions
        session["question_ids"] = [q["id"] for q in questions if isinstance(q, dict) and "id" in q]
        if mistake_cause:
            session["mistake_cause"] = mistake_cause
        return session

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session with deserialized answers, flags, and questions."""
        session = self.session_repo.get_session(session_id)
        if not session:
            return None
        session["answers"] = json.loads(session.get("answers_json") or "{}")
        session["flags"] = json.loads(session.get("flags_json") or "[]")
        session["is_completed"] = bool(session.get("is_completed", 0))
        qs = json.loads(session.get("questions_json") or "[]")
        session["questions"] = qs
        session["question_ids"] = [q["id"] for q in qs if isinstance(q, dict) and "id" in q]
        return session

    def submit_answer(
        self,
        session_id: str,
        question_id: str,
        user_answer: Any,
        time_spent_delta: int = 0,
        mistake_cause: Optional[Union[str, MistakeCause]] = None,
    ) -> Dict[str, Any]:
        """Submit and evaluate an answer for a question in a session."""
        session = self.session_repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        q_type = "SINGLE"
        correct_answer = ""
        explanation = ""

        session_qs = json.loads(session.get("questions_json") or "[]")
        matched_q = next((q for q in session_qs if isinstance(q, dict) and q.get("id") == question_id), None)

        if matched_q:
            q_type = matched_q.get("type", "SINGLE")
            correct_answer = matched_q.get("answer", "")
            explanation = matched_q.get("explanation", "")
        elif self.question_repo is not None:
            q = self.question_repo.get_question(question_id)
            if q:
                q_type = q.get("type", "SINGLE")
                correct_answer = q.get("answer", "")
                explanation = q.get("explanation", "")

        score_result = Scorer.result(q_type, user_answer, correct_answer)
        is_correct = bool(score_result["is_correct"])
        score_ratio = float(score_result["score_ratio"])
        mastery_status = score_result["mastery_status"]

        answers = json.loads(session.get("answers_json") or "{}")
        flags = json.loads(session.get("flags_json") or "[]")

        answers[question_id] = {
            "answer": user_answer,
            "user_answer": user_answer,
            "is_correct": is_correct,
            "score_ratio": score_ratio,
            "mastery_status": mastery_status,
            "correct_answer": correct_answer,
            "explanation": explanation,
        }

        new_time_spent = (session.get("time_spent") or 0) + max(0, time_spent_delta)

        self.session_repo.update_session_progress(
            session_id=session_id,
            current_index=session.get("current_index", 0),
            answers_json=json.dumps(answers, ensure_ascii=False),
            flags_json=json.dumps(flags, ensure_ascii=False),
            time_spent=new_time_spent,
        )

        mode_str = str(session.get("mode", "")).upper()
        mistake_res = None
        if mode_str in ("PRACTICE", "ELIMINATION", "FSRS") and self.mistake_service is not None:
            bank_id = session.get("bank_id", "")
            mistake_res = self.mistake_service.record_question_result(
                question_id=question_id,
                bank_id=bank_id,
                is_correct=is_correct,
                cause=mistake_cause,
            )

        is_cleared = bool(mistake_res.get("is_cleared", False)) if mistake_res else False
        consecutive_correct = mistake_res.get("consecutive_correct", 0) if mistake_res else 0

        return {
            "session_id": session_id,
            "question_id": question_id,
            "user_answer": user_answer,
            "is_correct": is_correct,
            "score_ratio": score_ratio,
            "mastery_status": mastery_status,
            "correct_answer": correct_answer,
            "explanation": explanation,
            "is_cleared": is_cleared,
            "consecutive_correct": consecutive_correct,
        }

    def sync_draft(
        self,
        session_id: str,
        current_index: Optional[Union[int, Dict[str, Any]]] = None,
        answers: Optional[Dict[str, Any]] = None,
        flags: Optional[List[str]] = None,
        time_spent: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Merge incremental draft from client localStorage into database session."""
        if isinstance(current_index, dict) and answers is None and flags is None and time_spent is None:
            draft = current_index
            current_index = draft.get("current_index")
            answers = draft.get("answers")
            flags = draft.get("flags")
            time_spent = draft.get("time_spent")

        session = self.session_repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        existing_answers = json.loads(session.get("answers_json") or "{}")
        if answers:
            existing_answers.update(answers)

        existing_flags = json.loads(session.get("flags_json") or "[]")
        if flags is not None:
            existing_flags = list(dict.fromkeys(flags))

        new_index = current_index if current_index is not None else session.get("current_index", 0)
        new_time_spent = time_spent if time_spent is not None else session.get("time_spent", 0)

        self.session_repo.update_session_progress(
            session_id=session_id,
            current_index=new_index,
            answers_json=json.dumps(existing_answers, ensure_ascii=False),
            flags_json=json.dumps(existing_flags, ensure_ascii=False),
            time_spent=new_time_spent,
        )

        updated = self.session_repo.get_session(session_id)
        if not updated:
            raise RuntimeError(f"Session '{session_id}' lost during sync.")

        updated["answers"] = json.loads(updated.get("answers_json") or "{}")
        updated["flags"] = json.loads(updated.get("flags_json") or "[]")
        updated["is_completed"] = bool(updated.get("is_completed", 0))
        return updated

    def sync_progress(self, session_id: str, draft_data: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for sync_draft taking a draft dictionary."""
        return self.sync_draft(session_id, current_index=draft_data)

    def toggle_flag(self, session_id: str, question_id: str) -> List[str]:
        """Toggle flag on question_id for a session and return the updated list of flags."""
        session = self.session_repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        flags = json.loads(session.get("flags_json") or "[]")
        if question_id in flags:
            flags.remove(question_id)
        else:
            flags.append(question_id)

        self.session_repo.update_session_progress(
            session_id=session_id,
            current_index=session.get("current_index", 0),
            answers_json=session.get("answers_json") or "{}",
            flags_json=json.dumps(flags, ensure_ascii=False),
            time_spent=session.get("time_spent", 0),
        )
        return flags

    def complete_session(self, session_id: str) -> Dict[str, Any]:
        """Compute score, correct count, accuracy, mark session completed, and return summary report."""
        session = self.session_repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        total_questions = session.get("total_questions", 0)
        answers = json.loads(session.get("answers_json") or "{}")

        total_score = 0.0
        correct_count = 0
        breakdown: Dict[str, Dict[str, Any]] = {}

        # Pre-fetch questions for bank to compute type breakdown
        bank_id = session.get("bank_id")
        bank_questions = self.question_repo.get_by_bank(bank_id) if (self.question_repo and bank_id) else []
        q_map = {q["id"]: q for q in bank_questions}

        # Initialize breakdown from bank questions if available
        for q in bank_questions:
            q_type = q.get("type", "SINGLE")
            if q_type not in breakdown:
                breakdown[q_type] = {"total": 0, "correct": 0, "score": 0.0}
            breakdown[q_type]["total"] += 1

        for qid, ans_val in answers.items():
            q = q_map.get(qid)
            if not q and self.question_repo:
                q = self.question_repo.get_question(qid)
            q_type = q.get("type", "SINGLE") if q else "SINGLE"

            if q_type not in breakdown:
                breakdown[q_type] = {"total": 1, "correct": 0, "score": 0.0}

            if isinstance(ans_val, dict) and "score_ratio" in ans_val:
                s_ratio = float(ans_val.get("score_ratio", 0.0))
                is_cor = bool(ans_val.get("is_correct", False))
            else:
                user_ans = (
                    ans_val
                    if isinstance(ans_val, str)
                    else (ans_val.get("answer") or ans_val.get("user_answer") or "")
                )
                if q:
                    is_cor, s_ratio = Scorer.evaluate(
                        q.get("type", "SINGLE"), user_ans, q.get("answer", "")
                    )
                else:
                    is_cor, s_ratio = False, 0.0

            total_score += s_ratio
            breakdown[q_type]["score"] = round(breakdown[q_type]["score"] + s_ratio, 2)
            if is_cor:
                correct_count += 1
                breakdown[q_type]["correct"] += 1

        final_score = round(total_score, 2)
        self.session_repo.complete_session(session_id, score=final_score)

        # Knowledge points (tags) breakdown
        tags_breakdown: Dict[str, Dict[str, Any]] = {}
        for qid, ans_val in answers.items():
            q = q_map.get(qid)
            if not q and self.question_repo:
                q = self.question_repo.get_question(qid)
            if q and q.get("tags"):
                raw_tags = q.get("tags")
                tag_list = raw_tags if isinstance(raw_tags, list) else [str(raw_tags)]
                is_cor = bool(ans_val.get("is_correct", False)) if isinstance(ans_val, dict) else False
                for t in tag_list:
                    t_str = str(t).strip()
                    if not t_str:
                        continue
                    if t_str not in tags_breakdown:
                        tags_breakdown[t_str] = {"total": 0, "correct": 0, "accuracy": 0.0}
                    tags_breakdown[t_str]["total"] += 1
                    if is_cor:
                        tags_breakdown[t_str]["correct"] += 1

        for t_info in tags_breakdown.values():
            t_info["accuracy"] = round((t_info["correct"] / max(1, t_info["total"])) * 100, 1)

        # Max score: total_questions * 1.0 (or at least final_score)
        max_possible_score = float(total_questions) if total_questions > 0 else max(final_score, 1.0)
        passing_score = round(max_possible_score * 0.6, 1)
        passed = final_score >= passing_score

        accuracy = (
            round((correct_count / total_questions * 100.0), 2)
            if total_questions > 0
            else 0.0
        )

        updated = self.session_repo.get_session(session_id)
        flags = json.loads(updated.get("flags_json") or "[]")

        return {
            "session_id": session_id,
            "bank_id": updated.get("bank_id"),
            "mode": updated.get("mode"),
            "is_completed": True,
            "total_questions": total_questions,
            "answered_count": len(answers),
            "answered_questions": len(answers),
            "correct_count": correct_count,
            "score": final_score,
            "total_score": round(max_possible_score, 1),
            "passing_score": passing_score,
            "passed": passed,
            "accuracy": accuracy,
            "breakdown": breakdown,
            "tags_breakdown": tags_breakdown,
            "time_spent": updated.get("time_spent", 0),
            "answers": answers,
            "flags": flags,
            "session": updated,
        }
