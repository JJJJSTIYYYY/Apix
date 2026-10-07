"""Storage lookup for custom providers, separate from the inference layer."""

from apix.agent.core.utils.exception import (
    ProviderNotFoundError,
    ProviderTypeMismatchError,
)


async def get_custom_provider_meta(
    provider_id: str, type_check: str | None = None
) -> dict:
    if not provider_id:
        raise ValueError("Provider ID is required.")
    from apix.agent.store import query_store

    result = await query_store(
        action="get_llm_provider_by_id", payload={"provider_id": provider_id}
    )
    meta = result.get("messages", [])
    if not meta:
        raise ProviderNotFoundError(f"No metadata found for provider ID: {provider_id}")
    if type_check is not None and meta[0].get("type") != type_check:
        raise ProviderTypeMismatchError(
            f"Provider type mismatch: expected {type_check}, got {meta[0].get('type')}."
        )
    return meta[0]
