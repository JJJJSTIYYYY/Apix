
# def add_prebuilt_tools_router(
#     self, 
#     bot_node_name: str = 'bot', 
#     tool_node_name: str = 'tools', 
#     next_default: str = END,
# ):
#     """Add a router node between bot node and tool node.
#     Auto bind tools for a bot instance.
    
#     Args:
#         bot_node_name: The bot node's name.
#         tool_node_name: The tool node's name.
#         next_default: The default node to enter when a tool node should not be entered.

#     Notes:
#         If a bot node has other routing destinations besides the tool node and a default node, use :data:`add_router` instead.
#     """
#     messages_key = self.messages_key
#     def should_call_tool(state):
#         messages: list[AnyMessage] = state.get(messages_key, []) or []
#         if not messages:
#             return next_default
#         if not isinstance(messages[-1], ApixAiMessage) or not messages[-1].tool_calls:
#             return next_default
#         return tool_node_name

#     self.add_router(bot_node_name, [next_default, tool_node_name], should_call_tool)