from apix.agent.core.bot.profile import (
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
    ToolProfile,
)

PROVIDER = ProviderProfile("moonshot", endpoint="https://api.moonshot.cn/v1")
MODELS = (
    ModelProfile(
        "kimi-k2.6*",
        reasoning=ReasoningProfile(
            mode="optional",
            toggle=RequestField(("thinking", "type"), "enabled", "disabled"),
            replay="always",
        ),
        tools=ToolProfile(reasoning_choice_modes=("auto", "none")),
    ),
    ModelProfile(
        "kimi-k2.5*",
        reasoning=ReasoningProfile(
            mode="optional",
            replay="always",
            toggle=RequestField(("thinking", "type"), "enabled", "disabled"),
        ),
        tools=ToolProfile(reasoning_choice_modes=("auto", "none")),
    ),
    ModelProfile(
        "kimi-k2-thinking*",
        reasoning=ReasoningProfile(mode="always", replay="always"),
        tools=ToolProfile(reasoning_choice_modes=("auto", "none")),
    ),
    ModelProfile(
        "kimi-k2.7-code*",
        reasoning=ReasoningProfile(mode="always", replay="always"),
        tools=ToolProfile(reasoning_choice_modes=("auto", "none")),
    ),
    ModelProfile(
        "kimi-k3*",
        reasoning=ReasoningProfile(
            mode="always",
            replay="always",
            effort_values=("low", "high", "max"),
            effort=RequestField(("reasoning_effort",)),
        ),
        tools=ToolProfile(reasoning_choice_modes=("auto", "none", "required")),
    ),
)
