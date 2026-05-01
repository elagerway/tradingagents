"""JWT verification for Supabase user tokens.

Supports both legacy HS256 and modern ES256/RS256 JWKS-based projects.
The `decode_user_token` callable picks the right path based on the JWT's
header `alg` field. Project Settings -> API -> JWT Settings tells you which
your project uses.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient

from api.settings import get_settings

# Module-level JWKS client; lazy-initialized on first use.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        _jwks_client = PyJWKClient(
            f"{settings.supabase_url}/auth/v1/.well-known/jwks.json",
            cache_jwk_set=True,
            lifespan=3600,
            cache_keys=True,
        )
    return _jwks_client


def decode_user_token(token: str, *, hs256_secret: str | None = None) -> UUID:
    """Verify a Supabase user JWT and return the user UUID.

    Picks HS256 vs ES256/RS256 based on the JWT's header. For HS256 the
    secret is required (passed in for testability). For asymmetric algos
    we fetch the signing key from Supabase's JWKS endpoint.
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")

        if alg == "HS256":
            if hs256_secret is None:
                hs256_secret = get_settings().supabase_jwt_secret
            if not hs256_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="HS256 secret not configured",
                )
            payload = jwt.decode(
                token,
                hs256_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        elif alg in ("ES256", "RS256"):
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unsupported JWT alg: {alg}",
            )

        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing sub claim",
            )
        return UUID(sub)
    except HTTPException:
        raise
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc


def current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    """FastAPI dependency: returns the user UUID for the bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.removeprefix("Bearer ")
    return decode_user_token(token)
