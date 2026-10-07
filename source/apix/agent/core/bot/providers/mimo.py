from apix.agent.core.bot.profile import (
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
)

PROVIDER = ProviderProfile("mimo", endpoint="https://api.xiaomimimo.com/v1")
MODELS = tuple(
    ModelProfile(
        pattern,
        reasoning=ReasoningProfile(
            mode="optional",
            toggle=RequestField(("thinking", "type"), "enabled", "disabled"),
            replay="when_tools",
        ),
    )
    for pattern in ("mimo-v2.5", "mimo-v2.5-pro")
)
