from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import current_user
from backend.app.api.routes.practice import DraftPayload

router = APIRouter(prefix="/sync", tags=["sync"])


class EventPayload(BaseModel):
    id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict = Field(default_factory=dict)


class EventsPayload(BaseModel):
    events: list[EventPayload] = Field(default_factory=list)


@router.post("/sessions/{session_id}")
def sync_session(session_id: str, payload: DraftPayload, request: Request, user=Depends(current_user)):
    return request.app.state.services.practice.sync_draft(user["id"], session_id, payload.model_dump())


@router.post("/events", status_code=201)
def append_events(payload: EventsPayload, request: Request, user=Depends(current_user)):
    accepted = request.app.state.services.practice.practices.append_events(user["id"], [event.model_dump() for event in payload.events])
    return {"accepted": accepted, "received": len(payload.events)}


@router.get("/events")
def list_events(request: Request, after: str | None = None, user=Depends(current_user)):
    return request.app.state.services.practice.practices.list_events(user["id"], after)
