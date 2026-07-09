"""Logging configuration for the application launcher."""
import logging


def setup_logging() -> logging.Logger:
    """Disable application logging output entirely."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(logging.NullHandler())
    logging.disable(logging.CRITICAL)
    return logging.getLogger("applauncher")
