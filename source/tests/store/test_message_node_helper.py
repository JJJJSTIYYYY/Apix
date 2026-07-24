"""Tests for rebuilding and traversing persisted message-node trees."""

from copy import deepcopy

import pytest

from apix.agent.store.utils.message_node_helper import MessageNodeHelper


def _row(
    node_id: str,
    parent_id: str | None,
    cursor: int,
    *,
    deleted: bool = False,
    **extra,
) -> dict:
    return {
        "node_id": node_id,
        "parent_id": parent_id,
        "msg_cursor": cursor,
        "is_deleted": deleted,
        **extra,
    }


def _node(
    node_id: str,
    cursor: int,
    *,
    visible: bool,
) -> dict:
    """Create a minimal node for isolated traversal-heuristic tests."""
    return {
        "node_id": node_id,
        "parent_id": "-",
        "rows": [],
        "first_cursor": cursor,
        "last_cursor": cursor,
        "visible": visible,
    }


def test_empty_helper_contains_only_root_and_has_empty_traversals():
    helper = MessageNodeHelper([])

    assert helper.nodes == [
        {
            "node_id": "-",
            "parent_id": None,
            "rows": [],
            "first_cursor": -1,
            "last_cursor": -1,
            "visible": True,
        }
    ]
    assert helper.node_map == {"-": helper.nodes[0]}
    assert helper.get_children("missing") == []
    assert helper.get_path("missing") == []
    assert helper.extend_path([]) == []
    assert helper.build_branch("-") == [helper.nodes[0]]
    assert helper.flatten_branch(helper.nodes) == []
    assert helper.find_nearest_visible("missing") is None


def test_grouping_preserves_node_order_and_sorts_rows_by_cursor():
    rows = [
        _row("node-a", "old-parent", 3, deleted=True, content="third"),
        _row("node-b", "-", 4, content="fourth"),
        _row("node-a", "new-parent", 1, content="first"),
        _row("node-a", "new-parent", 2, content="second"),
    ]

    helper = MessageNodeHelper(rows)
    node_a = helper.node_map["node-a"]

    assert [node["node_id"] for node in helper.nodes] == [
        "-",
        "node-a",
        "node-b",
    ]
    assert [row["msg_cursor"] for row in node_a["rows"]] == [1, 2, 3]
    assert node_a["parent_id"] == "-"
    assert node_a["first_cursor"] == 1
    assert node_a["last_cursor"] == 3
    assert node_a["visible"] is True
    assert [node["node_id"] for node in helper.get_children("-")] == [
        "node-a",
        "node-b",
    ]


def test_build_node_uses_shared_parent_and_detects_fully_deleted_node():
    helper = MessageNodeHelper([])
    rows = [
        _row("deleted", "parent", 2, deleted=True),
        _row("deleted", "parent", 1, deleted=True),
    ]

    node = helper._build_node(rows)

    assert node == {
        "node_id": "deleted",
        "parent_id": "parent",
        "rows": rows,
        "first_cursor": 1,
        "last_cursor": 2,
        "visible": False,
    }


def test_missing_deleted_flag_keeps_node_visible():
    helper = MessageNodeHelper([])
    row = {
        "node_id": "visible",
        "parent_id": "-",
        "msg_cursor": 1,
    }

    assert helper._build_node([row])["visible"] is True


@pytest.mark.parametrize(
    ("cursor", "expected_cursor"),
    [
        (5, 5),
        (-2, -1),
    ],
)
def test_real_dash_node_competes_with_synthetic_root(
    cursor,
    expected_cursor,
):
    """Duplicate node IDs retain whichever node has the latest cursor."""
    helper = MessageNodeHelper([
        _row("-", None, cursor),
    ])

    assert helper.node_map["-"]["last_cursor"] == expected_cursor


def test_deleted_nodes_are_skipped_and_visible_descendants_are_relinked():
    rows = [
        _row("parent", "-", 1),
        _row("deleted", "parent", 2, deleted=True),
        _row("child", "deleted", 3),
        _row("orphan", "missing", 4),
        _row("none-parent", None, 5),
    ]

    helper = MessageNodeHelper(rows)

    assert helper.node_map["deleted"]["visible"] is False
    assert helper.node_map["child"]["parent_id"] == "parent"
    assert helper.node_map["orphan"]["parent_id"] == "-"
    assert helper.node_map["none-parent"]["parent_id"] == "-"
    assert helper.get_children("deleted") == []
    assert [node["node_id"] for node in helper.get_children("parent")] == [
        "child",
    ]
    assert [node["node_id"] for node in helper.get_children("-")] == [
        "parent",
        "orphan",
        "none-parent",
    ]


def test_get_path_and_find_nearest_visible_follow_parent_chain():
    helper = MessageNodeHelper([
        _row("parent", "-", 1),
        _row("deleted", "parent", 2, deleted=True),
        _row("child", "deleted", 3),
    ])

    assert [
        node["node_id"]
        for node in helper.get_path("child")
    ] == ["-", "parent", "child"]
    assert helper.find_nearest_visible("child")["node_id"] == "child"
    assert helper.find_nearest_visible("deleted")["node_id"] == "parent"
    assert helper.find_nearest_visible("unknown") is None


def test_extend_path_prefers_visible_child_with_latest_cursor():
    helper = MessageNodeHelper([
        _row("start", "-", 1),
        _row("older", "start", 2),
        _row("newer", "start", 4),
        _row("leaf", "newer", 5),
    ])

    initial_path = helper.get_path("start")
    result = helper.extend_path(initial_path)

    assert result is initial_path
    assert [node["node_id"] for node in result] == [
        "-",
        "start",
        "newer",
        "leaf",
    ]
    assert [
        node["node_id"]
        for node in helper.build_branch("start")
    ] == ["-", "start", "newer", "leaf"]


def test_extend_path_falls_back_to_latest_invisible_child():
    helper = MessageNodeHelper([
        _row("start", "-", 1),
    ])
    older = _node("older-deleted", 2, visible=False)
    newer = _node("newer-deleted", 3, visible=False)
    helper.children_map["start"] = [newer, older]

    path = [helper.node_map["start"]]

    assert [
        node["node_id"]
        for node in helper.extend_path(path)
    ] == ["start", "newer-deleted"]


def test_flatten_branch_combines_and_globally_sorts_rows():
    rows = [
        _row("parent", "-", 3, content="third"),
        _row("parent", "-", 1, content="first"),
        _row("child", "parent", 2, content="second"),
    ]
    helper = MessageNodeHelper(deepcopy(rows))
    branch = [
        helper.node_map["parent"],
        helper.node_map["child"],
    ]

    flattened = helper.flatten_branch(branch)

    assert [row["content"] for row in flattened] == [
        "first",
        "second",
        "third",
    ]


def test_relink_sorts_siblings_by_first_cursor():
    helper = MessageNodeHelper([
        _row("late", "-", 5),
        _row("early", "-", 2),
        _row("middle", "-", 3),
    ])

    assert [
        node["node_id"]
        for node in helper.get_children("-")
    ] == ["early", "middle", "late"]
