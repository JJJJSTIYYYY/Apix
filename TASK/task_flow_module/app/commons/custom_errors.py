
from json import JSONDecodeError

class CaseLoadError(Exception):
    """
    Test case loading error. Indicates failure to load or parse test cases from a given source.
    """

    def __init__(self, message: str, source: str = None, original_exception: Exception = None):
        """
        :param message: error message
        :param source: Test case source (e.g., filename, URL)
        :param original_exception: Original exception that caused the load failure
        """
        super().__init__(message)
        self.source = source
        self.original_exception = original_exception

    def __str__(self):
        base = super().__str__()
        extra = []
        if self.source:
            extra.append(f"source={self.source}")
        if self.original_exception:
            extra.append(f"original_exception={type(self.original_exception).__name__}: {self.original_exception}")
        return f"{base} | {' | '.join(extra)}" if extra else base
