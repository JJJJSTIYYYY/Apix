from typing import Any, NotRequired, TypedDict


# Basic type for 
class ApixIdentity(TypedDict):
    id: str
    platform: NotRequired[str]
    conversation_id: NotRequired[str]
    associated_account: NotRequired[dict]


# Data schema for apix system entry point
class ApixEntryDataSchema(TypedDict):
    action: str
    data: Any