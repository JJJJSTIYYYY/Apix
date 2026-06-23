import json
from typing import Any

from langchain.messages import AIMessage, AIMessageChunk
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_deepseek import ChatDeepSeek
from langchain_core.language_models import LanguageModelInput

from apix_agent.commons.type_def import AgentConfigSchema
from apix_agent.commons.logger import logger


def get_temperature(config: AgentConfigSchema | None) -> float:
    config = config or {}
    t = config.get("model_temperature", 1)
    if t > 2: t = 2
    elif t < 0: t = 0
    return t


def get_ollama_model(
    model: str,
    api_key: str,
    base_url: str,
    config: AgentConfigSchema | None = None
):
    """
    Create an Ollama chat model instance.

    Args:
        model: Model name.
        api_key: API key for authentication.
        base_url: Ollama server base URL.
    """
    return ChatOllama(
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_retries=3,
        temperature=get_temperature(config)
    )


class PatchedChatOpenAI(ChatOpenAI):
    """
    Fixed OpenAI-compatible protocol model that restores reasoning_content when tool_calls exist.

    This subclass patches the internal `_get_request_payload` method
    to comply with API requirements.
    """

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ):
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )

        if generation_chunk is None:
            return None

        try:
            choices = chunk.get("choices", [])
            if not choices:
                return generation_chunk

            delta = choices[0].get("delta", {})
            reasoning = delta.get("reasoning_content")

            if reasoning:
                msg = generation_chunk.message

                existing = msg.additional_kwargs.get("reasoning_content", "")
                msg.additional_kwargs["reasoning_content"] = existing + reasoning

        except Exception:
            pass

        return generation_chunk

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        # Convert input to messages BEFORE parent payload conversion
        # so we can preserve reasoning_content
        messages = self._convert_input(input_).to_messages()

        # Map index -> reasoning_content
        # Now ALWAYS preserve reasoning_content (not only when tool_calls exist)
        reasoning_content_map: dict[int, str] = {}

        for i, msg in enumerate(messages):
            if isinstance(msg, (AIMessage, AIMessageChunk)):
                reasoning = msg.additional_kwargs.get("reasoning_content")

                # Always store reasoning_content if exists
                if reasoning:
                    reasoning_content_map[i] = reasoning
                elif isinstance(self.extra_body, dict) and (self.extra_body.get("thinking", {}) or {}).get("type", "enabled") != 'disabled':
                    reasoning_content_map[i] = '...'

        # Call original implementation
        payload = super()._get_request_payload(
            input_,
            stop=stop,
            **kwargs,
        )

        # Restore reasoning_content into ALL assistant messages
        if "messages" in payload and reasoning_content_map:
            for i, message in enumerate(payload["messages"]):
                if (
                    i in reasoning_content_map
                    and message.get("role") == "assistant"
                ):
                    message["reasoning_content"] = reasoning_content_map[i]

        # DeepSeek-specific formatting adjustments
        for message in payload.get("messages", []):
            # Tool content must be JSON string
            if message.get("role") == "tool" and isinstance(
                message.get("content"), list
            ):
                message["content"] = json.dumps(message["content"])

            # Assistant content must be string
            elif message.get("role") == "assistant" and isinstance(
                message.get("content"), list
            ):
                text_parts = [
                    block.get("text", "")
                    for block in message["content"]
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                message["content"] = "".join(text_parts) if text_parts else ""

        return payload


def get_openai_model(
    model: str,
    api_key: str,
    base_url: str,
    config: AgentConfigSchema | None = None
):
    """
    Create an OpenAI chat model instance.

    Args:
        model: Model name.
        api_key: API key for authentication.
        base_url: OpenAI-compatible base URL.
    """
    # enable_think = config.get("enable_think", False)
    if config.get("keep_tools_message"):
        return PatchedChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_retries=3,
            use_responses_api=False,
            temperature=get_temperature(config)
        )
    
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_retries=3,
        use_responses_api=False,
        temperature=get_temperature(config)
    )


def get_google_model(
    model: str,
    api_key: str,
    base_url: str,
    config: AgentConfigSchema | None = None
):
    """
    Create a Google Generative AI chat model instance.

    Args:
        model: Model name.
        api_key: Google API key.
        base_url: Optional base URL (if supported by backend).
    """
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        base_url=base_url,
        max_retries=3,
        temperature=get_temperature(config)
    )

class PatchedChatDeepSeek(ChatDeepSeek):
    """
    Fixed DeepSeek model that restores reasoning_content when tool_calls exist.

    This subclass patches the internal `_get_request_payload` method
    to comply with DeepSeek API requirements.
    """

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        # Convert input to messages BEFORE parent payload conversion
        # so we can preserve reasoning_content
        messages = self._convert_input(input_).to_messages()

        # Map index -> reasoning_content
        # Now ALWAYS preserve reasoning_content (not only when tool_calls exist)
        reasoning_content_map: dict[int, str] = {}

        for i, msg in enumerate(messages):
            if isinstance(msg, (AIMessage, AIMessageChunk)):
                reasoning = msg.additional_kwargs.get("reasoning_content")

                # Always store reasoning_content if exists
                if reasoning:
                    reasoning_content_map[i] = reasoning
                elif isinstance(self.extra_body, dict) and (self.extra_body.get("thinking", {}) or {}).get("type", "enabled") != 'disabled':
                    reasoning_content_map[i] = '...'

        # Call original implementation
        payload = super()._get_request_payload(
            input_,
            stop=stop,
            **kwargs,
        )

        # Restore reasoning_content into ALL assistant messages
        if "messages" in payload and reasoning_content_map:
            for i, message in enumerate(payload["messages"]):
                if (
                    i in reasoning_content_map
                    and message.get("role") == "assistant"
                ):
                    message["reasoning_content"] = reasoning_content_map[i]

        # DeepSeek-specific formatting adjustments
        for message in payload.get("messages", []):
            # Tool content must be JSON string
            if message.get("role") == "tool" and isinstance(
                message.get("content"), list
            ):
                message["content"] = json.dumps(message["content"])

            # Assistant content must be string
            elif message.get("role") == "assistant" and isinstance(
                message.get("content"), list
            ):
                text_parts = [
                    block.get("text", "")
                    for block in message["content"]
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                message["content"] = "".join(text_parts) if text_parts else ""

        return payload

def get_deepseek_model(
    model: str,
    api_key: str,
    base_url: str,
    config: AgentConfigSchema | None = None
):
    """
    Create a deepseek model instance.

    Args:
        model: Model name.
        api_key: Deepseek API key.
        base_url: Optional base URL (if supported by backend).
    """
    enable_think = config.get("enable_think", False)
    return PatchedChatDeepSeek(
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_retries=3,
        extra_body={"thinking": {"type": "enabled" if enable_think else "disabled"}},
        temperature=get_temperature(config)
    )


class PatchedChatMoonshot(ChatOpenAI):

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ):
        # print(f"_convert_chunk_to_generation_chunk called with chunk: {chunk}")
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )

        if generation_chunk is None:
            return None

        try:
            choices = chunk.get("choices", [])
            if not choices:
                return generation_chunk

            delta = choices[0].get("delta", {})
            reasoning = delta.get("reasoning_content")

            if reasoning:
                msg = generation_chunk.message

                existing = msg.additional_kwargs.get("reasoning_content", "")
                msg.additional_kwargs["reasoning_content"] = existing + reasoning

        except Exception:
            pass

        return generation_chunk
    

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        # Convert input to messages BEFORE parent payload conversion
        # so we can preserve reasoning_content
        messages = self._convert_input(input_).to_messages()

        # Map index -> reasoning_content
        # Moonshot requires reasoning_content when tool_calls are present
        reasoning_content_map: dict[int, str] = {}

        for i, msg in enumerate(messages):
            if (
                isinstance(msg, (AIMessage, AIMessageChunk))
                and (msg.tool_calls or msg.invalid_tool_calls)
                and (reasoning := msg.additional_kwargs.get("reasoning_content"))
            ):
                reasoning_content_map[i] = reasoning
            elif (
                isinstance(msg, (AIMessage, AIMessageChunk))
                and (msg.tool_calls or msg.invalid_tool_calls)
                and not msg.content
            ):
                reasoning_content_map[i] = "..."
                logger.warning("Empty message with tool calls.")
            if (
                isinstance(msg, (AIMessage, AIMessageChunk))
                and not msg.content
            ):
                msg.content = '...'

        # Call original implementation
        payload = super()._get_request_payload(
            input_,
            stop=stop,
            **kwargs,
        )

        # Restore reasoning_content into payload assistant messages
        if "messages" in payload and reasoning_content_map:
            for i, message in enumerate(payload["messages"]):
                if (
                    i in reasoning_content_map
                    and message.get("role") == "assistant"
                    and message.get("tool_calls")
                ):
                    message["reasoning_content"] = reasoning_content_map[i]

        # Moonshot-specific formatting adjustments
        for message in payload.get("messages", []):
            # Tool content must be JSON string
            if message.get("role") == "tool" and isinstance(
                message.get("content"), list
            ):
                message["content"] = json.dumps(message["content"])

            # Assistant content must be string
            elif message.get("role") == "assistant" and isinstance(
                message.get("content"), list
            ):
                text_parts = [
                    block.get("text", "")
                    for block in message["content"]
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                message["content"] = "".join(text_parts) if text_parts else ""

        return payload
    

def get_moonshot_model(
    model: str,
    api_key: str,
    base_url: str,
    config: AgentConfigSchema | None = None
):
    """
    Create a Moonshot (月之暗面) chat model instance.

    Args:
        model: Model name.
        api_key: Moonshot API key.
        base_url: Optional base URL (if supported by backend).
    """
    return PatchedChatMoonshot(
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_retries=3,
        use_responses_api=False,
        temperature=get_temperature(config)
    )


class PatchedChatXiaomiMIMO(ChatOpenAI):

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ):
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )

        if generation_chunk is None:
            return None

        try:
            choices = chunk.get("choices", [])
            if not choices:
                return generation_chunk

            delta = choices[0].get("delta", {})
            reasoning = delta.get("reasoning_content")

            if reasoning:
                msg = generation_chunk.message

                existing = msg.additional_kwargs.get("reasoning_content", "")
                msg.additional_kwargs["reasoning_content"] = existing + reasoning

        except Exception:
            pass

        return generation_chunk

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        # Convert input to messages BEFORE parent payload conversion
        # so we can preserve reasoning_content
        messages = self._convert_input(input_).to_messages()

        # Map index -> reasoning_content
        # Now ALWAYS preserve reasoning_content (not only when tool_calls exist)
        reasoning_content_map: dict[int, str] = {}

        for i, msg in enumerate(messages):
            if isinstance(msg, (AIMessage, AIMessageChunk)):
                reasoning = msg.additional_kwargs.get("reasoning_content")

                # Always store reasoning_content if exists
                if reasoning:
                    reasoning_content_map[i] = reasoning

        # Call original implementation
        payload = super()._get_request_payload(
            input_,
            stop=stop,
            **kwargs,
        )

        # Restore reasoning_content into ALL assistant messages
        if "messages" in payload and reasoning_content_map:
            for i, message in enumerate(payload["messages"]):
                if (
                    i in reasoning_content_map
                    and message.get("role") == "assistant"
                ):
                    message["reasoning_content"] = reasoning_content_map[i]

        # DeepSeek-specific formatting adjustments
        for message in payload.get("messages", []):
            # Tool content must be JSON string
            if message.get("role") == "tool" and isinstance(
                message.get("content"), list
            ):
                message["content"] = json.dumps(message["content"])

            # Assistant content must be string
            elif message.get("role") == "assistant" and isinstance(
                message.get("content"), list
            ):
                text_parts = [
                    block.get("text", "")
                    for block in message["content"]
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                message["content"] = "".join(text_parts) if text_parts else ""

        return payload


def get_xiaomi_model(
    model: str,
    api_key: str,
    base_url: str,
    config: AgentConfigSchema | None = None
):
    """
    Create an OpenAI chat model instance.

    Args:
        model: Model name.
        api_key: API key for authentication.
        base_url: OpenAI-compatible base URL.
    """
    enable_think = config.get("enable_think", False)
    return PatchedChatXiaomiMIMO(
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_retries=3,
        use_responses_api=False,
        extra_body={"thinking": {"type": "enabled" if enable_think else "disabled"}},
        temperature=get_temperature(config)
    )