from typing import Any

from langchain.chat_models import BaseChatModel

from apix_agent.commons.type_def import AgentConfigSchema, ProviderNotFound
from apix_agent.commons.logger import logger
from apix_agent.global_config import BASE_URL
from .llm_creator import *


def get_llm_node(*, provider: str, model: str, api_key: str, config: AgentConfigSchema | None = None) -> BaseChatModel | Any:
    logger.trace()
    logger.info(f"Trying to get {model} from {provider}...")
    if not provider.strip() or not model.strip():
        raise ValueError(f"Unsupported LLM service type: {provider}: {model}")

    llm_model = None
    if provider  in ("ollama:local", "ollama"):
        llm_model = get_ollama_model(model, api_key, BASE_URL.get(provider), config)
    elif provider == "openai":
        llm_model = get_openai_model(model, api_key, BASE_URL.get(provider), config)
    elif provider == "deepseek":
        llm_model = get_deepseek_model(model, api_key, BASE_URL.get(provider), config)
    elif provider == "moonshot":
        llm_model = get_moonshot_model(model, api_key, BASE_URL.get(provider), config)
    elif provider == "xiaomimimo":
        llm_model = get_xiaomi_model(model, api_key, BASE_URL.get(provider), config)
    elif provider == "google":
        raise ValueError(f"LLM provider: {provider} is Unsupported at now.")
        llm_model = get_google_model(model, api_key, BASE_URL.get(provider), config)
    elif provider == "qianfan":
        raise ValueError(f"LLM provider: {provider} is Unsupported at now.")
        llm_model = get_qianfan_model(model, api_key, BASE_URL.get(provider), config)
    elif provider.startswith("custom-"):
        _, p_type, p_id = provider.split('-', 2)
        if p_type == "openai":
            llm_model = get_openai_model(model, api_key, BASE_URL.get(provider), config)
        else:
            raise ProviderNotFound(f"Unsupport provider type: {p_type}.", provider=p_id)
    else:
        logger.error(f"Failed to get {model} from {provider}...")
        raise ValueError(f"Unsupported LLM service type: {provider}")
    
    return llm_model
    