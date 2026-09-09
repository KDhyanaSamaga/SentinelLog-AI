from datetime import datetime
from sqlalchemy.orm import Session
from src.modules.auth.models import RefreshToken
from src.modules.users.models import User
from src.modules.users.services import get_user_by_email, get_user_by_username
from src.modules.auth.security import verify_password

def authenticate_user(db: Session, email_or_username: str, password: str) -> User | None:
    # Check by email first, then username
    user = get_user_by_email(db, email=email_or_username)
    if not user:
        user = get_user_by_username(db, username=email_or_username)
    
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_refresh_token_entry(db: Session, user_id: str, token_hash: str, expires_at: datetime) -> RefreshToken:
    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token

def revoke_refresh_token(db: Session, token_id: str) -> None:
    db_token = db.query(RefreshToken).filter(RefreshToken.id == token_id).first()
    if db_token:
        db_token.revoked = True
        db.commit()

def revoke_all_user_tokens(db: Session, user_id: str) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id, 
        RefreshToken.revoked == False
    ).update({"revoked": True})
    db.commit()
