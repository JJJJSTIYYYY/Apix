from apix.agent.core.bot.profile import (
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
)

PROVIDER = ProviderProfile(
    "gemini", "gemini", "https://generativelanguage.googleapis.com/v1beta"
)
MODELS = tuple(
    ModelProfile(
        pattern,
        reasoning=ReasoningProfile(
            mode="always",
            effort_values=efforts,
            effort=RequestField(
                ("generationConfig", "thinkingConfig", "thinkingLevel")
            ),
            replay="always",
        ),
        request_options={
            "generationConfig": {"thinkingConfig": {"includeThoughts": True}}
        },
    )
    for patterns, efforts in (
        (("gemini-3-pro", "gemini-3-pro-preview"), ("low", "high")),
        (("gemini-3.1-pro", "gemini-3.1-pro-preview"), ("low", "medium", "high")),
        (
            (
                "gemini-3-flash",
                "gemini-3-flash-preview",
                "gemini-3.1-flash-lite",
                "gemini-3.1-flash-lite-preview",
            ),
            ("minimal", "low", "medium", "high"),
        ),
    )
    for pattern in patterns
)
