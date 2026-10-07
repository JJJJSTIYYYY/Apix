from dataclasses import replace

from apix.agent.core.bot.profile import (
    OPENAI_CHAT_SCHEMA,
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
    ResponseField,
    ResponseSchema,
)

PROVIDER = ProviderProfile("minimax", endpoint="https://api.minimax.cn/v1")
DETAILS_SCHEMA = ResponseSchema(
    complete=replace(
        OPENAI_CHAT_SCHEMA.complete,
        reasoning=ResponseField(
            ("choices", 0, "message", "reasoning_details"), value=("text",)
        ),
        extensions={
            "reasoning_details": ("choices", 0, "message", "reasoning_details")
        },
    ),
    stream=replace(
        OPENAI_CHAT_SCHEMA.stream,
        reasoning=ResponseField(
            ("choices", 0, "delta", "reasoning_details"), value=("text",)
        ),
        extensions={"reasoning_details": ("choices", 0, "delta", "reasoning_details")},
    ),
)
MODELS = (
    ModelProfile(
        "MiniMax-M2*",
        reasoning=ReasoningProfile(mode="always", replay="always"),
        request_options={"reasoning_split": True},
    ),
    ModelProfile(
        "MiniMax-M3",
        reasoning=ReasoningProfile(
            mode="optional",
            replay="always",
            toggle=RequestField(("thinking", "type"), "adaptive", "disabled"),
        ),
        request_options={"reasoning_split": True},
    ),
    ModelProfile(
        "MiniMax-M3.1-Flash-Preview",
        reasoning=ReasoningProfile(
            mode="always",
            replay="always",
            effort_values=("low", "medium", "high", "xhigh", "max"),
            effort=RequestField(("reasoning_effort",)),
        ),
        request_options={"reasoning_split": True},
    ),
)
