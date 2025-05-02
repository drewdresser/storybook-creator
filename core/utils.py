# core/utils.py
import re
import logging
from pathlib import Path


def setup_logging(name="StoryCreator", level=logging.INFO) -> logging.Logger:
    """Sets up basic console logging."""
    logger = logging.getLogger(name)
    if not logger.handlers:  # Avoid adding multiple handlers
        logger.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger


def sanitize_filename(text: str, max_length: int = 50) -> str:
    """Sanitize the text to create a filesystem-safe filename."""
    # Remove invalid characters
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace whitespace with underscores
    text = re.sub(r"\s+", "_", text).strip("_")
    # Truncate to max_length
    return text[:max_length]


def ensure_dir_exists(path: Path) -> None:
    """Creates a directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)
