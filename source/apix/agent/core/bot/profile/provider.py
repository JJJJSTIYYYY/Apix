from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    name: str
    protocol: str = "openai"
    endpoint: str = ""
    supports_server_state: bool = False
    verification: Literal["verified", "community"] = "community"

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str)
            for value in (self.name, self.protocol, self.endpoint)
        ):
            raise TypeError("provider name, protocol and endpoint must be strings")
        if (
            not self.name.strip()
            or not self.protocol.strip()
            or not self.endpoint.strip()
        ):
            raise ValueError("provider name, protocol and endpoint must be non-empty")
