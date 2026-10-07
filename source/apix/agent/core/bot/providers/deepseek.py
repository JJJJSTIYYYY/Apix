from apix.agent.core.bot.profile import (
    MessageProfile,
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
    ToolProfile,
)

PROVIDER = ProviderProfile("deepseek", endpoint="https://api.deepseek.com/v1")
MODELS = tuple(
    ModelProfile(
        pattern,
        "chat_completions",
        reasoning=ReasoningProfile(
            mode="optional",
            effort_values=("none", "low", "high", "max"),
            effort_map={
                "minimal": "low",
                "medium": "high",
                "xhigh": "high",
                "ultra": "max",
            },
            toggle=RequestField(("thinking", "type"), "enabled", "disabled"),
            effort=RequestField(("reasoning_effort",)),
            replay="when_tools",
        ),
        tools=ToolProfile(reasoning_choice_modes=("auto", "none")),
        messages=MessageProfile(supports_name=True),
    )
    for pattern in ("deepseek-v4*", "deepseek-flash")
) + (
    ModelProfile(
        "deepseek-reasoner",
        reasoning=ReasoningProfile(mode="always", replay="when_tools"),
        tools=ToolProfile(reasoning_choice_modes=("auto", "none")),
    ),
    ModelProfile("deepseek-chat", messages=MessageProfile(supports_name=True)),
)
