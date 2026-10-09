"""Entry point for the application launcher."""
import sys

from applauncher.gui.app import run_app
from applauncher.logger import setup_logging


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--verify-design":
        from applauncher.gui.design_verification import verify_design
        return verify_design(sys.argv[2:])
    setup_logging()
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
