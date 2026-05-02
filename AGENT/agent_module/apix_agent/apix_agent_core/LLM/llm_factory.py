from typing import Any

from langchain.chat_models import BaseChatModel

from apix_agent.commons.type_def import AgentConfigSchema, ProviderNoFound
from apix_agent.commons.logger import logger
from apix_agent.global_config import BASE_URL
from .llm_creator import *


def get_llm_node(*, provider: str, model: str, api_key: str, config: AgentConfigSchema | None = None) -> BaseChatModel | Any:
    logger.trace('[llm_factory.py] [ ] [get_llm_node] Enter')
    logger.info(f"[get_llm_node] Trying to get {model} from {provider}...")
    if not provider.strip() or not model.strip():
        raise ValueError(f"Unsupported LLM service type: {provider}: {model}")

    if provider  in ("ollama:local", "ollama"):
        ollama_model = get_ollama_model(model, api_key, BASE_URL.get(provider), config)
        return ollama_model
    elif provider == "openai":
        openai_model = get_openai_model(model, api_key, BASE_URL.get(provider), config)
        return openai_model
    elif provider == "deepseek":
        qianfan_model = get_deepseek_model(model, api_key, BASE_URL.get(provider), config)
        return qianfan_model
    elif provider == "moonshot":
        moonshot_model = get_moonshot_model(model, api_key, BASE_URL.get(provider), config)
        return moonshot_model
    elif provider == "xiaomimimo":
        openai_model = get_xiaomi_model(model, api_key, BASE_URL.get(provider), config)
        return openai_model
    elif provider == "google":
        raise ValueError(f"LLM provider: {provider} is Unsupported at now.")
        google_model = get_google_model(model, api_key, BASE_URL.get(provider), config)
        return google_model
    elif provider == "qianfan":
        raise ValueError(f"LLM provider: {provider} is Unsupported at now.")
        qianfan_model = get_qianfan_model(model, api_key, BASE_URL.get(provider), config)
        return qianfan_model
    elif provider.startswith("custom-"):
        _, p_type, p_id = provider.split('-', 2)
        if p_type == "openai":
            custom_model = get_openai_model(model, api_key, BASE_URL.get(provider), config)
        else:
            raise ProviderNoFound(f"Unsupport provider type: {p_type}.", provider=p_id)
        return custom_model
    else:
        logger.error(f"[get_llm_node] Failed to get {model} from {provider}...")
        raise ValueError(f"Unsupported LLM service type: {provider}")
    