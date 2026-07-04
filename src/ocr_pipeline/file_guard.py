"""Large-file guard for document processing.

Warns or skips files exceeding a configurable size threshold to
prevent out-of-memory conditions during in-memory text extraction.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default: warn at 500 MB, refuse at 2 GB
DEFAULT_WARN_MB = 500
DEFAULT_REFUSE_MB = 2000


def check_file_size(
    file_path: Path,
    warn_mb: int = DEFAULT_WARN_MB,
    refuse_mb: int = DEFAULT_REFUSE_MB,
) -> bool:
    """Check if a file is safe to process in-memory.

    Returns:
        ``True`` if the file is safe to process.  ``False`` if it should
        be skipped (size exceeds *refuse_mb*).
    """
    try:
        size_mb = file_path.stat().st_size / (1024 * 1024)
    except OSError:
        return True  # Can't stat — let the caller decide

    if size_mb > refuse_mb:
        logger.warning(
            "Skipping %s (%.1f MB > %d MB refuse threshold)",
            file_path.name,
            size_mb,
            refuse_mb,
        )
        return False

    if size_mb > warn_mb:
        logger.warning(
            "Processing large file %s (%.1f MB) — may use significant memory",
            file_path.name,
            size_mb,
        )

    return True
