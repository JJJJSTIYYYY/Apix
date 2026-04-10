from core.commons.logger import logger
from global_config import BASE_URL


def get_embed_model(*, provider: str, model: str, api_key: str, extra_config: dict | None = None):
    logger.trace('[embed_factory.py] [ ] [get_embed_model] Enter')
    logger.info(f"[get_embed_model] Trying to get {model} from {provider}...")
    if not provider.strip() or not model.strip():
        raise ValueError(f"Unsupported LLM service type: {provider}: {model}")

    if provider  in ("ollama:local", "ollama"):
        from .embed_creator import get_ollama_model
        ollama_model = get_ollama_model(model, api_key, BASE_URL.get(provider), extra_config)
        return ollama_model
    else:
        logger.error(f"[get_embed_model] Failed to get {model} from {provider}...")
        raise ValueError(f"Unsupported LLM service type: {provider}")
    