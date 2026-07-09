import logging
import logging.handlers
from pathlib import Path

from src.core.config import settings

LOG_FILE = Path("logs/app.log")
MAX_LOG_BYTES = 20 * 1024 * 1024


def get_logger() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_LOG_BYTES, backupCount=3
    )
    stream_handler = logging.StreamHandler()

    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[file_handler, stream_handler],
    )
