class Invalid_Syntax(Exception):
    """Raised when the input file does not match the expected syntax.

    Attributes:
        message: The human-readable error message.
        index: The line number where the error occurred.
    """

    def __init__(self, message: str, index: int):
        """Create a syntax error annotated with the offending line index.

        Args:
            message: The error message.
            index: The line number where the error occurred.
        """
        self.message = message
        self.index = index
        super().__init__(
            f"\033[91mError Invalid_Syntax in [line {index}]: \033[0m"
            + message
            )


class Invalid_Argument(Exception):
    """Raised when the CLI arguments are invalid.

    Attributes:
        message: The human-readable error message.
    """

    def __init__(self, message: str):
        """Create an argument error with a human-readable message.

        Args:
            message: The error message.
        """
        self.message = message
        super().__init__("\033[91mError Invalid Argument: \033[0m" + message)


class Invalid_graph(Exception):
    """Raised when no valid graph paths can be built.

    Attributes:
        message: The human-readable error message.
    """

    def __init__(self, message: str):
        """Create a graph error with a human-readable message.

        Args:
            message: The error message.
        """
        self.message = message
        super().__init__("\033[91mError Invalid graph: \033[0m" + message)
