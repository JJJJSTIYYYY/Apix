重构前AgentConfigSchema
```javascript
{
    models_provider: store.config.modelProvider,
    model_name: store.config.modelName,
    api_key: store.config.apiKey,
    enable_think: store.config.deepThink,
    work_dir: store.currentWorkDir,

    max_chunk_per_invoking: store.config.tokenLimit,
    async_tools_invoke: store.config.toolsInvokeAi,
    link_provider: store.config.linkProvider,
    link_api_key: store.config.linkApiKey,
    content_provider: store.config.contentPovider,
    content_api_key: store.config.contentApiKey,
    web_cleaner_mode: store.config.webContentFilter,
    keep_tools_message: store.config.remainToolsCache,
    enable_longterm_memory: store.config.longtermMemory,
    enable_shortterm_memory: store.config.shorttermMemory,
    summary_trigger_threshold: store.config.messageSummary,
    summary_exempt_tail_length: store.config.keepNotSummary,
    pure_chat_on: store.config.pureChat,
    use_model_vision: store.config.visionOn,

    enable_file_opration: store.config.fileOpration,
    enable_web_search: store.config.webSearch,
    enable_knowledge_retrieval: store.config.knowledgeRetrieval,
    enable_command_opration: store.config.commandOpration,
    enable_skill_load: store.config.skillLoad,
    enable_agent_assign: store.config.agentAssign,
    enable_agent_swarm: store.config.agentSwarm,

    embed_model: store.config.embeddingModel,
    role_prompt: toRaw(store.config.rolePrompt),
    higher_role_prompt_permission: store.config.higherRolePromptPermission,
    interface_test_mode: store.config.testExpertMode,
}
```