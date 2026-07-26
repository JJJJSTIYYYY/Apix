from typing import Any, NotRequired, TypedDict


# Basic type for 
class ApixIdentity(TypedDict):
    id: str
    platform: str
    conversation_uid: str
    associated_account: NotRequired[dict] # platform: uid


# Data schema for apix system entry point
class ApixEntryDataSchema(TypedDict):
    action: str
    data: Any