from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class InvocationPolicy:
    use_server_state: bool = False
    store: bool = False
    include_usage: bool = True
    timeout: float | None = None
    max_retries: int | None = None
    request_options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.use_server_state or self.store:
            raise ValueError("Apix requires client-managed context and store=False")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.max_retries is not None and self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
