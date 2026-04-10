


# Decorator to mark task handler methods
def task_handler(name: str | None = None):
    """
    Mark a method as a task handler.
    The task name defaults to function name if not provided.
    """
    def decorator(func):
        func._handler_name = name or func.__name__
        return func
    return decorator
