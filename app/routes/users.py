from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_user_by_ctk

router = APIRouter()


@router.get("/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    user = get_user_by_ctk(request, db)
    if not user:
        return None
    return {"id": user.id, "name": user.name}
