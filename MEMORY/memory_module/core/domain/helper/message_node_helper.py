from collections import defaultdict, OrderedDict
from typing import List, Dict, Any


class AgentNodeHelper:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.rows = rows

        self.nodes = []
        self.node_map = {}
        self.children_map = defaultdict(list)

        self._build()

    # Group rows by node_id
    def _group_by_node(self):
        groups = OrderedDict()

        for r in self.rows:
            nid = r["node_id"]

            if nid not in groups:
                groups[nid] = []

            groups[nid].append(r)

        return list(groups.values())

    def _build_node(self, rows: List[Dict[str, Any]]):
        rows.sort(key=lambda x: x["msg_cursor"])

        first = rows[0]
        last = rows[-1]

        parent_ids = {r["parent_id"] for r in rows}
        if len(parent_ids) == 1:
            parent_id = parent_ids.pop()
        else:
            parent_id = first["parent_id"]

        visible = any(not r.get("is_deleted") for r in rows)

        return {
            "node_id": last["node_id"],
            "parent_id": parent_id,
            "rows": rows,
            "first_cursor": first["msg_cursor"],
            "last_cursor": last["msg_cursor"],
            "visible": visible,
        }

    def _build(self):
        groups = self._group_by_node()
        self.nodes = [self._build_node(g) for g in groups]

        root_node = {
            "node_id": "-",
            "parent_id": None,
            "rows": [],
            "first_cursor": -1,
            "last_cursor": -1,
            "visible": True,
        }

        self.nodes.insert(0, root_node)

        for n in self.nodes:
            if n["node_id"] not in self.node_map:
                self.node_map[n["node_id"]] = n
            else:
                if n["last_cursor"] > self.node_map[n["node_id"]]["last_cursor"]:
                    self.node_map[n["node_id"]] = n

        raw_children_map = defaultdict(list)

        for n in self.nodes:
            parent_id = n["parent_id"]
            if parent_id is None:
                continue
            raw_children_map[parent_id].append(n)

        for k in raw_children_map:
            raw_children_map[k].sort(key=lambda x: x["first_cursor"])

        self.children_map = raw_children_map

        self.children_map = self._relink_deleted_nodes()

    def get_children(self, node_id: str):
        return self.children_map.get(node_id, [])

    def get_path(self, node_id: str):
        path = []
        cur = self.node_map.get(node_id)

        while cur:
            path.append(cur)
            cur = self.node_map.get(cur["parent_id"])

        return list(reversed(path))

    def extend_path(self, path: List[Dict[str, Any]]):
        if not path:
            return path

        cur = path[-1]

        while True:
            children = self.children_map.get(cur["node_id"])

            if not children:
                break

            visible_children = [c for c in children if c.get("visible")]

            if visible_children:
                next_node = max(visible_children, key=lambda x: x["last_cursor"])
            else:
                next_node = max(children, key=lambda x: x["last_cursor"])

            path.append(next_node)
            cur = next_node

        return path

    def build_branch(self, current_node_id: str):
        path = self.get_path(current_node_id)
        return self.extend_path(path)

    def flatten_branch(self, branch: List[Dict[str, Any]]):
        rows = []

        for node in branch:
            rows.extend(node["rows"])

        rows.sort(key=lambda x: x["msg_cursor"])
        return rows

    def find_nearest_visible(self, node_id: str):
        cur = self.node_map.get(node_id)

        while cur:
            if cur.get("visible"):
                return cur
            cur = self.node_map.get(cur["parent_id"])

        return None
    
    def _relink_deleted_nodes(self):
        """
        Rebuild parent-child relationship
        """

        new_children_map = defaultdict(list)

        def find_visible_ancestor(node):
            cur = self.node_map.get(node["parent_id"])
            while cur:
                if cur.get("visible"):
                    return cur
                cur = self.node_map.get(cur["parent_id"])
            return None

        for node in self.nodes:
            if node["node_id"] == "-":
                continue

            if node.get("visible"):
                parent = self.node_map.get(node["parent_id"])

                if parent and parent.get("visible"):
                    new_parent_id = parent["node_id"]
                else:
                    ancestor = find_visible_ancestor(node)
                    new_parent_id = ancestor["node_id"] if ancestor else "-"

                node["parent_id"] = new_parent_id
                new_children_map[new_parent_id].append(node)

            else:
                continue

        for k in new_children_map:
            new_children_map[k].sort(key=lambda x: x["first_cursor"])

        return new_children_map