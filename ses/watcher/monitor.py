"""
SES File Watcher with debounce and content-hash deduplication.

Watches configured directories for file changes and schedules ingestion
into the semantic engine.  Two safety mechanisms prevent duplicate work:

1. **Debounce** — after a file event, a timer starts.  If more events
   arrive for the *same path* within ``DEBOUNCE_SECONDS``, the timer
   resets.  Only when the timer expires is the file actually ingested.
2. **Content-hash dedup** — before ingesting, a SHA-256 hash of the
   file is computed.  If the hash matches the last-ingested version,
   the file is skipped.
"""

import hashlib
import json
import os
import logging
import asyncio
import threading
from typing import Dict, List, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ses.core.rag import OfflineRAGEngine as UnifiedSearchService, get_vector_service
from ses.config import WATCH_DIRECTORIES, PERSONAL_NAMESPACE, DEBOUNCE_SECONDS, MOUNT_MANIFEST_PATH

from .scanner import scan_directory

logger = logging.getLogger(__name__)


def _load_manifest(path: str) -> Dict[str, Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        files = payload.get("files", {})
        return files if isinstance(files, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Cannot load mount manifest %s: %s", path, exc)
        return {}


def _save_manifest(path: str, files: Dict[str, Dict]) -> None:
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"files": files}, f, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.error("Cannot save mount manifest %s: %s", path, exc)


def _file_sha256(path: str) -> Optional[str]:
    """Return hex SHA-256 of *path*, or None if unreadable."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        return h.hexdigest()
    except (OSError, IOError) as exc:
        logger.warning("Cannot hash %s: %s", path, exc)
        return None


class SESHandler(FileSystemEventHandler):
    """Filesystem event handler with per-path debounce and hash dedup."""

    def __init__(
        self,
        service: UnifiedSearchService,
        loop: asyncio.AbstractEventLoop,
        namespace: str,
        debounce_seconds: float = 2.0,
        manifest_path: str = MOUNT_MANIFEST_PATH,
    ):
        self.service = service
        self.loop = loop
        self.namespace = namespace
        self.debounce_seconds = debounce_seconds
        self.manifest_path = manifest_path
        self._manifest = _load_manifest(manifest_path)

        # Supported extensions from parsers.py
        self.supported_extensions = {".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md"}

        # Debounce timers keyed by absolute path
        self._timers: Dict[str, threading.Timer] = {}
        self._timer_lock = threading.Lock()

        # Hash of the last successfully ingested version, keyed by path
        self._ingested_hashes: Dict[str, str] = {
            path: entry.get("content_hash", "")
            for path, entry in self._manifest.items()
            if isinstance(entry, dict) and entry.get("content_hash")
        }

    # ------------------------------------------------------------------
    # watchdog callbacks
    # ------------------------------------------------------------------

    def on_modified(self, event):
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._handle_delete(event.src_path)

    # ------------------------------------------------------------------
    # debounce logic
    # ------------------------------------------------------------------

    def _schedule(self, file_path: str):
        """Start or reset the debounce timer for *file_path*."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.supported_extensions:
            return

        abs_path = os.path.abspath(file_path)

        with self._timer_lock:
            existing = self._timers.get(abs_path)
            if existing is not None:
                existing.cancel()
                logger.debug("Debounce reset for %s", abs_path)

            timer = threading.Timer(
                self.debounce_seconds,
                self._debounce_fire,
                args=(abs_path,),
            )
            timer.daemon = True
            self._timers[abs_path] = timer
            timer.start()

    def _cleanup_stale_documents(self, abs_path: str, document_ids: List[str]) -> List[str]:
        """Delete stale document versions and return IDs that still need cleanup."""
        remaining = []
        for document_id in dict.fromkeys(doc_id for doc_id in document_ids if doc_id):
            try:
                delete_future = asyncio.run_coroutine_threadsafe(
                    self.service.delete_document(self.namespace, document_id),
                    self.loop,
                )
                deleted = delete_future.result(timeout=120)
                if deleted is not True:
                    remaining.append(document_id)
                    logger.error(
                        "Failed to delete stale document %s for %s; cleanup remains pending",
                        document_id,
                        abs_path,
                    )
            except Exception as exc:
                remaining.append(document_id)
                logger.error(
                    "Failed to delete stale document %s for %s: %s",
                    document_id,
                    abs_path,
                    exc,
                )
        return remaining

    def _debounce_fire(self, abs_path: str):
        """Called when the debounce timer expires — actually process the file."""
        with self._timer_lock:
            self._timers.pop(abs_path, None)

        # Content-hash dedup check
        current_hash = _file_sha256(abs_path)
        if current_hash is None:
            # File disappeared between event and timer — skip silently
            return

        previous_hash = self._ingested_hashes.get(abs_path)
        if current_hash == previous_hash:
            logger.info(
                "⏭️  Skipping %s — content unchanged (hash %s…)",
                os.path.basename(abs_path),
                current_hash[:12],
            )
            return

        logger.info("🔄 Ingesting %s (hash %s…)", os.path.basename(abs_path), current_hash[:12])
        previous_entry = self._manifest.get(abs_path, {})

        try:
            previous_doc_id = previous_entry.get("document_id")

            with open(abs_path, "rb") as f:
                metadata = {
                    "source": "local_watcher",
                    "source_path": abs_path,
                    "abs_path": abs_path,
                    "filename": os.path.basename(abs_path),
                    "content_hash": current_hash,
                }
                future = asyncio.run_coroutine_threadsafe(
                    self.service.ingest_file(
                        namespace=self.namespace,
                        file_obj=f,
                        filename=os.path.basename(abs_path),
                        metadata=metadata,
                    ),
                    self.loop,
                )
                # Wait for result so we only mark the hash on success
                result = future.result(timeout=120)

            if result.get("status") == "success":
                new_doc_id = result.get("document_id")
                if not new_doc_id:
                    logger.error(
                        "Ingest succeeded without a document_id for %s; preserving previous manifest",
                        abs_path,
                    )
                    return

                stale_doc_ids = list(
                    previous_entry.get("pending_delete_document_ids", [])
                )
                if previous_doc_id and previous_doc_id != new_doc_id:
                    stale_doc_ids.append(previous_doc_id)
                stale_doc_ids = [
                    document_id
                    for document_id in stale_doc_ids
                    if document_id != new_doc_id
                ]
                pending_delete_ids = self._cleanup_stale_documents(
                    abs_path,
                    stale_doc_ids,
                )

                self._ingested_hashes[abs_path] = current_hash
                manifest_entry = {
                    "content_hash": current_hash,
                    "document_id": new_doc_id,
                    "filename": os.path.basename(abs_path),
                    "source_path": abs_path,
                    "status": (
                        "indexed_cleanup_pending"
                        if pending_delete_ids
                        else "indexed"
                    ),
                }
                if pending_delete_ids:
                    manifest_entry["pending_delete_document_ids"] = pending_delete_ids
                self._manifest[abs_path] = manifest_entry
                _save_manifest(self.manifest_path, self._manifest)
                logger.info(
                    "✅ Ingested %s — %d chunks",
                    os.path.basename(abs_path),
                    result.get("chunks_count", 1),
                )
            else:
                logger.warning("⚠️ Ingest returned non-success for %s: %s", abs_path, result)

        except Exception as exc:
            logger.error("❌ Error ingesting %s: %s", abs_path, exc)

    # ------------------------------------------------------------------
    # deletion
    # ------------------------------------------------------------------

    def _handle_delete(self, file_path: str):
        abs_path = os.path.abspath(file_path)
        logger.info("🗑️ File deletion detected: %s", abs_path)
        # Cancel any pending timer
        with self._timer_lock:
            timer = self._timers.pop(abs_path, None)
            if timer is not None:
                timer.cancel()
        # Clear cached hash
        self._ingested_hashes.pop(abs_path, None)
        previous_entry = self._manifest.pop(abs_path, None)
        if previous_entry:
            _save_manifest(self.manifest_path, self._manifest)
            previous_doc_id = previous_entry.get("document_id")
            if previous_doc_id and self.loop is not None:
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.service.delete_document(self.namespace, previous_doc_id),
                        self.loop,
                    )
                    future.result(timeout=120)
                except Exception as exc:
                    logger.error("Error deleting indexed chunks for %s: %s", abs_path, exc)

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------

    def cancel_all(self):
        """Cancel every pending timer (called on shutdown)."""
        with self._timer_lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()


class SESWatcher:
    """Manages the Observer and SESHandler lifecycle."""

    def __init__(self, directories: List[str] = None):
        self.directories = directories or []
        self.observer = Observer()
        self.namespace = PERSONAL_NAMESPACE or "personal_default"
        self.service = None
        self.loop = None
        self._handler: Optional[SESHandler] = None

    def init_loop(self):
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def start(self):
        if not self.directories:
            logger.warning("⚠️ No directories configured for SES Watcher.")
            return

        self.service = get_vector_service()
        if not self.loop:
            self.init_loop()

        self._handler = SESHandler(
            self.service,
            self.loop,
            self.namespace,
            debounce_seconds=DEBOUNCE_SECONDS,
            manifest_path=MOUNT_MANIFEST_PATH,
        )

        for directory in self.directories:
            if os.path.exists(directory):
                logger.info("👀 Watching directory: %s", directory)
                self.observer.schedule(self._handler, directory, recursive=True)
            else:
                logger.warning("⚠️ Directory does not exist: %s", directory)

        # Run initial scan before starting live observer
        self._initial_scan()

        self.observer.start()
        logger.info(
            "🚀 SES Watcher started (debounce=%.1fs, dedup=sha256).",
            DEBOUNCE_SECONDS,
        )

    def _initial_scan(self):
        """
        Scan all configured directories and ingest files not yet indexed.

        This enforces the mount-mode contract:
        - Source directories are read-only (never modified).
        - Files are identified by absolute path + SHA-256 hash.
        - ``source_path`` is stored in each chunk's metadata.
        - Already-indexed files (same hash) are skipped.
        """
        total_ingested = 0
        total_skipped = 0

        for directory in self.directories:
            manifest = scan_directory(directory)

            for entry in manifest:
                abs_path = entry["path"]
                content_hash = entry["content_hash"]

                # Check if this exact version is already indexed
                previous_hash = self._handler._ingested_hashes.get(abs_path)
                if content_hash == previous_hash:
                    previous_entry = self._handler._manifest.get(abs_path, {})
                    pending_delete_ids = previous_entry.get(
                        "pending_delete_document_ids",
                        [],
                    )
                    if pending_delete_ids:
                        remaining = self._handler._cleanup_stale_documents(
                            abs_path,
                            pending_delete_ids,
                        )
                        if remaining:
                            previous_entry["pending_delete_document_ids"] = remaining
                            previous_entry["status"] = "indexed_cleanup_pending"
                        else:
                            previous_entry.pop("pending_delete_document_ids", None)
                            previous_entry["status"] = "indexed"
                        _save_manifest(
                            self._handler.manifest_path,
                            self._handler._manifest,
                        )
                    total_skipped += 1
                    continue

                try:
                    with open(abs_path, "rb") as f:
                        metadata = {
                            "source": "initial_scan",
                            "source_path": abs_path,
                            "filename": entry["filename"],
                            "content_hash": content_hash,
                            "size_bytes": entry["size_bytes"],
                        }
                        future = asyncio.run_coroutine_threadsafe(
                            self.service.ingest_file(
                                namespace=self.namespace,
                                file_obj=f,
                                filename=entry["filename"],
                                metadata=metadata,
                            ),
                            self.loop,
                        )
                        result = future.result(timeout=120)

                    if result.get("status") == "success":
                        self._handler._ingested_hashes[abs_path] = content_hash
                        self._handler._manifest[abs_path] = {
                            "content_hash": content_hash,
                            "document_id": result.get("document_id"),
                            "filename": entry["filename"],
                            "source_path": abs_path,
                            "size_bytes": entry["size_bytes"],
                            "status": "indexed",
                        }
                        _save_manifest(
                            self._handler.manifest_path,
                            self._handler._manifest,
                        )
                        total_ingested += 1
                        logger.debug(
                            "Scan: ingested %s (%d chunks)",
                            entry["filename"],
                            result.get("chunks_count", 1),
                        )
                    else:
                        logger.warning(
                            "Scan: ingest failed for %s: %s",
                            abs_path, result,
                        )
                except Exception as exc:
                    logger.error("Scan: error ingesting %s: %s", abs_path, exc)

        logger.info(
            "📂 Initial scan complete: %d ingested, %d skipped (unchanged).",
            total_ingested, total_skipped,
        )

    def stop(self):
        if self._handler is not None:
            self._handler.cancel_all()
        self.observer.stop()
        self.observer.join()
        logger.info("🛑 SES Watcher stopped.")
