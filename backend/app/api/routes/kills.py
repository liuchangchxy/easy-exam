from fastapi import APIRouter, Depends, Request

from backend.app.dependencies import current_user

router = APIRouter(prefix="/kills", tags=["kills"])


@router.get("")
def list_killed(request: Request, user=Depends(current_user)):
    return request.app.state.services.practice.practices.list_killed(user["id"])


@router.post("/{question_id}", status_code=201)
def kill_question(question_id: str, request: Request, user=Depends(current_user)):
    request.app.state.services.practice.practices.kill(user["id"], question_id)
    return {"question_id": question_id, "is_killed": True}


@router.delete("/{question_id}", status_code=204)
def unkill_question(question_id: str, request: Request, user=Depends(current_user)):
    request.app.state.services.practice.practices.unkill(user["id"], question_id)
