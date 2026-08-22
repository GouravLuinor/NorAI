"""
backend/auth.py

Supabase Auth JWT verification and user resolution dependency for FastAPI.
Decodes Supabase JWT tokens, extracts sub (user_id), email, and metadata,
and ensures a corresponding User and Subscription record exist in the database.
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import jwt as pyjwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.db.database import get_db
from backend.db.models import User, Subscription

# HTTP Bearer authentication scheme (auto_error=False to allow anonymous optional routes)
security = HTTPBearer(auto_error=False)

load_dotenv()

# Real Supabase JWT secret (Settings → API → JWT Settings). Fails closed if absent
# unless NORAI_DEV_INSECURE_AUTH=1 is explicitly set for local-only development.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
DEV_INSECURE_AUTH = os.environ.get("NORAI_DEV_INSECURE_AUTH", "") == "1"

# Fail closed: the insecure-auth escape hatch decodes JWTs WITHOUT signature
# verification (any `sub` claim impersonates any account). It must never be
# active when the process claims to run in production — refuse to even import.
IS_PROD = os.environ.get("NORAI_ENV") == "production"
if IS_PROD and DEV_INSECURE_AUTH:
    raise RuntimeError(
        "Refusing to start: NORAI_DEV_INSECURE_AUTH=1 disables JWT signature "
        "verification and must never be set while NORAI_ENV=production."
    )

# Supabase access tokens are issued with aud "authenticated" for both
# email/OAuth users and anonymous (signInAnonymously) sessions.
ALLOWED_AUDIENCES = {"authenticated", "anon"}

# Newer Supabase projects sign access tokens with ES256 per-project keys,
# published at the JWKS endpoint. Cached by PyJWKClient (keyed by kid).
_jwks_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json") if SUPABASE_URL else None


def decode_supabase_jwt(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a Supabase JWT token.

    Verifies the signature using the token's algorithm: ES256 via the Supabase
    JWKS public keys (current default), or HS256 via SUPABASE_JWT_SECRET (legacy).
    Fails closed unless the signature and `aud` claim are valid.
    """
    if not token:
        return None
    try:
        alg = (pyjwt.get_unverified_header(token) or {}).get("alg", "")
        key: Any
        if alg == "ES256" and _jwks_client is not None:
            key = _jwks_client.get_signing_key_from_jwt(token).key
        elif alg == "HS256" and SUPABASE_JWT_SECRET:
            key = SUPABASE_JWT_SECRET
        elif DEV_INSECURE_AUTH and not IS_PROD:
            # Local-only escape hatch: decode without signature verification.
            payload = pyjwt.decode(token, options={"verify_signature": False})
            if not payload.get("sub"):
                return None
            return payload
        else:
            return None
        payload = pyjwt.decode(token, key, algorithms=[alg], audience=list(ALLOWED_AUDIENCES))
    except pyjwt.PyJWTError:
        return None

    if not payload.get("sub"):
        return None
    if payload.get("aud") not in ALLOWED_AUDIENCES:
        return None
    return payload


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
    # Trust the Supabase anon claim (signInAnonymously sessions) rather than the
    # email suffix, which is forgeable via the email field of any signed token.
    is_anonymous = bool(payload.get("is_anonymous", False))
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

        try:
            await db.flush()
        except IntegrityError:
            # Two tokens with different `sub` but the same email raced on
            # User.email unique. Roll back our insert and re-fetch the winner
            # so auth doesn't silently degrade to anonymous.
            await db.rollback()
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is None:
                result = await db.execute(select(User).where(User.email == email))
                user = result.scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unable to resolve user account",
                )

    # Ensure the resolved user always has a Subscription row
    sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    if not sub_result.scalar_one_or_none():
        db.add(
            Subscription(
                user_id=user.id,
                status="trial",
                plan_tier="free",
                monthly_minutes_quota=15,
                used_minutes_this_month=0,
            )
        )
        await db.flush()

    return user


DEV_USER_ID = "dev-user-0000-0000-0000-000000000000"


def is_dev_access() -> bool:
    """Check if local development bypass is active via env flags."""
    return (
        os.environ.get("NORAI_DEV_ACCESS", "0") == "1"
        or os.environ.get("NORAI_DEV_INSECURE_AUTH", "0") == "1"
    )


async def get_or_create_dev_user(db: AsyncSession) -> User:
    """Find or create the default local development user."""
    result = await db.execute(select(User).where(User.id == DEV_USER_ID))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            id=DEV_USER_ID,
            email="dev@norai.local",
            full_name="Local Dev User",
            is_anonymous=False,
        )
        db.add(user)
        db.add(
            Subscription(
                user_id=DEV_USER_ID,
                status="active",
                plan_tier="pro",
                monthly_minutes_quota=999999,
                used_minutes_this_month=0,
            )
        )
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            result = await db.execute(select(User).where(User.id == DEV_USER_ID))
            user = result.scalar_one_or_none()
    return user


# Device-scoped guest identities (P8.x): a frontend-generated persistent
# X-Guest-Id lets unauthenticated visitors process lectures under the free-trial
# quota without any Supabase token. The id is client-minted, so it only gates
# the 15-minute trial tier — real accounts (Bearer token) always win over it.
_GUEST_HEADER = "X-Guest-Id"
_GUEST_ID_MAX_LEN = 48  # keeps derived User.id within String(64)


def guest_id_from_request(request: Optional[Request]) -> Optional[str]:
    """Return a sanitized X-Guest-Id header value, or None."""
    if request is None:
        return None
    guest_id = request.headers.get(_GUEST_HEADER, "").strip()
    if not guest_id:
        return None
    if len(guest_id) > _GUEST_ID_MAX_LEN:
        guest_id = guest_id[:_GUEST_ID_MAX_LEN]
    return guest_id


async def get_or_create_guest_user(db: AsyncSession, guest_id: str) -> User:
    """Find or create an anonymous device-scoped User + free-trial Subscription."""
    user_id = f"guest-{guest_id}"

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=user_id,
            email=f"{guest_id}@guest.norai",
            full_name="Guest",
            is_anonymous=True,
        )
        db.add(user)
        db.add(
            Subscription(
                user_id=user_id,
                status="trial",
                plan_tier="free",
                monthly_minutes_quota=15,  # 15 mins free trial
                used_minutes_this_month=0,
            )
        )
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unable to resolve guest account",
                )

    # Ensure the resolved guest always has a Subscription row
    sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    if not sub_result.scalar_one_or_none():
        db.add(
            Subscription(
                user_id=user.id,
                status="trial",
                plan_tier="free",
                monthly_minutes_quota=15,
                used_minutes_this_month=0,
            )
        )
        await db.flush()

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Optional dependency: returns User if a valid Bearer token is provided.

    Otherwise, when NOT in local dev mode, falls back to a device-scoped guest
    user derived from the `X-Guest-Id` header (so unauthenticated visitors can
    process lectures under the free-trial quota). Returns None only when neither
    a valid token nor a guest id is present.
    """
    if credentials and credentials.credentials:
        payload = decode_supabase_jwt(credentials.credentials)
        if payload:
            try:
                return await get_or_create_user_from_token(payload, db)
            except Exception:
                return None

    # Local dev keeps its automatic dev-user escape hatch instead of guests.
    if not is_dev_access():
        guest_id = guest_id_from_request(request)
        if guest_id:
            try:
                return await get_or_create_guest_user(db, guest_id)
            except Exception:
                return None

    return None


async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Required dependency: raises 401 Unauthorized if no valid user token provided.
    In local dev mode (NORAI_DEV_ACCESS=1 or NORAI_DEV_INSECURE_AUTH=1), falls back
    to an automatic local dev user so localhost works seamlessly without login.
    """
    if not user:
        if is_dev_access():
            return await get_or_create_dev_user(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

