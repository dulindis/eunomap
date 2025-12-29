from fastapi import Depends, HTTPException, Header
from requests import Session
from auth import verify_access_token
from database import get_db
from models import User


def get_current_user(token: str = Header(...), db: Session = Depends(get_db)):
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = payload.get("sub")
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
