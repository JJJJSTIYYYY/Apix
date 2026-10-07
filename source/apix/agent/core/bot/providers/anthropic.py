from apix.agent.core.bot.profile import (
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
)

PROVIDER = ProviderProfile("anthropic", "anthropic", "https://api.anthropic.com/v1")
MODELS = tuple(
    ModelProfile(
        pattern,
        reasoning=ReasoningProfile(
            mode="optional",
            toggle=RequestField(("thinking", "type"), "adaptive", "disabled"),
            effort_values=efforts,
            effort=RequestField(("output_config", "effort")),
            replay="always",
            effort_without_reasoning=True,
        ),
    )
    for pattern, efforts in (
        ("claude-opus-4-6*", ("low", "medium", "high", "max")),
        ("claude-sonnet-4-6*", ("low", "medium", "high", "max")),
        ("claude-opus-4-7*", ("low", "medium", "high", "xhigh", "max")),
        ("claude-opus-4-8*", ("low", "medium", "high", "xhigh", "max")),
    )
)
