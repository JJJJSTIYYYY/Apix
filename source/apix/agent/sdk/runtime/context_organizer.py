import copy

from apix.agent.sdk.utils.message import AnyMessage, ApixSystemMessage
from apix.agent.sdk.utils.context import LongtermMemory, ShorttermMemory, Skill, Todo


class ContextOrganizer:
    """Organize and manage the execution context of an agent.

    ContextOrganizer provides a unified container for agent-related context,
    including conversation messages, system prompts, memory, skills, and
    task-related information. It is designed to simplify context management
    between different nodes during agent execution.

    When a context is copied (for example, before passing it to another node),
    fields listed in ``shared_fields`` will preserve their original references
    instead of being deep-copied. This allows selected mutable objects to be
    directly modified across nodes without requiring explicit state updates.

    By default, ``messages`` is shared between copied contexts. This means nodes
    can append, modify, or reorder messages directly, and the changes will be
    visible to other nodes using the same context reference.

    Attributes:
        messages: The conversation message history managed by the agent.
        system_prompt: Optional system-level instructions for the agent.
        shortterm_memory: Optional short-term memory associated with the context.
        longterm_memory: Optional collection of long-term memories.
        skills: Optional list of available agent skills.
        todo: Optional list of pending tasks or objectives.
        shared_fields: Field names that should preserve references during
            context copying instead of being deep-copied.

    Args:
        messages: Initial conversation messages.
        system_prompt: Optional system prompt messages.
        todo: Optional task list associated with the current context.
        shortterm_memory: Optional short-term memory object.
        longterm_memory: Optional long-term memory records.
        skills: Optional available skills for the agent.
        shared_fields: Fields that should be shared by reference between copied
            contexts. Defaults to ``["messages"]``.

    Examples:
        ```python
        class ContextState(TypedDict):
            context: Annotated[ContextOrganizer, AutoMerge()]
            others: Any

        context = ContextOrganizer(
            messages = [ApixUserMessage(content="A example user message.")]
        )
        state = ContextState(
            context = context,
            others = "Example State."
        )

        def modify_message(state):
            state.get("context").append(
                ApixAiMessage(content="A example ai message.")
            ) # Append directly
            return Command() # No updates in Command

        graph = (
            GraphManager(ContextState)
            .add_node(modify_message)
            .add_edge(START, "modify_message")
            .compile_graph()
        )
        final_state = await graph.invoke(state)

        assert final_state["context"].messages[-1].content == "A example ai message."
        ```
    """

    messages: list[AnyMessage]
    system_prompt: list[ApixSystemMessage] | None
    shortterm_memory: ShorttermMemory | None
    longterm_memory: list[LongtermMemory] | None
    skills: list[Skill] | None
    todo: list[Todo] | None
    shared_fields:list[str]

    def __init__(
        self,
        messages: list[AnyMessage],
        system_prompt: list[ApixSystemMessage] | None = None,
        todo: list[Todo] | None = None,
        shortterm_memory: ShorttermMemory | None = None,
        longterm_memory: list[LongtermMemory] | None = None,
        skills: list[Skill] | None = None,
        *,
        shared_fields:list[str] | None = None
    ):
        self.messages = messages
        self.system_prompt = system_prompt
        self.todo = todo
        self.shortterm_memory = shortterm_memory
        self.longterm_memory = longterm_memory
        self.skills = skills
        self.shared_fields = shared_fields or ["messages"]

    def __add__(self, other: list[AnyMessage] | AnyMessage):
        if not isinstance(other, list):
            other = [other]
        for message in other:
            if message.role in ['system', 'developer']:
                self.system_prompt.append(message)
            elif message.role in ['user', 'ai', 'tool']:
                self.messages.append(message)
            else:
                raise TypeError(f"Unsupport role to add, got `{message.role}`")

    def __getitem__(self, index):
        return self.messages[index]

    def __setitem__(self, index, value):
        self.messages[index] = value

    def __delitem__(self, index):
        del self.messages[index]

    def __len__(self):
        return len(self.messages)

    def __iter__(self):
        return iter(self.messages)

    def append(self, value):
        self.messages.append(value)

    def extend(self, values):
        self.messages.extend(values)

    def get_system_prompt(self):
        return copy.deepcopy(self.system_prompt)

    def get_messages(self):
        return copy.deepcopy(self.messages)