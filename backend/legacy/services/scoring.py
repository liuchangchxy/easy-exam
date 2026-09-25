"""Instant answer evaluation and scoring engine for multiple question types."""
from enum import Enum
import re
from typing import Any, Optional, Set, Tuple, Union

from backend.models import QuestionType

JUDGE_TRUE_VALUES = {"T", "TRUE", "1", "正确", "对", "YES", "Y", "✓", "✔"}
JUDGE_FALSE_VALUES = {"F", "FALSE", "0", "错误", "错", "NO", "N", "✗", "✘", "X"}


def _normalize_judge(ans: Any) -> Optional[str]:
    """Normalize judge question answers to standard 'T' or 'F'."""
    if ans is None:
        return None
    val = str(ans).strip().upper()
    if val in JUDGE_TRUE_VALUES:
        return "T"
    if val in JUDGE_FALSE_VALUES:
        return "F"
    return val


def _parse_multi_options(ans: Any) -> Set[str]:
    """Parse multiple choice answer representations into a set of option keys."""
    if ans is None:
        return set()
    if isinstance(ans, (list, tuple, set)):
        items: Set[str] = set()
        for x in ans:
            items.update(_parse_multi_options(x))
        return items

    val = str(ans).strip().upper()
    if not val:
        return set()

    # Extract alphanumeric characters as option tokens
    return {c for c in val if c.isalnum()}


class Scorer:
    """Core scoring engine for instant single-choice, judge, and multi-choice fractional scoring."""

    @staticmethod
    def evaluate(
        q_type: Union[str, QuestionType, Enum],
        user_answer: Any,
        correct_answer: Any,
        partial_ratio: float = 0.5,
    ) -> Tuple[bool, float]:
        """Evaluate user answer against correct answer.

        Args:
            q_type: Question type (SINGLE, MULTI, JUDGE, ESSAY)
            user_answer: Raw user answer string or structure
            correct_answer: Standard answer string or structure
            partial_ratio: Fractional score ratio for omitted choices in MULTI (default 0.5)

        Returns:
            Tuple[is_correct: bool, score_ratio: float]
        """
        result = Scorer.result(
            q_type=q_type,
            user_answer=user_answer,
            correct_answer=correct_answer,
            partial_ratio=partial_ratio,
        )
        return result["is_correct"], result["score_ratio"]

    @staticmethod
    def result(
        q_type: Union[str, QuestionType, Enum],
        user_answer: Any,
        correct_answer: Any,
        partial_ratio: float = 0.5,
    ) -> dict:
        """Return score and mastery semantics without conflating partial credit with correctness."""
        type_str = (
            q_type.value
            if hasattr(q_type, "value")
            else str(q_type)
        ).strip().upper()

        if type_str == QuestionType.SINGLE.value or type_str == "SINGLE":
            if user_answer is None or correct_answer is None:
                return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "UNANSWERED"}
            u_clean = str(user_answer).strip().upper()
            c_clean = str(correct_answer).strip().upper()
            if not u_clean:
                return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "UNANSWERED"}
            if u_clean and u_clean == c_clean:
                return {"is_correct": True, "score_ratio": 1.0, "mastery_status": "CORRECT"}
            return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "INCORRECT"}

        if type_str == QuestionType.JUDGE.value or type_str == "JUDGE":
            u_norm = _normalize_judge(user_answer)
            c_norm = _normalize_judge(correct_answer)
            if u_norm is not None and u_norm in ("T", "F") and u_norm == c_norm:
                return {"is_correct": True, "score_ratio": 1.0, "mastery_status": "CORRECT"}
            if user_answer is None or not str(user_answer).strip():
                return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "UNANSWERED"}
            return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "INCORRECT"}

        if type_str == QuestionType.MULTI.value or type_str == "MULTI":
            user_set = _parse_multi_options(user_answer)
            correct_set = _parse_multi_options(correct_answer)

            if not user_set or not correct_set:
                return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "UNANSWERED"}

            if user_set == correct_set:
                return {"is_correct": True, "score_ratio": 1.0, "mastery_status": "CORRECT"}

            if user_set.issubset(correct_set):
                # Omitted choices without any wrong choices gets partial score
                return {"is_correct": False, "score_ratio": partial_ratio, "mastery_status": "PARTIAL"}

            # Contains at least one wrong choice
            return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "INCORRECT"}

        if type_str == QuestionType.ESSAY.value or type_str == "ESSAY":
            # Essay question defaults to 0.0 until manual/AI scoring
            return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "UNANSWERED"}

        # Fallback exact string match for custom question types
        if user_answer is not None and correct_answer is not None:
            if str(user_answer).strip() == str(correct_answer).strip():
                return {"is_correct": True, "score_ratio": 1.0, "mastery_status": "CORRECT"}

        if user_answer is None or not str(user_answer).strip():
            return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "UNANSWERED"}
        return {"is_correct": False, "score_ratio": 0.0, "mastery_status": "INCORRECT"}
