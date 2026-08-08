"""Invocation-local graph state, lifecycle, and recovery context."""

from __future__ import annotations

import asyncio
from asyncio import Future
from dataclasses import InitVar, dataclass, field
from typing import Any, Literal, TypeAlias

from apix.core.graph.base import (
    START,
    _copy_state,
    get_auto_merge_keys,
    get_keep_ref_keys,
)
from apix.core.graph.stream import StreamWriter


GraphContextStatus: TypeAlias = Literal[
    "pending",
    "running",
    "failed",
    "aborted",
    "finished",
]

_ALLOWED_STATUS_TRANSITIONS: dict[
    GraphContextStatus,
    frozenset[GraphContextStatus],
] = {
    "pending": frozenset({"running", "failed", "aborted"}),
    "running": frozenset({"failed", "aborted", "finished"}),
    "failed": frozenset({"pending"}),
    "aborted": frozenset({"pending"}),
    "finished": frozenset(),
}


@dataclass(slots=True, eq=False)
class GraphContext:
    """Mutable state and lifecycle context for one recoverable graph run.

    ``state`` is always the most recently committed state snapshot, while
    ``node_name`` identifies the node that should consume that snapshot next.
    A failed or aborted context may be returned to ``pending`` with
    :meth:`resume`; a finished context is terminal.

    Args:
        state_schema: Optional annotated schema used to derive ``AutoMerge``
            and ``KeepRef`` fields. A graph's default schema is adopted when a
            fresh context does not specify one.
    """

    state_schema: InitVar[type | None] = None
    run_id: str | None = field(default=None, init=False)
    state: dict[str, Any] = field(default_factory=dict, init=False)
    node_name: str = field(default=START, init=False)
    steps: int = field(default=0, init=False)
    completion: Future[Any] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    stream_writer: StreamWriter | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _state_schema: type | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _auto_increase_keys: frozenset[str] = field(
        default_factory=frozenset,
        init=False,
        repr=False,
    )
    _keep_ref_keys: frozenset[str] = field(
        default_factory=frozenset,
        init=False,
        repr=False,
    )
    _status: GraphContextStatus = field(
        default="pending",
        init=False,
    )
    _owner_id: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _has_started: bool = field(
        default=False,
        init=False,
        repr=False,
    )
    _has_snapshot: bool = field(
        default=False,
        init=False,
        repr=False,
    )
    _pending_events: int = field(
        default=0,
        init=False,
        repr=False,
    )
    _running_nodes: int = field(
        default=0,
        init=False,
        repr=False,
    )
    _quiescent: asyncio.Event = field(
        default_factory=asyncio.Event,
        init=False,
        repr=False,
    )

    def __post_init__(self, state_schema: type | None) -> None:
        """Derive state behavior and initialize the recovery barrier."""
        self._set_state_schema(state_schema)
        self._quiescent.set()

    @property
    def status(self) -> GraphContextStatus:
        """Return the current lifecycle state."""
        return self._status

    @property
    def is_consumed(self) -> bool:
        """Return whether at least one invocation attempt has started."""
        return self._has_started

    @property
    def is_bound(self) -> bool:
        """Return whether runtime fields identify an invocation attempt."""
        return (
            self.run_id is not None
            and self.completion is not None
            and self.stream_writer is not None
        )

    @property
    def is_active(self) -> bool:
        """Return whether the current attempt is running and incomplete."""
        return (
            self._status == "running"
            and self.is_bound
            and self.completion is not None
            and not self.completion.done()
        )

    def _set_state_schema(self, state_schema: type | None) -> None:
        """Store a state schema and its derived behavior."""
        self._state_schema = state_schema
        self._auto_increase_keys = get_auto_merge_keys(state_schema)
        self._keep_ref_keys = get_keep_ref_keys(state_schema)

    def _adopt_default_state_schema(self, default: "GraphContext") -> None:
        """Adopt the graph default only for a schema-less fresh context."""
        if (
            not self._has_started
            and self._state_schema is None
            and default._state_schema is not None
        ):
            self._set_state_schema(default._state_schema)

    def _transition_to(self, status: GraphContextStatus) -> None:
        """Apply one validated lifecycle transition."""
        if status not in _ALLOWED_STATUS_TRANSITIONS[self._status]:
            raise RuntimeError(
                "Invalid GraphContext status transition: "
                f"{self._status} -> {status}."
            )
        self._status = status

    def _bind(
        self,
        *,
        owner_id: str,
        run_id: str,
        state: dict[str, Any],
        completion: Future[Any],
        stream_writer: StreamWriter,
    ) -> str:
        """Bind a pending context to one invocation attempt.

        The supplied state becomes the new committed snapshot. A fresh context
        starts at ``START``; a resumed context keeps its saved node name and
        cumulative step count.

        Returns:
            The node that should receive the first event of this attempt.
        """
        if self._status != "pending":
            raise RuntimeError(
                "GraphContext must be pending before starting an invocation."
            )
        if self._owner_id is not None and self._owner_id != owner_id:
            raise ValueError(
                "A recovered GraphContext must resume on its original graph."
            )
        if self._pending_events or self._running_nodes:
            raise RuntimeError(
                "GraphContext cannot start while its previous attempt is active."
            )

        self._owner_id = owner_id
        self._has_started = True
        state_snapshot = _copy_state(state, self._keep_ref_keys)

        if not self._has_snapshot:
            self.node_name = START
            self.steps = 0
            self._has_snapshot = True

        self.run_id = run_id
        self.state = state_snapshot
        self.completion = completion
        self.stream_writer = stream_writer
        self._transition_to("running")
        return self.node_name

    def _belongs_to(self, owner_id: str) -> bool:
        """Return whether this context belongs to a particular graph."""
        return self._owner_id == owner_id

    def _is_current_run(self, run_id: str | None) -> bool:
        """Return whether work still belongs to the active attempt."""
        return (
            run_id is not None
            and self.run_id == run_id
            and self._status == "running"
        )

    def _set_next_node(self, node_name: str) -> None:
        """Record which node should consume the current state snapshot."""
        self.node_name = node_name

    def _event_posted(self) -> None:
        """Track one event that must drain before recovery can begin."""
        self._pending_events += 1
        self._refresh_quiescence()

    def _event_received(self) -> None:
        """Mark one previously posted event as consumed by its graph."""
        if self._pending_events > 0:
            self._pending_events -= 1
        self._refresh_quiescence()

    def _node_started(self) -> None:
        """Track one in-flight node execution."""
        self._running_nodes += 1
        self._refresh_quiescence()

    def _node_finished(self) -> None:
        """Mark one in-flight node execution as drained."""
        if self._running_nodes > 0:
            self._running_nodes -= 1
        self._refresh_quiescence()

    def _refresh_quiescence(self) -> None:
        """Synchronize the recovery barrier with in-flight work."""
        if self._pending_events == 0 and self._running_nodes == 0:
            self._quiescent.set()
        else:
            self._quiescent.clear()

    def _snapshot_state(self) -> dict[str, Any]:
        """Copy the committed state using this context's KeepRef policy."""
        return _copy_state(self.state, self._keep_ref_keys)

    def _finish(self) -> None:
        """Resolve a running attempt and enter the terminal finished state."""
        if self._status == "finished":
            return
        if self._status != "running":
            return

        completion = self.completion
        assert completion is not None
        result = None if completion.done() else self._snapshot_state()
        self._transition_to("finished")
        if not completion.done():
            completion.set_result(result)

    def _fail(self, error: Exception) -> None:
        """Fail a pending or running attempt without changing its snapshot."""
        if self._status == "failed":
            return
        if self._status not in ("pending", "running"):
            return

        self._transition_to("failed")
        completion = self.completion
        if completion is not None and not completion.done():
            completion.set_exception(error)

    def abort(self) -> None:
        """Abort a pending or running attempt at its committed snapshot."""
        if self._status == "aborted":
            return
        if self._status not in ("pending", "running"):
            raise RuntimeError(
                f"Cannot abort a GraphContext with status {self._status}."
            )

        completion = self.completion
        result = None
        if completion is not None and not completion.done():
            result = self._snapshot_state()

        self._transition_to("aborted")
        if completion is not None and not completion.done():
            completion.set_result(result)

    async def resume(self) -> None:
        """Wait for stale work to drain and return this context to pending.

        Only failed and aborted contexts are recoverable. The state snapshot,
        next-node snapshot, cumulative steps, schema, and graph ownership are
        retained for the next invocation attempt.
        """
        if self._status not in ("failed", "aborted"):
            raise RuntimeError(
                "Only failed or aborted GraphContext instances can resume."
            )

        await self._quiescent.wait()

        # A concurrent resume may have completed while this task was waiting.
        if self._status not in ("failed", "aborted"):
            raise RuntimeError(
                "GraphContext is no longer available for recovery."
            )

        self._transition_to("pending")
        self.run_id = None
        self.completion = None
        self.stream_writer = None
