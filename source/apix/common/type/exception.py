class PlatformNotRegisteredError(Exception):
    
    def __init__(self, message="Platform not registered error.", platform=None):
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
        return f"{self.message}; {error_details}"


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
        return f"{self.message}; {error_details}"

class IdentityError(ValueError):
    """Ambiguous apix identity. Unknow user_uid, platform or conversation_uid"""