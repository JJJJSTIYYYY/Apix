from apix.agent.sdk.adapter.bot.base import (
    MessageConfig,
    ModelCapabilities,
    ReasoningConfig,
    RequestConfig,
)
from apix.agent.sdk.adapter.bot.base_bot import BaseOpenAIBot
from apix.agent.sdk.utils.exception import ProviderNotFoundError, ProviderTypeMismatchError
from apix.config.base_config import PROVIDER_BASE_URL
from apix.agent.store import query_store


async def get_custom_provider_meta(provider_id: str, type_check: str | None = None) -> dict:
    """Get the custom provider's metadata.
    
    Args:
        provider_id (str): The ID of the custom provider.
        type_check (str | None): The type to check against.

    Returns:
        dict: The metadata of the custom provider.
            ```python
            {
                "provider_id": str,
                "provider_name": str,
                "type": str,
                "endpoint": str,
                "model_list": list,
                "description": str,
                "created_at": str
            }
            ```

    Raises:
        ValueError: If the provider_id is not provided or if no metadata is found for the given provider_id.
    """
    if not provider_id:
        raise ValueError("Provider ID is required.")

    query_payload = {"provider_id": provider_id}
    result = await query_store(
        action="get_llm_provider_by_id",
        payload=query_payload
    )
    meta = result.get("messages", [])
    if not meta:
        raise ProviderNotFoundError(f"No metadata found for provider ID: {provider_id}")

    if type_check is not None and meta[0].get("type") != type_check:
        raise ProviderTypeMismatchError(f"Provider type mismatch: expected {type_check}, got {meta[0].get('type')}.")
    return meta[0]


class CustomBot(BaseOpenAIBot):
    """Custom provider adapter."""
