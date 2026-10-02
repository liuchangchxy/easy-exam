from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.dependencies import current_user

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/summary")
def summary(request: Request, user=Depends(current_user)):
    return request.app.state.services.learning.summary(user["id"])


@router.get("/trends")
def trends(
    bank_id: str | None = None,
    window_days: int = 14,
    request: Request = None,
    user=Depends(current_user),
):
    return request.app.state.services.learning.trends(user["id"], bank_id, window_days)


@router.get("/plan")
def study_plan(
    bank_id: str | None = None,
    minutes_per_day: int = 30,
    days: int = 7,
    difficulty: int | None = None,
    chapter: str | None = None,
    new_ratio: float | None = None,
    questions_per_day: int | None = None,
    request: Request = None,
    user=Depends(current_user),
):
    return request.app.state.services.learning.study_plan(
        user["id"], bank_id, minutes_per_day, days, difficulty, chapter, new_ratio, questions_per_day
    )


@router.get("/recommendations")
def recommendations(
    bank_id: str | None = None,
    limit: int = 20,
    include_new: bool = True,
    include_weak: bool = True,
    include_due: bool = True,
    question_type: str | None = None,
    difficulty: int | None = None,
    chapter: str | None = None,
    new_ratio: float | None = None,
    request: Request = None,
    user=Depends(current_user),
):
    return request.app.state.services.learning.recommendations(
        user["id"], bank_id, limit, include_new, include_weak, include_due, question_type, difficulty, chapter, new_ratio
    )


@router.post("/weak/{question_id}", status_code=201)
def mark_weak(question_id: str, request: Request, user=Depends(current_user)):
    result = request.app.state.services.practice.practices.mark_weak(user["id"], question_id)
    if not result:
        raise HTTPException(status_code=404, detail="question not found")
    return result


@router.delete("/weak/{question_id}", status_code=204)
def unmark_weak(question_id: str, request: Request, user=Depends(current_user)):
    request.app.state.services.practice.practices.unmark_weak(user["id"], question_id)
    return None
