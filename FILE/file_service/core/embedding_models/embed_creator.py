import inspect
from langchain_ollama import OllamaEmbeddings


# def _safe_create(cls, fixed_kwargs: dict, extra_config: dict | None = None):
#     """
#     Safely create a third-party object by filtering unsupported keyword arguments.

#     - cls: target class to instantiate
#     - fixed_kwargs: explicitly provided keyword arguments (always trusted)
#     - extra_config: optional extra keyword arguments (may contain unsupported keys)
#     """
#     extra_config = extra_config or {}

#     sig = inspect.signature(cls.__init__)
#     allowed_params = sig.parameters.keys()

#     # Filter extra config based on __init__ signature
#     filtered_extra = {
#         k: v for k, v in extra_config.items()
#         if k in allowed_params
#     }

#     return cls(**fixed_kwargs, **filtered_extra)



# def get_ollama_model(
#     model: str,
#     api_key: str,
#     base_url: str,
#     extra_config: dict | None = None,
# ):
#     return _safe_create(
#         OllamaEmbeddings,
#         fixed_kwargs={
#             "model": model,
#             "api_key": api_key,
#             "base_url": base_url,
#         },
#         extra_config=extra_config,
#     )

def get_ollama_model(
    model: str,
    api_key: str,
    base_url: str,
    config: dict | None = None
):
    """
    Create an Ollama chat model instance.

    Args:
        model: Model name.
        api_key: API key for authentication.
        base_url: Ollama server base URL.
    """
    return OllamaEmbeddings(
        model=model,
        base_url=base_url,
    )