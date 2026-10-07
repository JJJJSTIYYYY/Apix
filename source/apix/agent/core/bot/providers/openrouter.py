from dataclasses import replace

from apix.agent.core.bot.profile import (
    OPENAI_CHAT_SCHEMA,
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    ResponseSchema,
)

PROVIDER = ProviderProfile("openrouter", endpoint="https://openrouter.ai/api/v1")
SCHEMA = ResponseSchema(
    complete=replace(
        OPENAI_CHAT_SCHEMA.complete,
        reasoning=("choices", 0, "message", "reasoning"),
        extensions={
            "reasoning_details": ("choices", 0, "message", "reasoning_details")
        },
    ),
    stream=replace(
        OPENAI_CHAT_SCHEMA.stream,
        reasoning=("choices", 0, "delta", "reasoning"),
        extensions={"reasoning_details": ("choices", 0, "delta", "reasoning_details")},
        extension_stream_fields={
            "reasoning_details": ("text", "summary", "data", "signature")
        },
    ),
)
# Routed models need their own capability profile; only the wire format is shared.
MODELS = (
    ModelProfile(
        "*", reasoning=ReasoningProfile(replay="always"), response_schema=SCHEMA
    ),
)
