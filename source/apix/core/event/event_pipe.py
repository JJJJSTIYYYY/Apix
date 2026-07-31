import asyncio
from typing import Any
from abc import ABC, abstractmethod

from apix.config.base_config import EVENT_PIPE_MAX_LEN


EVENT_PIPE = asyncio.Queue(maxsize=EVENT_PIPE_MAX_LEN)


from abc import ABC, abstractmethod


class BaseEventChannel(ABC):
    """Abstract event channel interface.

    Supported channel implementations:
    1. kafka
    2. rabbitMQ
    3. builtin (default asyncio queue)
    """

    @abstractmethod
    async def put(self, event):
        """Push an event into the channel.

        Args:
            event: Event object to be sent.

        Returns:
            None.
        """
        ...

    @abstractmethod
    async def get(self):
        """Retrieve an event from the channel.

        This method blocks until an event is available.

        Returns:
            Event object retrieved from the channel.
        """
        ...

    @abstractmethod
    async def close(self):
        """Close the event channel.

        The implementation should release all related resources,
        such as network connections, consumers, or background tasks.

        Returns:
            None.
        """
        ...

    @abstractmethod
    def empty(self):
        """Check whether the channel is empty.

        Returns:
            bool: True if the channel contains no pending events,
            otherwise False.
        """
        ...

    @abstractmethod
    def get_nowait(self):
        """Retrieve an event without blocking.

        Raises:
            QueueEmpty: If no event is available immediately.

        Returns:
            Event object retrieved from the channel.
        """
        ...

    @abstractmethod
    def qsize(self):
        """Return the number of pending events in the channel.

        Returns:
            int: Number of events currently waiting to be processed.
        """
        ...

    @abstractmethod
    async def task_done(self):
        """Mark an event as processed."""
        ...


# Mailbox
class KafkaChannel(BaseEventChannel):

    pass


class RabbitMQChannel(BaseEventChannel):

    pass


# Builtin
class BuiltinChannel(BaseEventChannel):

    pass


class ApixEventPipe:

    def __init__(self):
        self._event_pipe: dict[str, BaseEventChannel] = {
            "builtin": BuiltinChannel(maxsize=EVENT_PIPE_MAX_LEN),
            "mailbox": BaseEventChannel()
        }