"""Invocation-local graph state, lifecycle, and recovery snapshots."""

from __future__ import annotations

import copy
from asyncio import Future
from dataclasses import InitVar, dataclass, field
import time
from typing import Any, Literal, TypeAlias, TypedDict

from apix.core.graph.base import (
    START,
    _copy_state,
    get_auto_increase_keys,
    get_keep_ref_keys,
)
from apix.core.graph.context.stream_writer import StreamWriter


GraphContextStatus: TypeAlias = Literal[
    "pending",
    "running",
    "failed",
    "aborted",
    "finished",
]


class GraphContextSnapshot(TypedDict):
    """Serializable checkpoint used to construct a new graph context.

    State is deep-copied when the snapshot is taken. Restoring a snapshot
    deep-copies the complete mapping again, including state fields marked with
    :class:`~apix.core.graph.base.KeepRef`.
    """

    timestamp: float
    state: dict[str, Any]
    node_name: str
    steps: int
    namespace: str


_ALLOWED_STATUS_TRANSITIONS: dict[
    GraphContextStatus,
    frozenset[GraphContextStatus],
] = {
    "pending": frozenset({"running", "failed", "aborted"}),
    "running": frozenset({"failed", "aborted", "finished"}),
    "failed": frozenset(),
    "aborted": frozenset(),
    "finished": frozenset(),
}


@dataclass(slots=True, eq=False)
class GraphContext:
    """Mutable state and lifecycle context for one graph invocation attempt.

    ``state`` is the latest committed state, while ``node_name`` identifies the
    node that should consume it next. A context is single-use. After a failed or
    aborted attempt, :meth:`from_snapshot` constructs a new context for retry.

    A context belongs to a graph namespace rather than a specific graph
    instance, so its snapshot may recover on a replacement graph using the same
    namespace.

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
    context_snapshot: GraphContextSnapshot | None = field(
        default=None,
        init=False,
    )
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
    _context_namespace: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _has_started: bool = field(
        default=False,
        init=False,
        repr=False,
    )

    def __post_init__(self, state_schema: type | None) -> None:
        """Derive state behavior from the optional schema."""
        self._set_state_schema(state_schema)

    @classmethod
    def from_snapshot(
        cls,
        snapshot: GraphContextSnapshot | None,
        state_schema: type | None = None,
    ) -> GraphContext:
        """Construct a fresh pending context from a stored checkpoint.

        The entire snapshot is deep-copied without applying ``KeepRef`` rules.
        Runtime-only fields such as ``run_id``, ``completion``, and
        ``stream_writer`` are initialized afresh.

        Args:
            snapshot: Checkpoint previously created by :meth:`take_a_snapshot`.
            state_schema: Optional schema override. When omitted, the context
                may adopt the replacement graph's default schema on invocation.

        Raises:
            RuntimeError: If no recoverable snapshot is supplied.
            TypeError: If the snapshot fields have invalid runtime types.
            ValueError: If the snapshot is missing required fields or contains
                a negative step count.
        """
        if snapshot is None:
            raise RuntimeError("Cannot restore a GraphContext without a snapshot.")
        if not isinstance(snapshot, dict):
            raise TypeError("GraphContext snapshot must be a dict.")

        required_fields = {"state", "node_name", "steps", "namespace"}
        missing_fields = required_fields.difference(snapshot)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(
                f"GraphContext snapshot is missing required fields: {missing}."
            )

        restored: GraphContextSnapshot = copy.deepcopy(snapshot)
        if not isinstance(restored["state"], dict):
            raise TypeError("GraphContext snapshot state must be a dict.")
        if not isinstance(restored["node_name"], str):
            raise TypeError("GraphContext snapshot node_name must be a string.")
        if (
            isinstance(restored["steps"], bool)
            or not isinstance(restored["steps"], int)
        ):
            raise TypeError("GraphContext snapshot steps must be an int.")
        if restored["steps"] < 0:
            raise ValueError("GraphContext snapshot steps cannot be negative.")
        if not isinstance(restored["namespace"], str):
            raise TypeError("GraphContext snapshot namespace must be a string.")

        context = cls(state_schema)
        context.state = restored["state"]
        context.node_name = restored["node_name"]
        context.steps = restored["steps"]
        context._context_namespace = restored["namespace"]
        context.context_snapshot = restored
        return context

    @property
    def status(self) -> GraphContextStatus:
        """Return the current lifecycle state."""
        return self._status

    @property
    def is_consumed(self) -> bool:
        """Return whether this context has started its one invocation."""
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
        self._auto_increase_keys = get_auto_increase_keys(state_schema)
        self._keep_ref_keys = get_keep_ref_keys(state_schema)

    def _adopt_default_state_schema(self, default: GraphContext) -> None:
        """Adopt the graph default only for an unconsumed schema-less context."""
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
        context_namespace: str,
        run_id: str,
        state: dict[str, Any],
        completion: Future[Any],
        stream_writer: StreamWriter,
    ) -> str:
        """Bind this pending context to its single invocation attempt."""
        if self._status != "pending":
            raise RuntimeError(
                "GraphContext must be pending before starting an invocation."
            )
        if (
            self._context_namespace is not None
            and self._context_namespace != context_namespace
        ):
            raise ValueError(
                "A recovered GraphContext must run in its original namespace."
            )

        self._context_namespace = context_namespace
        self._has_started = True
        if self.context_snapshot is None:
            self.node_name = START
            self.steps = 0

        self.run_id = run_id
        self.state = _copy_state(state, self._keep_ref_keys)
        self.completion = completion
        self.stream_writer = stream_writer
        self._transition_to("running")
        return self.node_name

    def _belongs_to(self, context_namespace: str) -> bool:
        """Return whether this context belongs to a graph namespace."""
        return self._context_namespace == context_namespace

    def _set_next_node(self, node_name: str) -> None:
        """Record which node should consume the current state next."""
        self.node_name = node_name

    def take_a_snapshot(self) -> None:
        """Capture an isolated copy of the current recoverable state."""
        if not self.is_active or self._context_namespace is None:
            raise RuntimeError(
                "A snapshot can only be taken from an active GraphContext."
            )
        self.context_snapshot = {
            "timestamp": time.time(),
            "state": copy.deepcopy(self.state),
            "node_name": self.node_name,
            "steps": self.steps,
            "namespace": self._context_namespace,
        }

    def get_current_snapshot(self) -> GraphContextSnapshot | None:
        """Get a deepcopy of the current snapshot in this context, return :class:`GraphContextSnapshot`."""
        return copy.deepcopy(self.context_snapshot) if self.context_snapshot else None

    def _snapshot_state(self) -> dict[str, Any]:
        """Copy the latest committed state using this context's KeepRef policy."""
        return _copy_state(self.state, self._keep_ref_keys)

    def _recovery_state(self) -> dict[str, Any]:
        """Copy the recovery checkpoint, falling back to pre-node state."""
        snapshot = self.context_snapshot
        state = self.state if snapshot is None else snapshot["state"]
        return _copy_state(state, self._keep_ref_keys)

    def _finish(self) -> None:
        """Resolve a running attempt and enter the terminal finished state."""
        if self._status == "finished" or self._status != "running":
            return

        completion = self.completion
        assert completion is not None
        result = None if completion.done() else self._snapshot_state()
        self._transition_to("finished")
        if not completion.done():
            completion.set_result(result)

    def _fail(self, error: Exception) -> None:
        """Fail a pending or running attempt without changing its snapshot."""
        if self._status == "failed" or self._status not in ("pending", "running"):
            return

        self._transition_to("failed")
        completion = self.completion
        if completion is not None and not completion.done():
            completion.set_exception(error)

    def abort(self) -> None:
        """Abort a pending or running attempt at its latest snapshot."""
        if self._status == "aborted":
            return
        if self._status not in ("pending", "running"):
            raise RuntimeError(
                f"Cannot abort a GraphContext with status {self._status}."
            )

        completion = self.completion
        result = None
        if completion is not None and not completion.done():
            result = self._recovery_state()

        self._transition_to("aborted")
        if completion is not None and not completion.done():
            completion.set_result(result)
