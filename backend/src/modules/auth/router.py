from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database.connections import get_db
from src.modules.auth import schema, services, security

router = APIRouter(prefix="/auth", tags=["auth"])

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

@router.post("/login", response_model=schema.TokenResponse)
def login(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2PasswordRequestForm expects username and password. We can use form_data.username for either email or username.
    user = services.authenticate_user(db, email_or_username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email/username or password"
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    access_token = security.create_access_token(user.id)
    refresh_token = security.create_refresh_token(user.id)
    
    # Save the refresh token in the database
    decoded_refresh = security.decode_token(refresh_token)
    expires_at = datetime.fromtimestamp(decoded_refresh["exp"], tz=timezone.utc)
    # We use a hash of the token to store in the DB for security, but we could just store it.
    # To keep it simple, we store the hash
    token_hash = security.get_password_hash(refresh_token)
    services.create_refresh_token_entry(
        db,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": security.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/refresh", response_model=schema.TokenResponse)
def refresh_token(request: schema.RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        decoded_refresh = security.decode_token(request.refresh_token)
        if decoded_refresh.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        
    user_id = decoded_refresh.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    # We must find the refresh token in DB.
    # Since we store hashes, we must verify. However, it's inefficient to check against all hashes.
    # Instead, we just revoke all old tokens for the user, or we decode the token and if it's valid, we proceed,
    # but that doesn't prevent replay attacks. A better approach for this simple implementation:
    # We decode it, check if it's in the DB if we didn't hash it, but we hashed it.
    # Let's simplify and just find the token that matches the user and verify its hash.
    # Actually, passlib hash verification can be slow if we have many tokens.
    # We can fetch all active tokens for the user.
    active_tokens = db.query(services.RefreshToken).filter(
        services.RefreshToken.user_id == user_id,
        services.RefreshToken.revoked == False
    ).all()
    
    matched_token = None
    for token_record in active_tokens:
        if security.verify_password(request.refresh_token, token_record.token_hash):
            matched_token = token_record
            break
            
    if not matched_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or not found")
        
    # Discard the old token
    services.revoke_refresh_token(db, matched_token.id)
    
    # Generate new tokens
    access_token = security.create_access_token(user_id)
    new_refresh_token = security.create_refresh_token(user_id)
    
    new_decoded = security.decode_token(new_refresh_token)
    new_expires_at = datetime.fromtimestamp(new_decoded["exp"], tz=timezone.utc)
    new_token_hash = security.get_password_hash(new_refresh_token)
    
    services.create_refresh_token_entry(
        db,
        user_id=user_id,
        token_hash=new_token_hash,
        expires_at=new_expires_at
    )
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": security.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/change-password")
def change_password(
    payload: schema.ChangePassword,
    current_user: services.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
        
    if not security.verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")
        
    services.change_user_password(db, current_user, payload.new_password)
    
    return {"message": "Password updated successfully"}
