from apix.core.event.base import HandlerEntry
from apix.core.utils.exception import EventHandlerAlreadyRegisteredError


class ApixHandlerRegistry:
    """Event handler registry.
    """

    registry: dict[str, HandlerEntry] # handler name to HandlerEntry item

    # If a cached chain is a empty list, it means no handler registered in registry.
    # If a cached chain is None, it means the former cached chain is expired by version increment.
    cached_chain: dict[str, dict[int, list[str]] | None] # event name to list of handler name with different version.
    current_version: dict[str, int]

    _event_handler_map: dict[str, list[str]] # event name to handler names. Index for cache construction.

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self.registry = {}
        self.cached_chain = {}
        self.current_version = {}
        self._event_handler_map = {}
        self._initialized = True


    def get_handlers_chain_for_event(self, event_name: str) -> list[str]:
        """Find handlers for an event and return handler names in order.

        If the cache is available, return the cached chain.
        """


    def register_handler(self, handler_entry: HandlerEntry):
        """Register a handler into registry.

        Expire those matched chain in cache immediately by version increment.

        This method will:  
            - Append :data:`HandlerEntry.subscribe` and update handler meta in HandlerEntry if a existed handler is registering.
            - Append :data:`HandlerRegistry.registry` if a new handler is registering.
            - Maintain the event to handlers mapping.

        Raises:
            EventHandlerAlreadyRegisteredError: raised when trying to register a handler with a name
                that already exists in :data:`registry`, but with a different callback reference and the existed callback is not None.
        """


    def unregister_handler(self, handler_name: str, event_names: list[str] = None):
        """Unregister a handler.

        Expire those matched chain in cache immediately by version increment if event_names is specified.

        This method will:  
            - Remove handler from :data:`HandlerRegistry.registry` if event_names is not specified.
            - Append event_names to :data:`HandlerEntry.subscribe` if event_names is specified.
            - Append :data:`HandlerRegistry.registry` with a HandlerEntry item with empty callback if the handler is not registered
                and then set the subscribe with event_names.
        """


    def delete_handler(self, handler_name: str):
        """Delete handler from registry.
        
        This method not expire any cache.
        """


    def get_handler(self, handler_name: str) -> HandlerEntry | None:
        """Get HandlerEntry item from registry.

        If this method returns None, the handler may have deleted by :data:`delete_handler`.
        """


    def construct_cached_chain(self, event_name: str):
        """Construct handlers chain for target event.
        """