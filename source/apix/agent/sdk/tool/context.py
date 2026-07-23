"""Context for tools."""
from dataclasses import dataclass, field
from typing import Any, Mapping

from apix.agent.sdk.utils.message import ToolCall


@dataclass(frozen=True, slots=True)
class AutoInjection:
    """Mark an Annotated argument as runtime-injected.

    This class contains no runtime data. It is only metadata inspected by
    the :class:`Tool` class when parsing the tool function signature.
    """

    pass


@dataclass(slots=True)
class ToolInjectionState:
    """
    Runtime values available for automatic tool argument injection.
    """

    state: dict[str, Any]
    tool_call: ToolCall

    @property
    def tool_call_id(self) -> str:
        return self.tool_call["call_id"]
    

# injection: Annotated[ToolInjectionState, AutoInjection()]