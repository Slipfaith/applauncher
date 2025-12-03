"""Logging configuration for the application launcher."""
import logging
from pathlib import Path

LOG_FILE = Path("launcher.log")


def setup_logging() -> logging.Logger:
    """Configure root logging for the application and return a module logger."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True) if LOG_FILE.parent != Path('') else None

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )
    return logging.getLogger("applauncher")
