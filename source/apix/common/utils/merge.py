import copy
from typing import Any


def merge_dicts(
    left: dict[str, Any],
    right: dict[str, Any]
) -> dict[str, Any]:
    """
    Deep merge two dicts and return a new dict.

    Rules:
        - If both values are dict, merge recursively.
        - Otherwise right overwrites left.
        - Neither input dict will be modified.

    Example:
        left = {
            "a": 1,
            "b": {
                "c": 2,
                "d": [1, 2],
            },
        }

        right = {
            "b": {
                "c": 100,
                "e": 200,
            },
        }

        merged = merge_dicts(left, right)

        print(merged)
        # {
        #     'a': 1,
        #     'b': {'c': 100, 'd': [1, 2], 'e': 200}
        # }
    """
    result = copy.deepcopy(left)

    stack = [(result, right)]

    while stack:
        base, updates = stack.pop()

        for k, v in updates.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                stack.append((base[k], v))
            else:
                base[k] = copy.deepcopy(v)

    return result