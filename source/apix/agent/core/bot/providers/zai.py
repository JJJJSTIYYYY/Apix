from apix.agent.core.bot.profile import (
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
    ToolProfile,
)

PROVIDER = ProviderProfile("zai", endpoint="https://api.z.ai/api/paas/v4")
MODELS = (
    (ModelProfile("*", tools=ToolProfile(choice_modes=("auto",))),)
    + tuple(
        ModelProfile(
            pattern,
            reasoning=ReasoningProfile(
                mode="optional",
                toggle=RequestField(("thinking", "type"), "enabled", "disabled"),
                replay="when_tools",
            ),
            tools=ToolProfile(choice_modes=("auto",)),
        )
        for pattern in ("glm-4.5*", "glm-4.6*", "glm-4.7*", "glm-5", "glm-5.1*")
    )
    + (
        ModelProfile(
            "glm-5.2*",
            reasoning=ReasoningProfile(
                mode="optional",
                replay="when_tools",
                toggle=RequestField(("thinking", "type"), "enabled", "disabled"),
                effort_values=("none", "high", "max"),
                effort_map={
                    "minimal": "none",
                    "low": "high",
                    "medium": "high",
                    "xhigh": "max",
                },
                effort=RequestField(("reasoning_effort",)),
            ),
            tools=ToolProfile(choice_modes=("auto",)),
        ),
        ModelProfile(
            "glm-5.3*",
            reasoning=ReasoningProfile(
                mode="always",
                replay="when_tools",
                effort_values=("low", "high", "max"),
                effort=RequestField(("reasoning_effort",)),
            ),
            tools=ToolProfile(choice_modes=("auto",)),
        ),
    )
)
