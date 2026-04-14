from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from app.commons.logger import logger


class Translator:
    def __init__(self, max_depth: int = 10):
        # Maximum allowed recursion depth for nested folders
        self.max_depth = max_depth

    def translate(
        self,
        raw_case: dict[str, Any],
        *,
        depth: int = 0,
    ) -> Iterator[dict[str, Any]]:
        """
        Translate raw case data into executable case objects.

        This method is re-entrant and concurrency-safe because it does not rely
        on shared mutable state during traversal.
        """
        if not isinstance(raw_case, dict):
            raise TypeError(f"raw_case must be dict, got {type(raw_case).__name__}")

        if depth > self.max_depth:
            raise RecursionError(
                f"Translator: maximum translation depth exceeded ({self.max_depth})."
            )

        try:
            # If the case is already translated, yield it directly
            if raw_case.get("translate_status", False):
                yield raw_case
                return

            case_type = raw_case.get("type")

            match case_type:
                case "folder":
                    yield from self._translate_folder(raw_case, depth)

                case "interface" | "database" | "script":
                    case_data = self.construct_case(raw_case, case_type)
                    if case_data is not None:
                        yield case_data
                    else:
                        logger.warning(
                            f"[translate] Skipped invalid case: type={case_type}, "
                            f"title={raw_case.get('title', 'Unnamed task')!r}"
                        )

                case _:
                    logger.warning(
                        f"[translate] Unsupported case type: {case_type!r}, "
                        f"title={raw_case.get('title', 'Unnamed task')!r}"
                    )

        except Exception as e:
            logger.error(
                f"translator.py: translate: {type(e).__name__}: {e}; "
                f"raw_case={raw_case!r}"
            )
            raise

    def _translate_folder(
        self,
        raw_case: dict[str, Any],
        depth: int,
    ) -> Iterator[dict[str, Any]]:
        """
        Translate all sub-cases inside a folder recursively.
        """
        content = raw_case.get("content", [])

        if content is None:
            return

        if not isinstance(content, list):
            raise TypeError(
                f"folder content must be list, got {type(content).__name__}"
            )

        for index, sub_case in enumerate(content):
            if not isinstance(sub_case, dict):
                logger.warning(
                    f"[translate] Skipped non-dict sub_case at index={index}: {sub_case!r}"
                )
                continue

            yield from self.translate(sub_case, depth=depth + 1)

    def construct_case(
        self,
        raw_case: dict[str, Any],
        case_type: str,
    ) -> dict[str, Any] | None:
        """
        Construct an executable case from a raw case definition.

        Returns None when required fields are missing.
        """
        result: dict[str, Any] = {
            "name": raw_case.get("title", "Unnamed task"),
            "type": case_type,
        }

        if case_type in ("interface", "database"):
            address = raw_case.get("address")
            if not address:
                return None
            result["address"] = address

        elif case_type == "script":
            script = raw_case.get("script")
            if not script:
                return None
            result["script"] = script

        else:
            return None
        
        result["id"] = raw_case.get("id", str(uuid4()))
        result["description"] = raw_case.get("description", "")

        return result
    


translator = Translator()