from typing import Any

from langchain.chat_models import BaseChatModel

from apix_agent.commons.logger import logger
from apix_agent.global_config import BASE_URL


def get_llm_node(*, provider: str, model: str, api_key: str, config: dict | None = None) -> BaseChatModel | Any:
    logger.trace('[llm_factory.py] [ ] [get_llm_node] Enter')
    logger.info(f"[get_llm_node] Trying to get {model} from {provider}...")
    if not provider.strip() or not model.strip():
        raise ValueError(f"Unsupported LLM service type: {provider}: {model}")

    if provider  in ("ollama:local", "ollama"):
        from .llm_creator import get_ollama_model
        ollama_model = get_ollama_model(model, api_key, BASE_URL.get(provider), config)
        return ollama_model
    elif provider == "openai":
        from .llm_creator import get_openai_model
        openai_model = get_openai_model(model, api_key, BASE_URL.get(provider)+'/v1', config)
        return openai_model
    elif provider == "deepseek":
        from .llm_creator import get_deepseek_model
        qianfan_model = get_deepseek_model(model, api_key, BASE_URL.get(provider)+'/v1', config)
        return qianfan_model
    elif provider == "moonshot":
        from .llm_creator import get_moonshot_model
        moonshot_model = get_moonshot_model(model, api_key, BASE_URL.get(provider)+'/v1', config)
        return moonshot_model
    elif provider == "google":
        raise ValueError(f"LLM provider: {provider} is Unsupported at now.")
        from .llm_creator import get_google_model
        google_model = get_google_model(model, api_key, BASE_URL.get(provider), config)
        return google_model
    elif provider == "qianfan":
        raise ValueError(f"LLM provider: {provider} is Unsupported at now.")
        from .llm_creator import get_qianfan_model
        qianfan_model = get_qianfan_model(model, api_key, BASE_URL.get(provider), config)
        return qianfan_model
    else:
        logger.error(f"[get_llm_node] Failed to get {model} from {provider}...")
        raise ValueError(f"Unsupported LLM service type: {provider}")
    