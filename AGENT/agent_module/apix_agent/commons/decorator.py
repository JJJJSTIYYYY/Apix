import inspect
from functools import wraps

def accept_extra_kwargs(func):
    """
    Ignore unexpected keyword arguments.
    Works for functions and class __init__.
    """
    sig = inspect.signature(func)
    param_names = set(sig.parameters.keys())

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Filter out unexpected keyword arguments
        filtered_kwargs = {
            k: v for k, v in kwargs.items()
            if k in param_names
        }
        return func(*args, **filtered_kwargs)

    return wrapper
