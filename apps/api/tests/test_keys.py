"""Tests for the vault_load_keys client."""
import logging
from uuid import UUID

import httpx
import pytest

from api.keys import KeyVaultError, load_keys


USER_ID = UUID("11111111-2222-3333-4444-555555555555")


def make_mock_transport(*, status_code: int, payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)
    return httpx.MockTransport(handler)


async def test_load_keys_returns_decrypted_plaintext():
    transport = make_mock_transport(
        status_code=200,
        payload=[
            {"provider": "openai", "plaintext": "sk-test-openai"},
            {"provider": "anthropic", "plaintext": "sk-test-anthropic"},
        ],
    )
    keys = await load_keys(
        user_id=USER_ID,
        providers=["openai", "anthropic"],
        supabase_url="http://test.local",
        service_role_key="service-role-token",
        transport=transport,
    )
    assert keys == {"openai": "sk-test-openai", "anthropic": "sk-test-anthropic"}


async def test_load_keys_raises_on_missing_provider():
    transport = make_mock_transport(
        status_code=200,
        payload=[{"provider": "openai", "plaintext": "sk-test-openai"}],
    )
    with pytest.raises(KeyVaultError, match="anthropic"):
        await load_keys(
            user_id=USER_ID,
            providers=["openai", "anthropic"],
            supabase_url="http://test.local",
            service_role_key="service-role-token",
            transport=transport,
        )


async def test_load_keys_does_not_log_plaintext(caplog):
    transport = make_mock_transport(
        status_code=200,
        payload=[{"provider": "openai", "plaintext": "sk-secret-do-not-leak"}],
    )
    caplog.set_level(logging.DEBUG)
    await load_keys(
        user_id=USER_ID,
        providers=["openai"],
        supabase_url="http://test.local",
        service_role_key="service-role-token",
        transport=transport,
    )
    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "sk-secret-do-not-leak" not in log_text


async def test_load_keys_raises_on_5xx():
    transport = make_mock_transport(status_code=500, payload={"error": "boom"})
    with pytest.raises(KeyVaultError, match="500"):
        await load_keys(
            user_id=USER_ID,
            providers=["openai"],
            supabase_url="http://test.local",
            service_role_key="service-role-token",
            transport=transport,
        )
