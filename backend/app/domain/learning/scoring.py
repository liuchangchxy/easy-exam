"""Stable domain scoring contract used by the v1 practice application."""
from typing import Any, Dict


def _tokens(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        result: set[str] = set()
        for item in value:
            result.update(_tokens(item))
        return result
    return {char for char in str(value).strip().upper() if char.isalnum()}


def _judge(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"TRUE", "1", "正确", "对", "YES", "Y", "T"}:
        return "T"
    if text in {"FALSE", "0", "错误", "错", "NO", "N", "F"}:
        return "F"
    return text


def score_answer(question_type: str, user_answer: Any, correct_answer: Any) -> Dict[str, Any]:
    type_name = str(question_type or "SINGLE").upper()
    if type_name in {"ESSAY", "SHORT_ANSWER", "SUBJECTIVE"}:
        return {
            "score_ratio": 0.0,
            "correctness": "UNANSWERED",
            "mastery_status": "UNSEEN",
            "is_objective": False,
        }
    if type_name == "MULTI":
        user_set = _tokens(user_answer)
        correct_set = _tokens(correct_answer)
        if not user_set:
            status, ratio = "UNANSWERED", 0.0
        elif user_set == correct_set and correct_set:
            status, ratio = "CORRECT", 1.0
        elif user_set and user_set.issubset(correct_set) and correct_set:
            status, ratio = "PARTIAL", 0.5
        else:
            status, ratio = "INCORRECT", 0.0
    elif type_name == "JUDGE" and _judge(user_answer) == _judge(correct_answer) and _judge(user_answer) in {"T", "F"}:
        status, ratio = "CORRECT", 1.0
    elif user_answer is None or not str(user_answer).strip():
        status, ratio = "UNANSWERED", 0.0
    elif str(user_answer).strip().upper() == str(correct_answer or "").strip().upper():
        status, ratio = "CORRECT", 1.0
    else:
        status, ratio = "INCORRECT", 0.0
    return {
        "score_ratio": ratio,
        "correctness": status,
        "mastery_status": "MASTERED" if status == "CORRECT" else ("PARTIAL" if status == "PARTIAL" else ("UNSEEN" if status == "UNANSWERED" else "WEAK")),
        "is_objective": True,
    }
