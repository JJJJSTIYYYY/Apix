class ProviderNotFoundError(Exception):
    
    def __init__(self, message="Custom provider not found.", provider=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = provider if provider else ''
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"


class ProviderTypeMismatchError(Exception):
    
    def __init__(self, message="Provider type mismatch.", provider=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = provider if provider else ''
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"
    

class InvalidToolArgsError(TypeError):
    def __init__(self, *args):
        super().__init__(*args)


class ChunkMergeError(ValueError):
    """Chunks belonging to different streams were merged."""


class IncompleteToolCallError(ValueError):
    """A streamed tool call cannot be converted into a complete tool call."""