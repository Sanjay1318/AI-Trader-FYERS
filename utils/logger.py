import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_for_output(value: object) -> str:
    """Convert non-ASCII characters to ASCII-safe substitutes for cp1252 consoles."""
    if value is None:
        return ""
    text = str(value)
    replacements = {
        "→": "->",
        "₹": "Rs",
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "’": "'",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("ascii", "ignore").decode("ascii")


class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(sanitize_for_output(msg) + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Console handler
_console = SafeStreamHandler(sys.stdout)
_console.setFormatter(_formatter)

# File handler
_file = logging.FileHandler(LOG_DIR / "trading.log", encoding="utf-8")
_file.setFormatter(_formatter)

logger = logging.getLogger("ai_trader")
logger.setLevel(logging.INFO)
logger.addHandler(_console)
logger.addHandler(_file)


def get_logger(name: str) -> logging.Logger:
    child = logger.getChild(name)
    return child