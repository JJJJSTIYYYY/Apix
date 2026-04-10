### Tool & Plugin Registration

1. **Each plugin must define a unique tool name.**

2. **The Tool Service maintains a registry** (dictionary) that maps each tool name to its corresponding handler.

3. **Foreign tools must be registered via the Tool Service API:**

   ```python
   def register_foreign_tool(tool_name: str, script_path: list[str])
   ```

4. **All foreign tools share a unified execution entry point** (`python_script_runner`):

   ```python
   def python_script_runner(tool)
   ```

---

### End-to-End Execution Flow

1. The **AI Service** issues a tool invocation request.
2. The request enters the **Tool Service API**.
3. The Tool Service creates a **task creation request** and forwards it to the **Memory Service**.
4. The Memory Service:

   * Verifies execution permission
   * Sets the task status in Redis to `pending`
   * Returns execution permission to the Tool Service
5. The Tool Service:

   * Receives permission
   * Creates the task
   * Returns the **task ID** to both the **AI Service** and **User Client**
6. The Tool Service waits for **explicit user approval**.
7. Once user permission is granted:

   * The Tool Service triggers task execution
   * Sends a task status update request to the Memory Service
8. The Memory Service updates the task status in Redis to `running`.
9. After execution completes:

   * The Tool Service reports the final task status and result to the Memory Service
10. The task result is returned to:

    * User Client
    * AI Service
11. The **LLM** analyzes the task result.
12. The final analysis is returned to the **User Client**.

