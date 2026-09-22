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
        type_str = (
            q_type.value
            if hasattr(q_type, "value")
            else str(q_type)
        ).strip().upper()

        if type_str == QuestionType.SINGLE.value or type_str == "SINGLE":
            if user_answer is None or correct_answer is None:
                return False, 0.0
            u_clean = str(user_answer).strip().upper()
            c_clean = str(correct_answer).strip().upper()
            if u_clean and u_clean == c_clean:
                return True, 1.0
            return False, 0.0

        if type_str == QuestionType.JUDGE.value or type_str == "JUDGE":
            u_norm = _normalize_judge(user_answer)
            c_norm = _normalize_judge(correct_answer)
            if u_norm is not None and u_norm in ("T", "F") and u_norm == c_norm:
                return True, 1.0
            return False, 0.0

        if type_str == QuestionType.MULTI.value or type_str == "MULTI":
            user_set = _parse_multi_options(user_answer)
            correct_set = _parse_multi_options(correct_answer)

            if not user_set or not correct_set:
                return False, 0.0

            if user_set == correct_set:
                return True, 1.0

            if user_set.issubset(correct_set):
                # Omitted choices without any wrong choices gets partial score
                return True, partial_ratio

            # Contains at least one wrong choice
            return False, 0.0

        if type_str == QuestionType.ESSAY.value or type_str == "ESSAY":
            # Essay question defaults to 0.0 until manual/AI scoring
            return False, 0.0

        # Fallback exact string match for custom question types
        if user_answer is not None and correct_answer is not None:
            if str(user_answer).strip() == str(correct_answer).strip():
                return True, 1.0

        return False, 0.0
