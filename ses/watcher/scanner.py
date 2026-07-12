"""
Recursive directory scanner for SES mount-mode ingestion.

Scans configured ``WATCH_DIRECTORIES`` on startup and ingests all supported
files that haven't been indexed yet (or whose content has changed).

Mount-mode contract
-------------------
- Source directories are treated as **read-only**.  SES never writes,
  moves, or deletes files in the mounted path.
- Each file's identity is determined by its **absolute path + SHA-256
  content hash**.  If the hash changes the file is re-ingested.
- Every indexed chunk carries ``source_path`` (absolute original
  location) in its metadata for full traceability.
- The scanner is idempotent: running it twice with unchanged files
  produces zero new Qdrant points.

Integration
-----------
``SESWatcher.start()`` calls ``initial_scan()`` before attaching the
live filesystem observer, so the index is populated before real-time
events begin.
"""

import hashlib
import logging
import os
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Extensions mirrored from parsers.py
SUPPORTED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md"}


def _file_sha256(path: str) -> Optional[str]:
    """Return hex SHA-256 of *path*, or ``None`` if unreadable."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        return h.hexdigest()
    except (OSError, IOError) as exc:
        logger.warning("Cannot hash %s: %s", path, exc)
        return None


def scan_directory(directory: str) -> List[Dict[str, str]]:
    """
    Recursively walk *directory* and return a manifest of supported files.

    Each entry is a dict with:
    - ``path``: absolute path
    - ``filename``: basename
    - ``content_hash``: SHA-256 hex digest
    - ``size_bytes``: file size as string

    The directory itself is never modified (read-only contract).
    """
    manifest: List[Dict[str, str]] = []

    if not os.path.isdir(directory):
        logger.warning("Scanner: directory does not exist: %s", directory)
        return manifest

    for root, _dirs, files in os.walk(directory):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            abs_path = os.path.abspath(os.path.join(root, fname))

            content_hash = _file_sha256(abs_path)
            if content_hash is None:
                continue

            try:
                size = os.path.getsize(abs_path)
            except OSError:
                size = 0

            manifest.append({
                "path": abs_path,
                "filename": fname,
                "content_hash": content_hash,
                "size_bytes": str(size),
            })

    logger.info(
        "Scanner: found %d supported files in %s",
        len(manifest), directory,
    )
    return manifest
