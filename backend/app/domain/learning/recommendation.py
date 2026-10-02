"""Deterministic learning recommendation rules.

The first version deliberately keeps recommendation explainable.  A user can
see why an item was selected, and the rules remain useful when AI is disabled.
"""

from typing import Any


def rank_recommendation(record: dict[str, Any]) -> dict[str, Any]:
    """Add a stable priority and human-readable reason to a learning record."""
    mistakes = int(record.get("mistake_count") or 0)
    mastery = record.get("mastery_status") or "UNSEEN"
    is_cleared = bool(record.get("is_cleared"))
    is_due = bool(record.get("is_due"))
    is_weak_flagged = bool(record.get("is_weak_flagged"))
    is_weak = is_weak_flagged or (not is_cleared and mistakes > 0 and mastery in {"WEAK", "PARTIAL"})
    if is_weak_flagged:
        reason = "标记薄弱"
        category = "WEAK"
        priority = 90
    elif not is_cleared and mistakes > 0 and mastery in {"WEAK", "PARTIAL"}:
        reason = "错题待复习"
        category = "WEAK"
        priority = 100 + min(mistakes, 20)
    elif is_due:
        reason = "复习到期"
        category = "DUE"
        priority = 80
    elif not record.get("last_attempt_at"):
        reason = "新题覆盖"
        category = "NEW"
        priority = 50
    else:
        reason = "巩固练习"
        category = "CONSOLIDATE"
        priority = 20

    return {**record, "priority": priority, "reason": reason, "category": category}


def build_recommendations(
    records: list[dict[str, Any]],
    limit: int = 20,
    include_new: bool = True,
    include_weak: bool = True,
    include_due: bool = True,
    difficulty: int | None = None,
    chapter: str | None = None,
    new_ratio: float | None = None,
) -> list[dict[str, Any]]:
    """Rank records without consulting AI or any external service.

    Difficulty policy (SPEC §8 & Confirmed Decision):
    - When a specific difficulty filter is active, unclassified questions (difficulty 0) are excluded.
    - When no specific difficulty filter is active, unclassified questions participate normally.
    - Difficulty is never inferred from user attempts.
    """
    filtered_records = list(records)

    # 1. Difficulty filter (1..5; 0 means unclassified)
    if difficulty is not None:
        target_diff = int(difficulty)
        filtered_records = [
            r for r in filtered_records
            if int(r.get("difficulty") or 0) == target_diff
        ]

    # 2. Chapter filter (matched against tags or chapter_id)
    if chapter:
        target_chapter = str(chapter).strip()
        filtered_records = [
            r for r in filtered_records
            if target_chapter in r.get("tags", []) or target_chapter == str(r.get("chapter_id") or "")
        ]

    ranked = [rank_recommendation(record) for record in filtered_records]

    # 3. Category switches (EE-016: use structured category and exhaustive flags)
    if not include_new:
        ranked = [item for item in ranked if item.get("category") != "NEW" and item["reason"] != "新题覆盖"]
    if not include_weak:
        ranked = [
            item for item in ranked
            if item.get("category") != "WEAK"
            and not item.get("is_weak_flagged")
            and item["reason"] not in {"错题待复习", "标记薄弱"}
        ]
    if not include_due:
        ranked = [item for item in ranked if item.get("category") != "DUE" and item["reason"] != "复习到期"]

    # 4. Sorting by priority desc, last_attempt_at, question_id
    ranked.sort(key=lambda item: (-item["priority"], item.get("last_attempt_at") or "", item["question_id"]))

    max_limit = max(0, min(limit, 10000))

    # 5. Ratio adjustment if new_ratio is specified (0.0 to 1.0)
    if new_ratio is not None and max_limit > 0:
        ratio = max(0.0, min(1.0, float(new_ratio)))
        target_new = round(max_limit * ratio)
        target_review = max_limit - target_new

        new_pool = [item for item in ranked if item["reason"] == "新题覆盖"]
        review_pool = [item for item in ranked if item["reason"] != "新题覆盖"]

        selected_new = new_pool[:target_new]
        selected_review = review_pool[:target_review]

        # Fill remainder from either pool if one is exhausted
        if len(selected_new) < target_new:
            needed = target_new - len(selected_new)
            selected_review.extend(review_pool[target_review:target_review + needed])
        elif len(selected_review) < target_review:
            needed = target_review - len(selected_review)
            selected_new.extend(new_pool[target_new:target_new + needed])

        combined = selected_new + selected_review
        combined.sort(key=lambda item: (-item["priority"], item.get("last_attempt_at") or "", item["question_id"]))
        return combined[:max_limit]

    return ranked[:max_limit]

