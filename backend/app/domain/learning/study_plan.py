from datetime import datetime, timezone


def build_study_plan(
    recommendations: list[dict],
    minutes_per_day: int = 30,
    days: int = 7,
    minutes_per_question: int = 2,
    questions_per_day: int | None = None,
) -> dict:
    minutes_per_day = max(1, min(int(minutes_per_day), 600))
    days = max(1, min(int(days), 30))
    minutes_per_question = max(1, int(minutes_per_question))

    total_available = len(recommendations)
    if questions_per_day is not None and int(questions_per_day) > 0:
        per_day = max(1, min(int(questions_per_day), 10000))
    else:
        per_day = max(1, minutes_per_day // minutes_per_question)

    target_capacity = days * per_day
    schedule = []

    def get_phase_focus(day_idx: int, total_days: int) -> tuple[str, str]:
        ratio = day_idx / total_days
        if ratio <= 0.35:
            return "基础攻坚", "新题探索与核心概念理解"
        elif ratio <= 0.70:
            return "薄弱突破", "高频错题与难点考点强化"
        else:
            return "抗遗忘冲刺", "到期艾宾浩斯复习与综合提分"

    if total_available == 0:
        for day_number in range(1, days + 1):
            focus_name, focus_desc = get_phase_focus(day_number, days)
            schedule.append({
                "day_number": day_number,
                "title": f"第 {day_number} 天 · {focus_name}",
                "focus": focus_name,
                "focus_description": focus_desc,
                "estimated_minutes": 0,
                "question_count": 0,
                "question_ids": [],
                "bank_id": None,
                "items": [],
            })
    elif total_available < days:
        for day_number in range(1, days + 1):
            day_items = [recommendations[day_number - 1]] if day_number <= total_available else []
            focus_name, focus_desc = get_phase_focus(day_number, days)
            schedule.append({
                "day_number": day_number,
                "title": f"第 {day_number} 天 · {focus_name}",
                "focus": focus_name,
                "focus_description": focus_desc,
                "estimated_minutes": len(day_items) * minutes_per_question,
                "question_count": len(day_items),
                "question_ids": [it.get("question_id") for it in day_items if it.get("question_id")],
                "bank_id": day_items[0].get("bank_id") if day_items else None,
                "items": [
                    {**it, "estimated_minutes": minutes_per_question}
                    for it in day_items
                ],
            })
    elif total_available < target_capacity:
        base_count = total_available // days
        rem = total_available % days
        cursor = 0
        for day_number in range(1, days + 1):
            take = base_count + (1 if day_number <= rem else 0)
            day_items = recommendations[cursor:cursor + take]
            cursor += len(day_items)
            focus_name, focus_desc = get_phase_focus(day_number, days)
            schedule.append({
                "day_number": day_number,
                "title": f"第 {day_number} 天 · {focus_name}",
                "focus": focus_name,
                "focus_description": focus_desc,
                "estimated_minutes": len(day_items) * minutes_per_question,
                "question_count": len(day_items),
                "question_ids": [it.get("question_id") for it in day_items if it.get("question_id")],
                "bank_id": day_items[0].get("bank_id") if day_items else None,
                "items": [
                    {**it, "estimated_minutes": minutes_per_question}
                    for it in day_items
                ],
            })
    else:
        cursor = 0
        for day_number in range(1, days + 1):
            day_items = recommendations[cursor:cursor + per_day]
            cursor += len(day_items)
            focus_name, focus_desc = get_phase_focus(day_number, days)
            schedule.append({
                "day_number": day_number,
                "title": f"第 {day_number} 天 · {focus_name}",
                "focus": focus_name,
                "focus_description": focus_desc,
                "estimated_minutes": len(day_items) * minutes_per_question,
                "question_count": len(day_items),
                "question_ids": [it.get("question_id") for it in day_items if it.get("question_id")],
                "bank_id": day_items[0].get("bank_id") if day_items else None,
                "items": [
                    {**it, "estimated_minutes": minutes_per_question}
                    for it in day_items
                ],
            })

    assigned = sum(len(day["items"]) for day in schedule)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": schedule,
        "day_count": days,
        "question_count": assigned,
        "planned_minutes": assigned * minutes_per_question,
        "time_budget_minutes": minutes_per_day * days,
        "minutes_per_question": minutes_per_question,
        "minutes_per_day": minutes_per_day,
    }
