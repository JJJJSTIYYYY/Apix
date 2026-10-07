"""Built-in provider data; no transport implementations belong here."""

from apix.agent.core.bot.profile import (
    ModelProfile,
    ProviderProfile,
    ReasoningProfile,
    RequestField,
    ToolProfile,
)
from apix.agent.core.bot.profile.registry import ProfileRegistry
from apix.agent.core.bot.providers import (
    anthropic,
    deepseek,
    gemini,
    mimo,
    minimax,
    moonshot,
    openai,
    openrouter,
    qwen,
    siliconflow,
    zai,
)


def register_builtins(registry: ProfileRegistry) -> None:
    for module in (
        openai,
        deepseek,
        mimo,
        minimax,
        moonshot,
        zai,
        qwen,
        anthropic,
        gemini,
        openrouter,
        siliconflow,
    ):
        registry.register_provider(
            module.PROVIDER, aliases=("xiaomimimo",) if module is mimo else ()
        )
        for model in module.MODELS:
            registry.register_model(module.PROVIDER.name, model)
    registry.register_provider(
        ProviderProfile("ollama", "ollama", "http://localhost:11434")
    )
    registry.register_model(
        "ollama",
        ModelProfile(
            "*",
            tools=ToolProfile(choice_modes=("auto",)),
        ),
    )
    for pattern in ("qwen3", "qwen3:*"):
        registry.register_model(
            "ollama",
            ModelProfile(
                pattern,
                reasoning=ReasoningProfile(
                    mode="optional",
                    toggle=RequestField(("think",)),
                    replay="always",
                ),
                tools=ToolProfile(choice_modes=("auto",)),
            ),
        )
    for pattern in ("gpt-oss", "gpt-oss:*"):
        registry.register_model(
            "ollama",
            ModelProfile(
                pattern,
                reasoning=ReasoningProfile(
                    mode="always",
                    effort_values=("low", "medium", "high"),
                    effort=RequestField(("think",)),
                    replay="always",
                ),
                tools=ToolProfile(choice_modes=("auto",)),
            ),
        )
