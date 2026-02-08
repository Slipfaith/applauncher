"""Logging configuration for the application launcher."""
import logging
from pathlib import Path

from .config import resolve_config_path


def _resolve_log_file() -> Path:
    try:
        return Path(resolve_config_path("launcher.log"))
    except OSError:
        return Path("launcher.log")


LOG_FILE = _resolve_log_file()


def setup_logging() -> logging.Logger:
    """Configure root logging for the application and return a module logger."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    file_logging_ready = True
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))
    except OSError:
        file_logging_ready = False

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    logger = logging.getLogger("applauncher")
    if not file_logging_ready:
        logger.warning("File logging disabled; cannot open log file: %s", LOG_FILE)
    return logger
