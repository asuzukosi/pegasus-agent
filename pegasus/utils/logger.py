import logging

# ansi color codes for level-based coloring
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_RESET = "\033[0m"

LEVEL_COLORS = {
    logging.DEBUG: _GREEN,
    logging.INFO: _GREEN,
    logging.WARNING: _YELLOW,
    logging.ERROR: _RED,
    logging.CRITICAL: _RED,
}


class ColoredFormatter(logging.Formatter):
    """Format log records with level-based colors."""

    def format(self, record: logging.LogRecord) -> str:
        color = LEVEL_COLORS.get(record.levelno, _RESET)
        return f"{color}{super().format(record)}{_RESET}"


_handler = logging.StreamHandler()
_handler.setFormatter(
    ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.propagate = False