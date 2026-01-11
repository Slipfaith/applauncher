"""Entry point for the application launcher."""
import sys

from applauncher.gui.app import run_app
from applauncher.logger import setup_logging


def main() -> int:
    setup_logging()
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
