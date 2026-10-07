from apix.agent.core.bot.profile import (
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
    ToolProfile,
)

PROVIDER = ProviderProfile("siliconflow", endpoint="https://api.siliconflow.cn/v1")
MODELS = tuple(
    ModelProfile(
        pattern,
        reasoning=ReasoningProfile(
            mode="optional",
            toggle=RequestField(("enable_thinking",)),
            effort_values=("high", "max"),
            effort_map={"low": "high", "medium": "high", "xhigh": "max"},
            effort=RequestField(("reasoning_effort",)),
        ),
        tools=ToolProfile(choice_modes=("auto",)),
    )
    for pattern in (
        "deepseek-ai/DeepSeek-V4-Flash",
        "Pro/deepseek-ai/DeepSeek-V4",
        "Pro/zai-org/GLM-5.2",
    )
)
