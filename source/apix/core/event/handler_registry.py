from apix.core.event.base import ApixEventHandler
from apix.core.utils.exception import EventHandlerAlreadyRegisteredError


class ApixHandlerRegistry:
    """Event handler registry.
    """

    registry: dict[str, ApixEventHandler] # handler name -> corresponding ApixEventHandler.
    priority_buckets: dict[int, list[str]] # Buckets grouped by handler priority. Within a single bucket, the list preserves the registration order.

    # An empty list means no handler is registered in the registry for this event.
    # None means the cached chain has expired due to a version increment.
    # Use the list index to distinguish different versions.
    cached_chain: dict[str, list[list[str] | None]] # event name mapped to a list of handler name lists (or None) for different versions.

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.registry = {}
        self.priority_buckets = {}
        self.cached_chain = {}
        self._initialized = True


    def get_handlers_chain_for_event(self, event_name: str) -> list[str]:
        pass


    def register_handler(self, handler_entry: ApixEventHandler):
        pass


    def unregister_handler(self, handler_name: str, event_names: list[str] = None):
        pass


    def delete_handler_from_registry(self, handler_name: str, event_names: list[str] = None):
        pass


    def get_handler(self, handler_name: str) -> ApixEventHandler | None:
        pass