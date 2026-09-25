"""Exam scoring rules applied only when a mock exam is submitted."""


def grade_report(attempts: list[dict], blueprint: dict | None = None) -> float:
    blueprint = blueprint or {}
    negative_mark = float(blueprint.get("negative_mark", 0) or 0)
    score = sum(float(item.get("score_ratio") or 0) for item in attempts)
    incorrect = sum(1 for item in attempts if item.get("correctness") == "INCORRECT")
    return round(score - incorrect * negative_mark, 2)
