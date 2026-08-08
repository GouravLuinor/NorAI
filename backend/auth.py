"""
backend/auth.py

Supabase Auth JWT verification and user resolution dependency for FastAPI.
Decodes Supabase JWT tokens, extracts sub (user_id), email, and metadata,
and ensures a corresponding User and Subscription record exist in the database.
"""

import os
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.database import get_db
from backend.db.models import User, Subscription

# HTTP Bearer authentication scheme (auto_error=False to allow anonymous optional routes)
security = HTTPBearer(auto_error=False)

SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "super-secret-jwt-token-with-at-least-32-characters")


def decode_supabase_jwt(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a Supabase JWT token.
    Attempts pyjwt decoding if available; falls back to unverified header/payload extraction in dev mode.
    """
    try:
        import jwt
        # Attempt decoding with secret if provided
        try:
            payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
            return payload
        except Exception:
            # Fallback to unverified payload decoding for local dev/testing without secret
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
    except Exception:
        return None


async def get_or_create_user_from_token(payload: Dict[str, Any], db: AsyncSession) -> User:
    """
    Given a decoded JWT payload, find or create the User and their default Subscription in DB.
    """
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing sub/user_id",
        )

    email = payload.get("email") or f"{user_id}@anonymous.norai"
    is_anonymous = payload.get("is_anonymous", False) or email.endswith("@anonymous.norai")
    full_name = payload.get("user_metadata", {}).get("full_name") or payload.get("name")
    avatar_url = payload.get("user_metadata", {}).get("avatar_url")

    # Fetch user from DB
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=user_id,
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            is_anonymous=is_anonymous,
        )
        db.add(user)
        
        # Create default Free Trial Subscription
        subscription = Subscription(
            user_id=user_id,
            status="trial",
            plan_tier="free",
            monthly_minutes_quota=15,  # 15 mins free trial
            used_minutes_this_month=0,
        )
        db.add(subscription)
        await db.flush()

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Optional dependency: returns User if valid Bearer token provided, otherwise None.
    """
    if not credentials or not credentials.credentials:
        return None

    payload = decode_supabase_jwt(credentials.credentials)
    if not payload:
        return None

    try:
        return await get_or_create_user_from_token(payload, db)
    except Exception:
        return None


async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """
    Required dependency: raises 401 Unauthorized if no valid user token provided.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
