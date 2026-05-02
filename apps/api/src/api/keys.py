"""Client for the Plan 1 `vault_load_keys` RPC.

Fetches BYO API keys for a specific (user, providers) pair via Supabase's
PostgREST RPC endpoint, using the service-role key. Plaintext lives only
in the returned dict and never enters logs.
"""

from __future__ import annotations

from uuid import UUID

import httpx

from api.logging import get_logger

logger = get_logger(__name__)


class KeyVaultError(RuntimeError):
    """Raised when key vault access fails or required keys are missing."""


async def load_keys(
    *,
    user_id: UUID,
    providers: list[str],
    supabase_url: str,
    service_role_key: str,
    optional_providers: list[str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = 5.0,
) -> dict[str, str]:
    """Fetch and decrypt the user's BYO keys.

    `providers` are required — KeyVaultError is raised if any are missing.
    `optional_providers` are best-effort: included in the lookup, returned
    if present, silently absent otherwise. Useful for keys (like
    alpha_vantage) that the engine can do without.
    """
    optional = optional_providers or []
    all_providers = list(dict.fromkeys(list(providers) + optional))

    url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/vault_load_keys"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    payload = {"p_user_id": str(user_id), "p_providers": all_providers}

    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        logger.error(
            "vault_load_keys failed",
            status_code=response.status_code,
            user_id=str(user_id),
        )
        raise KeyVaultError(f"vault_load_keys returned {response.status_code}")

    rows = response.json()
    keys: dict[str, str] = {row["provider"]: row["plaintext"] for row in rows}

    missing_required = set(providers) - keys.keys()
    if missing_required:
        logger.warning(
            "vault_load_keys missing required providers",
            user_id=str(user_id),
            missing_providers=sorted(missing_required),
        )
        raise KeyVaultError(
            f"No API key configured for: {', '.join(sorted(missing_required))}. "
            "Add one in Settings."
        )

    logger.info(
        "vault_load_keys ok",
        user_id=str(user_id),
        providers=sorted(keys.keys()),
    )
    return keys
