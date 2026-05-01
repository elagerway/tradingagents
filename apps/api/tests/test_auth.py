"""Tests for JWT verification."""

import time
from uuid import UUID

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import decode_user_token

HS256_SECRET = "test-secret-do-not-use-in-prod"
SUB_UUID = "11111111-2222-3333-4444-555555555555"


def make_token(
    *,
    sub: str = SUB_UUID,
    exp_offset: int = 3600,
    aud: str = "authenticated",
    role: str = "authenticated",
) -> str:
    payload = {
        "sub": sub,
        "aud": aud,
        "role": role,
        "exp": int(time.time()) + exp_offset,
        "iss": "https://test.supabase.co/auth/v1",
    }
    return jwt.encode(payload, HS256_SECRET, algorithm="HS256")


def test_valid_hs256_token_returns_user_id():
    token = make_token()
    user_id = decode_user_token(token, hs256_secret=HS256_SECRET)
    assert user_id == UUID(SUB_UUID)


def test_expired_token_raises_401():
    token = make_token(exp_offset=-60)
    with pytest.raises(HTTPException) as exc:
        decode_user_token(token, hs256_secret=HS256_SECRET)
    assert exc.value.status_code == 401


def test_wrong_audience_raises_401():
    token = make_token(aud="anon")
    with pytest.raises(HTTPException) as exc:
        decode_user_token(token, hs256_secret=HS256_SECRET)
    assert exc.value.status_code == 401


def test_malformed_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        decode_user_token("not.a.real.jwt", hs256_secret=HS256_SECRET)
    assert exc.value.status_code == 401


def _build_app(secret: str):
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user_id=current_user_id_dep(secret)):  # noqa: B008
        return {"user_id": str(user_id)}

    return app


def current_user_id_dep(secret):
    # Inline override so tests don't pull from settings.
    from fastapi import Depends, Header

    def _dep(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Missing bearer")
        token = authorization.removeprefix("Bearer ")
        return decode_user_token(token, hs256_secret=secret)

    return Depends(_dep)


def test_whoami_with_valid_token():
    client = TestClient(_build_app(HS256_SECRET))
    token = make_token()
    r = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"user_id": SUB_UUID}


def test_whoami_without_authorization_returns_401():
    client = TestClient(_build_app(HS256_SECRET))
    r = client.get("/whoami")
    assert r.status_code == 401
