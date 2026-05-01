"""Shared fixtures for FastAPI integration tests."""

import time

import jwt
import pytest

HS256_SECRET = "test-secret-do-not-use-in-prod"
DEFAULT_USER_ID = "11111111-2222-3333-4444-555555555555"


def make_test_token(*, sub: str = DEFAULT_USER_ID, exp_offset: int = 3600) -> str:
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "role": "authenticated",
            "exp": int(time.time()) + exp_offset,
            "iss": "https://test.supabase.co/auth/v1",
        },
        HS256_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def hs256_secret() -> str:
    return HS256_SECRET


@pytest.fixture
def test_user_id() -> str:
    return DEFAULT_USER_ID


@pytest.fixture
def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_test_token()}"}


def pytest_addoption(parser):
    parser.addoption(
        "--run-real-engine",
        action="store_true",
        default=False,
        help="Run tests marked @pytest.mark.real_engine (calls real LLMs, costs money)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-real-engine"):
        return
    skip_real = pytest.mark.skip(reason="pass --run-real-engine to run")
    for item in items:
        if item.get_closest_marker("real_engine"):
            item.add_marker(skip_real)
