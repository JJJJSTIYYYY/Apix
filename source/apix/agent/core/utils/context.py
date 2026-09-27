from typing import Any, Literal, Optional, TypedDict


class RoleSchema(TypedDict):
    name: str
    title: Optional[str]
    definition: str


class Todo(TypedDict):
    content: str
    status: Literal["pending", "in_progress", "completed"]


class Skill(TypedDict):
    skill_id: str
    skill_name: str
    description: str


class LongtermMemory(TypedDict):
    memory_id: str
    title: str
    date: str
    abstract: str
    content: str
    source: Literal["conversation", "workspace"]


class ShorttermMemory(TypedDict):
    memory_id: str
    content: str
    created_timestamp: int


# ============================================================
# Context item detection
# ============================================================

_CONTEXT_ITEM_SCHEMA: dict[str, set[str]] = {
    "RoleSchema": {
        "name",
        "definition",
    },
    "Todo": {
        "content",
        "status",
    },
    "Skill": {
        "skill_id",
        "skill_name",
        "description",
    },
    "LongtermMemory": {
        "memory_id",
        "title",
        "date",
        "abstract",
        "content",
        "source",
    },
    "ShorttermMemory": {
        "memory_id",
        "content",
        "created_timestamp",
    },
}


def _has_keys(
    value: dict,
    required_keys: set[str],
) -> bool:
    """Check whether a dict contains all required keys."""
    return required_keys.issubset(value.keys())


def _get_context_item_type(
    context_item: dict | list,
) -> str:
    """Determine context item type.

    Supported:
        - RoleSchema
        - list[Todo]
        - list[Skill]
        - list[LongtermMemory]
        - list[ShorttermMemory]
    """
    if isinstance(context_item, dict):
        candidates = [context_item]

    elif isinstance(context_item, list):
        if not context_item:
            raise ValueError(
                "Cannot determine context item type from empty list."
            )

        candidates = [context_item[0]]

    else:
        raise ValueError(
            "Context item must be dict or list."
        )

    item = candidates[0]

    if not isinstance(item, dict):
        raise ValueError(
            "Context item element must be dict."
        )

    for item_type, required_keys in _CONTEXT_ITEM_SCHEMA.items():
        if _has_keys(item, required_keys):
            return item_type

    raise ValueError(
        "Invalid context item format."
    )


# ============================================================
# Prompt helpers
# ============================================================

def _escape_markdown(
    value: str,
) -> str:
    """Escape markdown table separators."""
    return value.replace("|", "\\|")


# ============================================================
# Prompt conversion
# ============================================================

def to_prompt(
    context_item: Any,
    type_hint: Optional[str] = None,
) -> str:
    """Convert context item into model prompt.

    Supported context items:

        RoleSchema:
            Role definition injected directly.

        list[Todo]:
            Current task progress.

        list[Skill]:
            Available skills for progressive loading.

        list[LongtermMemory]:
            Available memories for progressive loading.

        list[ShorttermMemory]:
            Conversation compression summary.
    """
    if type_hint is not None:
        ci_type = type_hint
    else:
        ci_type = _get_context_item_type(context_item)

    # ========================================================
    # RoleSchema
    # ========================================================

    if ci_type == "RoleSchema":
        name = context_item.get(
            "name",
            "",
        ).strip()

        title = (
            context_item.get("title")
            or ""
        ).strip()

        definition = context_item.get(
            "definition",
            "",
        ).strip()

        if not name and not title and not definition:
            return ""

        lines = [
            "## Role Definition",
            "",
        ]

        if name:
            lines.append(
                f"- Your name: {name}."
            )

        if title:
            lines.append(
                f"- Your title: {title}."
            )

        if definition:
            lines.append(
                "- Your Characteristics:"
            )
            lines.append(
                f"  {definition}"
            )

        return "\n".join(lines) + "\n"


    # ========================================================
    # Todo
    # ========================================================

    if ci_type == "Todo":
        if not context_item:
            return ""

        lines = [
            "## Task Progress:"
        ]

        for index, item in enumerate(
            context_item,
            start=1,
        ):
            content = item.get(
                "content",
                "",
            ).strip()

            status = item.get(
                "status",
                "",
            ).strip()

            if not content:
                continue

            lines.append(
                f"{index}. {content} -- {status};"
            )

        return "\n".join(lines)


    # ========================================================
    # Skill (Progressive Loading)
    # ========================================================

    if ci_type == "Skill":
        if not context_item:
            return ""

        lines = [
            (
                "Skills are reusable capability packages that help you "
                "perform complex tasks. Each skill provides specialized "
                "instructions, workflows, and examples."
            ),
            "",
            (
                "Skills are not loaded automatically. "
                "Before using a skill, you must load it first to obtain "
                "its detailed guide (SKILL.md)."
            ),
            "",
            (
                "Only load a skill when it is clearly relevant to the "
                "user's request. Avoid loading unnecessary skills."
            ),
            "",
            "### Available skills to load:",
            "",
        ]

        for skill in context_item:
            name = skill.get(
                "skill_name",
                "",
            ).strip()

            description = skill.get(
                "description",
                "",
            ).strip()

            if not name:
                continue

            lines.append(
                f"- {name}"
            )

            if description:
                lines.append(
                    f"  Description: {description}"
                )

            lines.append("")

        lines.append(
            (
                "After loading a skill, you can follow the instructions "
                "provided in its guide."
            )
        )

        return "\n".join(lines) + "\n"


    # ========================================================
    # LongtermMemory (Progressive Loading)
    # ========================================================

    if ci_type == "LongtermMemory":
        if not context_item:
            return ""

        lines = [
            (
                "Long-term memories are persistent information collected "
                "from previous conversations and workspace activities."
            ),
            "",
            (
                "Each memory contains a short abstract describing its "
                "content. The full memory is not included here."
            ),
            "",
            (
                "Retrieve a memory only when it is clearly relevant to "
                "the current request."
            ),
            "",
            "### Available long-term memories:",
            "",
            "| # | Title | Date | Abstract |",
            "|---|---|---|---|",
        ]

        for index, item in enumerate(
            context_item,
            start=1,
        ):
            title = _escape_markdown(
                item.get("title", "").strip()
            )

            date = item.get(
                "date",
                "",
            ).strip()

            abstract = _escape_markdown(
                item.get("abstract", "").strip()
            )

            lines.append(
                f"| {index} | "
                f"{title or 'None'} | "
                f"{date or 'None'} | "
                f"{abstract or 'None'} |"
            )

        return "\n".join(lines)


    # ========================================================
    # ShorttermMemory
    # ========================================================

    if ci_type == "ShorttermMemory":
        if not context_item:
            return ""

        lines = [
            "## Conversation Compress",
            "",
            (
                "The following is a summary of earlier messages "
                "in this conversation:"
            ),
            "",
        ]

        for item in context_item:
            content = item.get(
                "content",
                "",
            ).strip()

            if content:
                lines.append(content)

        return "\n".join(lines)


    raise ValueError(
        f"Unsupported context item type: {ci_type}"
    )