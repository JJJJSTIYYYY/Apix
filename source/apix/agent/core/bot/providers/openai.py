from dataclasses import replace

from apix.agent.core.bot.profile import (
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
)

PROVIDER = ProviderProfile(
    "openai", endpoint="https://api.openai.com/v1", supports_server_state=True
)
MODELS = tuple(
    ModelProfile(
        pattern,
        "responses",
        reasoning=ReasoningProfile(
            mode="always",
            effort_values=("minimal", "low", "medium", "high"),
            effort=RequestField(("reasoning", "effort")),
            replay="always",
        ),
    )
    for pattern in ("gpt-5", "gpt-5-202*", "gpt-5-mini*", "gpt-5-nano*")
) + (
    ModelProfile(
        "gpt-5.1",
        "responses",
        reasoning=ReasoningProfile(
            mode="optional",
            effort_values=("none", "low", "medium", "high"),
            toggle=RequestField(("reasoning", "effort"), "medium", "none"),
            effort=RequestField(("reasoning", "effort")),
            replay="always",
        ),
    ),
    ModelProfile(
        "gpt-5.2",
        "responses",
        reasoning=ReasoningProfile(
            mode="optional",
            effort_values=("none", "low", "medium", "high", "xhigh"),
            toggle=RequestField(("reasoning", "effort"), "medium", "none"),
            effort=RequestField(("reasoning", "effort")),
            replay="always",
        ),
    ),
    ModelProfile("gpt-5-chat-latest", "responses"),
    ModelProfile("gpt-5.1-chat-latest", "responses"),
    ModelProfile("gpt-5.2-chat-latest", "responses"),
    ModelProfile(
        "gpt-5-pro*",
        "responses",
        reasoning=ReasoningProfile(
            mode="always",
            effort_values=("high",),
            effort=RequestField(("reasoning", "effort")),
            replay="always",
        ),
    ),
    ModelProfile(
        "gpt-5.2-pro*",
        "responses",
        reasoning=ReasoningProfile(
            mode="always",
            effort_values=("medium", "high", "xhigh"),
            effort=RequestField(("reasoning", "effort")),
            replay="always",
        ),
    ),
    ModelProfile(
        "o3",
        "responses",
        reasoning=ReasoningProfile(
            mode="always",
            effort_values=("low", "medium", "high"),
            effort=RequestField(("reasoning", "effort")),
            replay="always",
        ),
    ),
    ModelProfile(
        "o4-mini",
        "responses",
        reasoning=ReasoningProfile(
            mode="always",
            effort_values=("low", "medium", "high"),
            effort=RequestField(("reasoning", "effort")),
            replay="always",
        ),
    ),
)
MODELS += tuple(
    replace(profile, pattern=f"{profile.pattern}-202*")
    for profile in MODELS
    if profile.pattern in ("gpt-5.1", "gpt-5.2", "o3", "o4-mini")
)
MODELS += tuple(
    ModelProfile(
        pattern,
        "responses",
        reasoning=ReasoningProfile(mode="always", replay="always"),
    )
    for pattern in ("gpt-5.1-codex*", "gpt-5.2-codex*", "o3-pro*")
)
