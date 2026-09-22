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

    def start_session(
        self,
        bank_id: str,
        mode: Union[str, SessionMode],
        total_questions: int,
        time_limit: int = 0,
    ) -> Dict[str, Any]:
        """Start a new practice or exam session and return the initial session dictionary."""
        session_id = self.session_repo.create_session(
            bank_id=bank_id,
            mode=mode,
            total_questions=total_questions,
            time_limit=time_limit,
        )
        session = self.session_repo.get_session(session_id)
        if not session:
            raise RuntimeError(f"Failed to create session for bank {bank_id}")

        session["answers"] = json.loads(session.get("answers_json") or "{}")
        session["flags"] = json.loads(session.get("flags_json") or "[]")
        session["is_completed"] = bool(session.get("is_completed", 0))
        return session

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session with deserialized answers and flags."""
        session = self.session_repo.get_session(session_id)
        if not session:
            return None
        session["answers"] = json.loads(session.get("answers_json") or "{}")
        session["flags"] = json.loads(session.get("flags_json") or "[]")
        session["is_completed"] = bool(session.get("is_completed", 0))
        return session

    def submit_answer(
        self,
        session_id: str,
        question_id: str,
        user_answer: Any,
        time_spent_delta: int = 0,
        mistake_cause: Optional[Union[str, MistakeCause]] = None,
    ) -> Dict[str, Any]:
        """Submit and evaluate an answer for a question in a session.

        - Instant scoring via Scorer
        - Persists answer into session repository
        - If mode in (PRACTICE, ELIMINATION, FSRS) and mistake_service is provided, records mistake / success
        - Returns evaluation result including is_correct, score_ratio, correct_answer, explanation
        """
        session = self.session_repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        q_type = "SINGLE"
        correct_answer = ""
        explanation = ""

        if self.question_repo is not None:
            q = self.question_repo.get_question(question_id)
            if q:
                q_type = q.get("type", "SINGLE")
                correct_answer = q.get("answer", "")
                explanation = q.get("explanation", "")

        is_correct, score_ratio = Scorer.evaluate(q_type, user_answer, correct_answer)

        answers = json.loads(session.get("answers_json") or "{}")
        flags = json.loads(session.get("flags_json") or "[]")

        answers[question_id] = {
            "answer": user_answer,
            "user_answer": user_answer,
            "is_correct": is_correct,
            "score_ratio": score_ratio,
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
        if mode_str in ("PRACTICE", "ELIMINATION", "FSRS") and self.mistake_service is not None:
            bank_id = session.get("bank_id", "")
            self.mistake_service.record_question_result(
                question_id=question_id,
                bank_id=bank_id,
                is_correct=is_correct,
                cause=mistake_cause,
            )

        return {
            "session_id": session_id,
            "question_id": question_id,
            "user_answer": user_answer,
            "is_correct": is_correct,
            "score_ratio": score_ratio,
            "correct_answer": correct_answer,
            "explanation": explanation,
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

        for qid, ans_val in answers.items():
            if isinstance(ans_val, dict) and "score_ratio" in ans_val:
                s_ratio = float(ans_val.get("score_ratio", 0.0))
                is_cor = bool(ans_val.get("is_correct", False))
            else:
                user_ans = (
                    ans_val
                    if isinstance(ans_val, str)
                    else (ans_val.get("answer") or ans_val.get("user_answer") or "")
                )
                if self.question_repo:
                    q = self.question_repo.get_question(qid)
                    if q:
                        is_cor, s_ratio = Scorer.evaluate(
                            q.get("type", "SINGLE"), user_ans, q.get("answer", "")
                        )
                    else:
                        is_cor, s_ratio = False, 0.0
                else:
                    is_cor, s_ratio = False, 0.0

            total_score += s_ratio
            if is_cor:
                correct_count += 1

        final_score = round(total_score, 2)
        self.session_repo.complete_session(session_id, score=final_score)

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
            "correct_count": correct_count,
            "score": final_score,
            "accuracy": accuracy,
            "time_spent": updated.get("time_spent", 0),
            "answers": answers,
            "flags": flags,
            "session": updated,
        }
