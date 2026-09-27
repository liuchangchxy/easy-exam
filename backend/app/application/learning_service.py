from backend.app.domain.learning.recommendation import build_recommendations
from backend.app.domain.learning.study_plan import build_study_plan


class LearningService:
    def __init__(self, practices):
        self.practices = practices

    def summary(self, user_id: str) -> dict:
        return self.practices.summary(user_id)

    def trends(self, user_id: str, bank_id: str | None = None, window_days: int = 14) -> dict:
        return self.practices.trends(user_id, bank_id, window_days)

    def recommendations(
        self,
        user_id: str,
        bank_id: str | None = None,
        limit: int = 20,
        include_new: bool = True,
        include_weak: bool = True,
        include_due: bool = True,
        question_type: str | None = None,
        difficulty: int | None = None,
        chapter: str | None = None,
        new_ratio: float | None = None,
    ) -> list[dict]:
        return build_recommendations(
            self.practices.recommendation_candidates(user_id, bank_id, question_type),
            limit=limit,
            include_new=include_new,
            include_weak=include_weak,
            include_due=include_due,
            difficulty=difficulty,
            chapter=chapter,
            new_ratio=new_ratio,
        )

    def study_plan(
        self,
        user_id: str,
        bank_id: str | None,
        minutes_per_day: int,
        days: int,
        difficulty: int | None = None,
        chapter: str | None = None,
        new_ratio: float | None = None,
    ) -> dict:
        limit = min(500, max(1, (minutes_per_day // 2) * days))
        records = self.practices.recommendation_candidates(user_id, bank_id)
        recommendations = build_recommendations(
            records,
            limit=limit,
            difficulty=difficulty,
            chapter=chapter,
            new_ratio=new_ratio,
        )
        return build_study_plan(recommendations, minutes_per_day, days)
