"""
Standalone test: auth user-resolution on duplicate email (P0.7), anon-claim
determination (P0.8), and JWT rejection of unsigned tokens.
Run directly: venv/bin/python backend/test_auth_email.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from backend.auth import get_or_create_user_from_token, decode_supabase_jwt
from backend.db.models import User, Subscription

PASSED = 0
FAILED = 0


def check(label: str, cond: bool):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {label}")
    else:
        FAILED += 1
        print(f"FAIL  {label}")


class FakeResult:
    def __init__(self, rows):
        self._rows = rows if rows else []

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    """Minimal AsyncSession double: enough for get_or_create_user_from_token."""

    def __init__(self, existing_user=None, fail_first_flush=False):
        self._user = existing_user
        self.fail_first_flush = fail_first_flush
        self.flush_calls = 0
        self.added = []
        self.rolled_back = False

    async def execute(self, stmt):
        text = str(stmt)
        if "Subscription" in text or "subscriptions" in text.lower():
            # Flushed Subscription rows are visible to later queries in the
            # same session/transaction (mirrors real SQLAlchemy behavior).
            subs = [a for a in self.added if isinstance(a, Subscription)]
            return FakeResult(subs)
        return FakeResult([self._user] if self._user else [])

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flush_calls += 1
        if self.fail_first_flush and self.flush_calls == 1:
            self.rolled_back = True
            # Simulate the "winner" of the race existing after the rollback.
            self._user = User(id="u2", email="same@example.com", is_anonymous=False)
            raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: users.email"))

    async def rollback(self):
        self.rolled_back = True


def test_new_user_creation():
    s = FakeSession()
    user = __import__("asyncio").run(get_or_create_user_from_token(
        {"sub": "u1", "email": "a@example.com", "is_anonymous": False}, s))
    check("new user created", user.id == "u1")
    check("subscription added", len(s.added) == 2)  # User + Subscription
    check("no rollback needed", s.rolled_back is False)


def test_duplicate_email_race():
    # First insert flushes with IntegrityError -> must re-resolve, not raise.
    s = FakeSession(fail_first_flush=True)
    user = __import__("asyncio").run(get_or_create_user_from_token(
        {"sub": "u2", "email": "same@example.com", "is_anonymous": False}, s))
    check("resolved to existing user after race", user.id == "u2")


def test_missing_subscription_backfilled():
    existing = User(id="u3", email="c@example.com", is_anonymous=False)
    s = FakeSession(existing_user=existing)
    user = __import__("asyncio").run(get_or_create_user_from_token(
        {"sub": "u3", "email": "c@example.com", "is_anonymous": False}, s))
    check("existing user returned", user.id == "u3")
    check("missing subscription backfilled", any(isinstance(a, Subscription) for a in s.added))


def test_anon_claim_from_payload():
    # P0.8: is_anonymous comes from the JWT claim, not the email suffix.
    s = FakeSession()
    anon = __import__("asyncio").run(get_or_create_user_from_token(
        {"sub": "g1", "is_anonymous": True}, s))
    check("anon claim honored", anon.is_anonymous is True)

    s2 = FakeSession()
    # Forged email ending in @anonymous.norai WITHOUT the claim must NOT be anon.
    user = __import__("asyncio").run(get_or_create_user_from_token(
        {"sub": "g2", "email": "victim@anonymous.norai", "is_anonymous": False}, s2))
    check("forged email suffix does not mark anonymous", user.is_anonymous is False)


def test_decode_rejects_unsigned():
    check("empty token -> None", decode_supabase_jwt("") is None)
    check("garbage token -> None", decode_supabase_jwt("not.a.jwt") is None)


if __name__ == "__main__":
    test_new_user_creation()
    test_duplicate_email_race()
    test_missing_subscription_backfilled()
    test_anon_claim_from_payload()
    test_decode_rejects_unsigned()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
