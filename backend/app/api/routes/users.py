from fastapi import APIRouter, Depends, Request

from backend.app.dependencies import current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/search")
def search_users(q: str = "", request: Request = None, user=Depends(current_user)):
    """Prefix search used by the add-bank-member combobox."""
    return request.app.state.services.users.search(q, exclude_user_id=user["id"], limit=10)
