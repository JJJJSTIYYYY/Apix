from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from fnmatch import fnmatchcase

from apix.agent.core.bot.base import ApiStyle
from apix.agent.core.bot.profile import (
    ANTHROPIC_SCHEMA,
    GEMINI_SCHEMA,
    OPENAI_CHAT_SCHEMA,
    OPENAI_RESPONSES_SCHEMA,
    CustomProfile,
    MessageProfile,
    ModelProfile,
    ProviderProfile,
    ResponseSchema,
)


@dataclass(frozen=True, slots=True)
class ProtocolDefaults:
    api_style: ApiStyle
    messages: MessageProfile
    response_schema: ResponseSchema


PROTOCOL_DEFAULTS = {
    "openai": ProtocolDefaults(
        "chat_completions",
        MessageProfile(roles=("system", "developer", "user", "assistant", "tool")),
        OPENAI_CHAT_SCHEMA,
    ),
    "anthropic": ProtocolDefaults("messages", MessageProfile(), ANTHROPIC_SCHEMA),
    "gemini": ProtocolDefaults("generate_content", MessageProfile(), GEMINI_SCHEMA),
    "ollama": ProtocolDefaults("ollama_chat", MessageProfile(), OPENAI_CHAT_SCHEMA),
}
STYLE_SCHEMAS = {
    "chat_completions": OPENAI_CHAT_SCHEMA,
    "responses": OPENAI_RESPONSES_SCHEMA,
    "messages": ANTHROPIC_SCHEMA,
    "generate_content": GEMINI_SCHEMA,
}
PROTOCOL_STYLES = {
    "openai": ("chat_completions", "responses"),
    "anthropic": ("messages",),
    "gemini": ("generate_content",),
    "ollama": ("ollama_chat",),
}


@dataclass(frozen=True, slots=True)
class ResolvedProfile:
    provider: ProviderProfile
    model: ModelProfile


class ProfileRegistry:
    """Provider-scoped glob matching; exact and more specific names win."""

    def __init__(self) -> None:
        self.providers: dict[str, ProviderProfile] = {}
        self.models: dict[tuple[str, str], ModelProfile] = {}
        self.aliases: dict[str, str] = {}

    def register_provider(
        self, profile: ProviderProfile, *, aliases: tuple[str, ...] = ()
    ) -> None:
        if profile.protocol not in PROTOCOL_DEFAULTS:
            raise ValueError(f"unknown protocol: {profile.protocol!r}")
        self.providers[profile.name] = deepcopy(profile)
        for alias in aliases:
            self.aliases[alias] = profile.name

    def register_model(self, provider: str, profile: ModelProfile) -> None:
        provider = self.resolve_provider(provider).name
        if not profile.pattern:
            raise ValueError("model pattern cannot be empty")
        self.models[provider, profile.pattern] = deepcopy(profile)

    def resolve_provider(self, provider: str) -> ProviderProfile:
        name = self.aliases.get(provider, provider)
        try:
            return deepcopy(self.providers[name])
        except KeyError:
            raise ValueError(f"unknown provider: {provider!r}") from None

    def resolve_model(self, provider: str, model: str) -> ModelProfile:
        name = self.resolve_provider(provider).name
        matches = [
            value
            for (owner, pattern), value in self.models.items()
            if owner == name and fnmatchcase(model.casefold(), pattern.casefold())
        ]
        if not matches:
            return ModelProfile()

        def rank(profile: ModelProfile) -> tuple[bool, int]:
            pattern = profile.pattern
            return (
                pattern.casefold() == model.casefold(),
                sum(char not in "*?[]" for char in pattern),
            )

        matches.sort(key=rank, reverse=True)
        if len(matches) > 1 and rank(matches[0]) == rank(matches[1]):
            raise ValueError(f"ambiguous model profiles for {provider}/{model}")
        return deepcopy(matches[0])

    def resolve(
        self,
        provider: str | ProviderProfile,
        model: str,
        custom: CustomProfile | None = None,
    ) -> ResolvedProfile:
        if isinstance(provider, ProviderProfile):
            destination = deepcopy(provider)
            behavior = (
                self.resolve_model(provider.name, model)
                if provider.name in self.providers
                else ModelProfile()
            )
        else:
            destination = self.resolve_provider(provider)
            behavior = self.resolve_model(provider, model)
        if custom is not None:
            if custom.endpoint is not None:
                destination = replace(destination, endpoint=custom.endpoint)
            if custom.protocol is not None:
                destination = replace(destination, protocol=custom.protocol)
            if custom.model_profile is not None:
                behavior = deepcopy(custom.model_profile)
            overrides = {
                key: deepcopy(getattr(custom, key))
                for key in (
                    "api_style",
                    "reasoning",
                    "tools",
                    "messages",
                    "response_schema",
                    "request_options",
                )
                if getattr(custom, key) is not None
            }
            behavior = replace(behavior, **overrides)
        try:
            defaults = PROTOCOL_DEFAULTS[destination.protocol]
        except KeyError:
            raise ValueError(f"unknown protocol: {destination.protocol!r}") from None
        style = behavior.api_style or defaults.api_style
        if style not in PROTOCOL_STYLES[destination.protocol]:
            raise ValueError(
                f"API style {style!r} is incompatible with {destination.protocol!r}"
            )
        behavior = replace(
            behavior,
            api_style=style,
            messages=deepcopy(behavior.messages or defaults.messages),
            response_schema=deepcopy(
                behavior.response_schema
                or STYLE_SCHEMAS.get(style, defaults.response_schema)
            ),
        )
        return ResolvedProfile(destination, behavior)


REGISTRY = ProfileRegistry()
PROVIDERS = REGISTRY.providers
MODELS = REGISTRY.models


def resolve_provider(provider: str) -> ProviderProfile:
    return REGISTRY.resolve_provider(provider)


def resolve_model(provider: str, model: str) -> ModelProfile:
    return REGISTRY.resolve_model(provider, model)
