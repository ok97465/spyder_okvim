import os

def running_in_pytest() -> bool:
    """Return ``True`` if executed within a pytest session."""
    return "PYTEST_CURRENT_TEST" in os.environ
