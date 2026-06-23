import json
from pathlib import Path
from typing import Any, Literal

from langchain.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from apix_agent.commons.type_def import AgentConfigSchema, ProviderNotFound
from apix_agent.commons.logger import logger

from .llm_factory import get_llm_node
from apix_agent.global_config import BASE_DIR


test_img_base64 = """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"""


class LlmNodeAdapter:
    """
    Adapter for:
    - OpenAI
    - DeepSeek
    - MoonShot
    - Ollama
    """

    # cache: {(provider, model): bool}
    _vision_cache: dict[tuple[str, str], bool] = {}

    # cache file path
    _cache_file_path = Path(BASE_DIR) / "running_cache" / "vision_cache.json"

    @classmethod
    def _ensure_cache_file(cls):
        """Ensure cache directory and file exist"""
        cls._cache_file_path.parent.mkdir(parents=True, exist_ok=True)
        if not cls._cache_file_path.exists():
            cls._cache_file_path.write_text("{}", encoding="utf-8")

    @classmethod
    def _load_cache_from_file(cls):
        """Load cache from file into memory"""
        cls._ensure_cache_file()
        try:
            data = json.loads(cls._cache_file_path.read_text(encoding="utf-8"))
            for k, v in data.items():
                provider, model = k.split(":", 1)
                cls._vision_cache[(provider, model)] = bool(v)
        except Exception:
            # corrupted file -> reset
            cls._vision_cache = {}

    @classmethod
    def _save_cache_to_file(cls):
        """Persist current memory cache to file"""
        cls._ensure_cache_file()

        data = {
            f"{provider}:{model}": value
            for (provider, model), value in cls._vision_cache.items()
        }

        cls._cache_file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    @classmethod
    def get_atapted_llm_node(
        cls, 
        *, 
        provider: str, 
        model: str, 
        api_key: str, 
        config: AgentConfigSchema | None = None
    ) -> BaseChatModel | Any:
        """
        To adapt different model provider.
        """
        if provider not in ['ollama:local', 'ollama', 'openai', 'deepseek', 'moonshot', 'xiaomimimo'] and not provider.startswith("custom-"):
            raise ProviderNotFound(f"LLM provider: {provider} is Unsupported at now.", provider=provider)
        # if provider == 'deepseek':
        #     # enable_think = bool(config.get("enable_think", False))
        #     # if enable_think: model = 'deepseek-reasoner'
        #     # else: model = 'deepseek-chat'
        #     return get_llm_node(provider=provider, model=model, api_key=api_key, config=config)
        # else:
        #     return get_llm_node(provider=provider, model=model, api_key=api_key, config=config)
        return get_llm_node(provider=provider, model=model, api_key=api_key, config=config)

        
    @classmethod
    async def astream(
        cls,
        llm_node: BaseChatModel | Any,
        *,
        input,
        reasoning: bool = False,
        fall_back_config: AgentConfigSchema = None
    ):
        """
        Unified streaming interface.

        DeepSeek:
            - DOES NOT support reasoning parameter
            - We select model by reasoning flag:
                reasoning=True  -> deepseek-reasoner
                reasoning=False -> deepseek-chat

        DeepSeek-V4:
            - DOES NOT support reasoning parameter
            - We select model by reasoning flag:
                reasoning=True  -> extra_body={"thinking": {"type": "enabled"}}
                reasoning=False -> extra_body={"thinking": {"type": "disabled"}}

        MoonShot:
            - MoonShot's model can not turn think-mode on or off by reasoning parameter

        Other providers:
            - Pass reasoning if supported
        """

        fall_back_provider=fall_back_config.get("models_provider")
        fall_back_model_name=fall_back_config.get("model_name")
        fall_back_api_key=fall_back_config.get("api_key")
        provider = getattr(llm_node, "provider", fall_back_provider)
        model_name = getattr(llm_node, "model_name", fall_back_model_name)
        api_key = getattr(llm_node, "api_key", fall_back_api_key)
        extra_body = getattr(llm_node, "extra_body", {}) or {}
        config = fall_back_config.copy()
        config['enable_think'] = reasoning

        logger.warning(f"Get attr: provider={provider}, model_name={model_name}.")

        if provider == "deepseek" or (
            model_name and model_name.startswith("deepseek")
        ):
            # If current model not match → rebuild
            if ((extra_body.get("thinking", {}) or {}).get("type", "") == 'enabled') != reasoning:
                llm_node = cls.get_atapted_llm_node(
                    provider=provider,
                    model=model_name,
                    api_key=api_key,
                    config=config,
                )

            async for chunk in llm_node.astream(input):
                yield chunk
            return

        if provider == "xiaomimimo" or (
            model_name and model_name.startswith("mimo")
        ):
            # If current model not match → rebuild
            if ((extra_body.get("thinking", {}) or {}).get("type", "") == 'enabled') != reasoning:
                llm_node = cls.get_atapted_llm_node(
                    provider=provider,
                    model=model_name,
                    api_key=api_key,
                    config=config,
                )

            async for chunk in llm_node.astream(input):
                yield chunk
            return
        
        if provider == "moonshot" or (
            model_name and model_name.startswith(("moonshot", "kimi"))
        ):
            async for chunk in llm_node.astream(input):
                yield chunk
            return

        try:
            async for chunk in llm_node.astream(
                input,
                reasoning=reasoning
            ):
                yield chunk
        except TypeError:
            # Provider doesn't support reasoning parameter
            async for chunk in llm_node.astream(input):
                yield chunk


    @classmethod
    async def ainvoke(
        cls,
        llm_node: BaseChatModel | Any,
        *,
        input,
        reasoning: bool = False,
        fall_back_config: AgentConfigSchema = None
    ):
        """
        Unified non-stream invoke interface.

        DeepSeek:
            - DOES NOT support reasoning parameter
            - We select model by reasoning flag:
                reasoning=True  -> deepseek-reasoner
                reasoning=False -> deepseek-chat

        DeepSeek-V4:
            - DOES NOT support reasoning parameter
            - We select model by reasoning flag:
                reasoning=True  -> extra_body={"thinking": {"type": "enabled"}}
                reasoning=False -> extra_body={"thinking": {"type": "disabled"}}

        MoonShot:
            - MoonShot's model can not turn think-mode on or off by reasoning parameter

        Other providers:
            - Keep official LangChain behavior
        """

        fall_back_provider=fall_back_config.get("models_provider")
        fall_back_model_name=fall_back_config.get("model_name")
        fall_back_api_key=fall_back_config.get("api_key")
        provider = getattr(llm_node, "provider", fall_back_provider)
        model_name = getattr(llm_node, "model_name", fall_back_model_name)
        api_key = getattr(llm_node, "api_key", fall_back_api_key)
        extra_body = getattr(llm_node, "extra_body", {}) or {}
        config = fall_back_config.copy()
        config['enable_think'] = reasoning

        logger.warning(f"Get attr: provider={provider}, model_name={model_name}.")

        if provider == "deepseek" or (
            model_name and model_name.startswith("deepseek")
        ):
            # If current model not match → rebuild
            if ((extra_body.get("thinking", {}) or {}).get("type", "") == 'enabled') != reasoning:
                llm_node = cls.get_atapted_llm_node(
                    provider="deepseek",
                    model=model_name,
                    api_key=api_key,
                    config=config,
                )

            return await llm_node.ainvoke(input)

        if provider == "xiaomimimo" or (
            model_name and model_name.startswith("mimo")
        ):
            # If current model not match → rebuild
            if ((extra_body.get("thinking", {}) or {}).get("type", "") == 'enabled') != reasoning:
                llm_node = cls.get_atapted_llm_node(
                    provider="xiaomimimo",
                    model=model_name,
                    api_key=api_key,
                    config=config,
                )

            return await llm_node.ainvoke(input)

        try:
            return await llm_node.ainvoke(
                input,
                reasoning=reasoning,
            )
        except TypeError:
            # Provider doesn't support reasoning parameter
            return await llm_node.ainvoke(input)
        


    @classmethod
    def filter_empty_content():
        pass

        

    @classmethod
    async def is_vision_model(
        cls,
        *,
        provider: str, 
        model_name: str, 
        api_key: str, 
        config: AgentConfigSchema | None = None
    ) -> bool:
        """
        Detect whether the model has vision capability using probe strategy.

        Strategy:
        1. Check local cache first
        2. If cache empty -> try load from file
        3. If still not found -> probe
        4. Save result to memory + file
        """

        cache_key = (provider, model_name)

        # 1. check memory cache
        if not cls._vision_cache:
            cls._load_cache_from_file()

        if cache_key in cls._vision_cache:
            return cls._vision_cache[cache_key]

        # 3. build llm node
        llm_node = cls.get_atapted_llm_node(
            provider=provider,
            model=model_name,
            api_key=api_key,
            config=config
        )

        # 4. prepare probe
        prompt = (
            "You are given an image.\n"
            "The image contains only text.\n"
            "Extract the exact text from the image.\n"
            "Return only the text. No explanation."
        )

        messages = [
            SystemMessage(content="You are a precise OCR assistant."),
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "base64": test_img_base64,
                        "mime_type": "image/png",
                    },
                ]
            ),
        ]

        result_flag = False

        try:
            resp: AIMessage = await cls.ainvoke(
                llm_node,
                input=messages,
                reasoning=False,
                fall_back_config=config
            )

            content = resp.content

            result = content.strip().lower()
            logger.debug(f"provider={provider}, model={model_name}, test_resp_content={content}")
            if "test" in result and "vision" in result:
                result_flag = True

        except Exception as e:
            error_msg = str(e).lower()
            logger.warning(f"Error: {type(e)}: {str(e)}")

            # 5. detect auth error -> DO NOT cache
            if any(keyword in error_msg for keyword in [
                "unauthorized",
                "authentication",
                "invalid api key",
                "api key",
                "permission denied",
                "401"
            ]):
                return False  # do not write cache

            # other errors -> treat as no vision
            result_flag = False

        # 6. update cache (memory + file)
        cls._vision_cache[cache_key] = result_flag
        cls._save_cache_to_file()

        return result_flag
    
    @classmethod
    def guess_exception_type(cls, err: Exception|str) -> Literal['token_exceed', 'rate_limit', 'others']:
        if isinstance(err, Exception):
            err = str(err)
        err = err.lower()

        rate_limit_keywords = {
            "too many requests",
            "rate limit",
            "quota",
            "exceeded your current quota",
            "requests per min",
            "tokens per min",
            "rpm",
            "tpm",
            "concurrency"
        }

        if any(kw in err for kw in rate_limit_keywords):
            return "rate_limit"
        
        token_exceed_keywords = {
            "maximum context length",
            "context length exceeded",
            "prompt too long",
            "input too long",
            "request too large",
            "too many tokens",
            "reduce the length",
            "reduce tokens",
            "max tokens",
            "token limit",
            "message too long"
        }

        if any(kw in err for kw in token_exceed_keywords):
            return "token_exceed"
        
        rate_limit_object_set = {"rate", "concurrency", "rpm", "tpm"}
        rate_limit_action_set = {"exceed", "limit", "reach"}

        if any(o in err for o in rate_limit_object_set) and any(a in err for a in rate_limit_action_set):
            return "rate_limit"
        
        token_exceed_object_set = {"token", "context", "prompt", "input"}
        token_exceed_action_set = {"exceed", "long", "limit", "large"}

        if any(o in err for o in token_exceed_object_set) and any(a in err for a in token_exceed_action_set):
            return "token_exceed"
        
        return "others"