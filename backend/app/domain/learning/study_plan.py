from datetime import datetime, timezone


def build_study_plan(recommendations: list[dict], minutes_per_day: int, days: int, minutes_per_question: int = 2) -> dict:
    minutes_per_day = max(5, min(int(minutes_per_day), 600))
    days = max(1, min(int(days), 7))
    per_day = minutes_per_day // minutes_per_question
    schedule = []
    cursor = 0
    for day_number in range(1, days + 1):
        items = recommendations[cursor:cursor + per_day]
        cursor += len(items)
        schedule.append({
            "day_number": day_number,
            "estimated_minutes": len(items) * minutes_per_question,
            "items": [
                {**item, "estimated_minutes": minutes_per_question}
                for item in items
            ],
        })
    assigned = sum(len(day["items"]) for day in schedule)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": schedule,
        "question_count": assigned,
        "planned_minutes": assigned * minutes_per_question,
        "time_budget_minutes": minutes_per_day * days,
        "minutes_per_question": minutes_per_question,
    }
