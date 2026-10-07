from apix.agent.core.bot.profile import (
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
    ToolProfile,
)

PROVIDER = ProviderProfile(
    "qwen", endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
TOOLS = ToolProfile(
    choice_modes=("auto", "none", "named"), reasoning_choice_modes=("auto", "none")
)
MODELS = (
    (ModelProfile("*", tools=TOOLS),)
    + tuple(
        ModelProfile(
            pattern,
            reasoning=ReasoningProfile(
                mode="optional",
                toggle=RequestField(("enable_thinking",)),
                replay="never",
            ),
            tools=TOOLS,
        )
        for pattern in ("qwen3.5-plus*", "qwen3-vl-plus*", "qwen3-vl-flash*")
    )
    + tuple(
        ModelProfile(
            pattern,
            reasoning=ReasoningProfile(
                mode="optional",
                toggle=RequestField(("enable_thinking",)),
                replay="never",
                stream_only=True,
            ),
            tools=TOOLS,
        )
        for pattern in (
            "qwen3-235b-a22b",
            "qwen3-30b-a3b",
            "qwen3-32b",
            "qwen3-14b",
            "qwen3-8b",
            "qwen3-4b",
            "qwen3-1.7b",
            "qwen3-0.6b",
        )
    )
    + tuple(
        ModelProfile(
            pattern,
            reasoning=ReasoningProfile(mode="always", replay="never"),
            tools=TOOLS,
        )
        for pattern in (
            "qwen3-235b-a22b-thinking-2507",
            "qwen3-30b-a3b-thinking-2507",
            "qwen3-next-80b-a3b-thinking",
            "qwen3-vl-235b-a22b-thinking",
            "qwen3-vl-30b-a3b-thinking",
        )
    )
)
