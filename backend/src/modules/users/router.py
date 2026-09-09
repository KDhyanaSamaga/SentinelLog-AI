from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.connections import get_db
from src.modules.users import schema, services
from src.modules.auth.security import get_current_user
from src.modules.auth.security import verify_password

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/signup", response_model=schema.UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_in: schema.UserCreate, db: Session = Depends(get_db)):
    if services.get_user_by_email(db, email=user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system."
        )
    if services.get_user_by_username(db, username=user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this username already exists in the system."
        )
    if not user_in.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required."
        )
    
    user = services.create_user(db, user_in=user_in)
    return user

@router.post("/change-password")
def change_password(
    payload: schema.ChangePassword,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
        
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")
        
    services.change_user_password(db, current_user, payload.new_password)
    
    return {"message": "Password updated successfully"}
