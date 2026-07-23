class ProviderNotFound(Exception):
    
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


class PlatformNotRegister(Exception):
    
    def __init__(self, message="Platform not register error.", platform=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = platform if platform else ''
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"


class ConflictToolCalls(Exception):
    
    def __init__(self, message="Invalid tool calls detected", errors=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = errors if errors else []
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"


class InvalidOutputsError(Exception):
    
    def __init__(self, message="Invalid outputs detected", errors=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = errors if errors else []
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"
    

class EventHandlerNotRegistered(Exception):
    
    def __init__(self, message="Invalid hander detected", errors=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = errors if errors else []
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"
    

class EventHandlerAlreadyRegistered(Exception):
    
    def __init__(self, message="Invalid hander detected", errors=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = errors if errors else []
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"
    

class InvalidNodeReturns(Exception):
    
    def __init__(self, message="Invalid node returns", errors=None):
        """        
        Args:
            message: error message
            errors: error object
        """
        self.message = message
        self.errors = errors if errors else []
        super().__init__(self.message)
    
    def __str__(self):
        error_details = f"Errors: {self.errors}" if self.errors else ""
        return f"{self.message}{error_details}"
    

class InvalidToolArgs(TypeError):
    def __init__(self, *args):
        super().__init__(*args)


class ChunkMergeError(ValueError):
    """Chunks belonging to different streams were merged."""


class IncompleteToolCallError(ValueError):
    """A streamed tool call cannot be converted into a complete tool call."""


class CommandMergeError(ValueError):
    """Raised when multiple commands contain conflicting routes."""