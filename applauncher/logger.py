"""Logging configuration for the application launcher."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging() -> logging.Logger:
    """Keep routine output silent and retain warnings about design resources."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(logging.NullHandler())
    logging.disable(logging.NOTSET)
    design_logger = logging.getLogger("applauncher.gui.styles")
    design_logger.setLevel(logging.WARNING)
    design_logger.propagate = False
    for handler in list(design_logger.handlers):
        handler.close()
        design_logger.removeHandler(handler)
    try:
        from .config import resolve_config_path
        log_path = Path(resolve_config_path()).parent / "design_warnings.log"
        handler = RotatingFileHandler(log_path, maxBytes=256_000, backupCount=1, encoding="utf-8", delay=True)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        design_logger.addHandler(handler)
    except OSError:
        design_logger.addHandler(logging.NullHandler())
    return logging.getLogger("applauncher")
