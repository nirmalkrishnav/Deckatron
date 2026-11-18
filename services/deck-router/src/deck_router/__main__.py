"""Run deck-router with Uvicorn using the shared environment settings."""

import logging
import sys

import uvicorn
from pydantic import ValidationError

from deck_router.app import create_app
from deck_router.utils.settings import Settings

logger = logging.getLogger(__name__)


def main() -> int:
    """Start the local server, returning exit code 2 for invalid configuration."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        settings = Settings()
    except ValidationError as error:
        logger.error("Invalid deck-router configuration: %s", error)
        return 2

    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
