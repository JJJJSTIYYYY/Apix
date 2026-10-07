"""Resolve invocation controls, then assemble the provider request once."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from apix.agent.core.bot.codec.base import BaseCodec, function_schemas, read_path
from apix.agent.core.bot.profile import InvocationPolicy, ModelProfile


def merge_options(*layers: Mapping[str, Any]) -> dict[str, Any]:
    result = {}
    for layer in layers:
        if not isinstance(layer, Mapping):
            raise TypeError("request_options and extra_body must be mappings")
        for key, value in layer.items():
            result[key] = (
                merge_options(result[key], value)
                if isinstance(result.get(key), Mapping) and isinstance(value, Mapping)
                else deepcopy(value)
            )
    return result


def set_path(target: dict, path: tuple, value: Any) -> None:
    for key in path[:-1]:
        child = target.setdefault(key, {})
        if not isinstance(child, dict):
            raise TypeError(f"request path conflicts at {key!r}")
        target = child
    target[path[-1]] = deepcopy(value)


RESERVED_OPTIONS = frozenset(
    {
        "model",
        "messages",
        "input",
        "contents",
        "system",
        "systemInstruction",
        "instructions",
        "stream",
        "tools",
        "tool_choice",
        "toolConfig",
        "parallel_tool_calls",
        "store",
        "previous_response_id",
        "previousResponseId",
        "conversation",
        "conversation_id",
        "cachedContent",
        "cached_content",
        "thread_id",
        "session_id",
        "background",
        "context_management",
        "extra_body",
        "extra_query",
        "extra_headers",
        "timeout",
        "builtin_tools",
        "provider_tools",
        "web_search",
        "web_search_options",
        "enable_search",
        "search_parameters",
        "file_search",
        "computer_use",
        "code_interpreter",
        "mcp",
    }
)

REASONING_CONTROLS = (
    ("reasoning_effort",),
    ("reasoning", "effort"),
    ("reasoning", "enabled"),
    ("output_config", "effort"),
    ("thinking", "type"),
    ("enable_thinking",),
    ("think",),
    ("generationConfig", "thinkingConfig", "thinkingLevel"),
)


def build_request(
    *,
    model: str,
    profile: ModelProfile,
    codec: BaseCodec,
    messages: list,
    tools: list[dict],
    reasoning: bool | None,
    reasoning_effort: str | None,
    tool_choice: str | None,
    parallel_tool_calls: bool | None,
    policy: InvocationPolicy,
    request_options: Mapping | None = None,
    extra_body: Mapping | None = None,
    stream: bool = False,
) -> dict:
    options = merge_options(
        profile.request_options,
        policy.request_options,
        {} if request_options is None else request_options,
        {} if extra_body is None else extra_body,
    )
    forbidden = RESERVED_OPTIONS.intersection(options)
    if forbidden:
        raise ValueError(
            f"controlled context forbids request overrides: {', '.join(sorted(forbidden))}"
        )
    if reasoning is not None and not isinstance(reasoning, bool):
        raise TypeError("reasoning must be bool or None")
    if reasoning_effort is not None and not isinstance(reasoning_effort, str):
        raise TypeError("reasoning_effort must be a string or None")
    reason = profile.reasoning
    enabled = reason.mode != "none" if reasoning is None else reasoning
    if reason.mode == "none" and (enabled or reasoning_effort is not None):
        raise ValueError("this model does not support reasoning")
    if reason.mode == "always" and not enabled:
        raise ValueError("reasoning cannot be disabled for this model")
    if (
        not enabled
        and reasoning_effort is not None
        and not reason.effort_without_reasoning
    ):
        raise ValueError("reasoning_effort cannot be used with reasoning disabled")
    effort = None
    if reasoning_effort is not None:
        effort = reason.effort_map.get(reasoning_effort, reasoning_effort)
        if effort not in reason.effort_values or reason.effort is None:
            raise ValueError(
                f"model does not support reasoning effort {reasoning_effort!r}"
            )
        if effort == "none":
            if reason.mode == "always":
                raise ValueError("reasoning cannot be disabled for this model")
            if reasoning is True:
                raise ValueError(
                    "reasoning=True conflicts with reasoning_effort='none'"
                )
            enabled = False
    if reason.mode == "optional" and reason.toggle is None:
        if reason.effort is None:
            raise ValueError("optional reasoning requires a configured request control")
        if not enabled and "none" in reason.effort_values:
            effort = "none"
        elif effort is None:
            raise ValueError("this model requires an explicit reasoning_effort")
    if enabled and reason.stream_only and not stream:
        raise ValueError("this model only supports reasoning in streaming calls")
    if (
        effort is not None
        and reason.effort is not None
        and reason.effort.path
        == ("generationConfig", "thinkingConfig", "thinkingLevel")
        and read_path(options, ("generationConfig", "thinkingConfig", "thinkingBudget"))
        is not None
    ):
        raise ValueError(
            "thinkingBudget cannot be combined with this model's thinkingLevel"
        )
    controls = [
        control.path
        for control in (reason.toggle, reason.effort)
        if control is not None
    ]
    for path in (*REASONING_CONTROLS, *controls):
        if read_path(options, path) is not None:
            raise ValueError(
                "reasoning controls must use the explicit invocation parameters"
            )
    functions = function_schemas(tools)
    if functions and not profile.tools.supported:
        raise ValueError("this model does not support function tools")
    effective_choice = "auto" if tool_choice is None and functions else tool_choice
    if effective_choice is not None:
        tool_choice = effective_choice
        if not isinstance(tool_choice, str) or not tool_choice:
            raise TypeError("tool_choice must be a mode or function name")
        choice_mode = (
            tool_choice if tool_choice in ("auto", "none", "required") else "named"
        )
        allowed = (
            profile.tools.reasoning_choice_modes
            if enabled and profile.tools.reasoning_choice_modes is not None
            else profile.tools.choice_modes
        )
        if choice_mode not in allowed:
            raise ValueError(
                f"tool_choice {choice_mode!r} is not supported in this reasoning mode"
            )
        if tool_choice != "none" and not functions:
            raise ValueError("tool_choice requires function tools")
        if choice_mode == "named" and tool_choice not in {
            fn["name"] for fn in functions
        }:
            raise ValueError(f"tool_choice names an unbound function: {tool_choice!r}")
    if parallel_tool_calls is not None and not isinstance(parallel_tool_calls, bool):
        raise TypeError("parallel_tool_calls must be bool or None")
    if parallel_tool_calls and not profile.tools.parallel:
        raise ValueError("this model does not support parallel function calls")
    if functions and not profile.tools.parallel:
        parallel_tool_calls = False
    if parallel_tool_calls is not None and not functions:
        raise ValueError("parallel_tool_calls requires function tools")
    request = options
    request.update(
        codec.encode_request(messages, tools, tool_choice, parallel_tool_calls)
    )
    style = profile.api_style
    if style != "generate_content":
        request.update(model=model, stream=stream)
    if style == "responses":
        request["store"] = False
        if enabled and reason.replay != "never":
            include = request.setdefault("include", [])
            if not isinstance(include, list):
                raise TypeError("include must be a list")
            if "reasoning.encrypted_content" not in include:
                include.append("reasoning.encrypted_content")
    elif style == "chat_completions" and stream and policy.include_usage:
        request.setdefault("stream_options", {})["include_usage"] = True
    elif style == "messages":
        request.setdefault("max_tokens", 4096)
    if reason.mode != "none" and reason.toggle is not None:
        set_path(
            request,
            reason.toggle.path,
            reason.toggle.enabled if enabled else reason.toggle.disabled,
        )
    if effort is not None:
        set_path(request, reason.effort.path, effort)
    return request
