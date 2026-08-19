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
import time
import io
from typing import Dict, List, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ses.core.rag import OfflineRAGEngine as UnifiedSearchService, get_vector_service
from ses.config import WATCH_DIRECTORIES, PERSONAL_NAMESPACE, DEBOUNCE_SECONDS, MOUNT_MANIFEST_PATH

from .scanner import scan_directory
from .connectors import DataSourceConnector, LocalFileSystemConnector, SMBDataSourceConnector

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

        # 1. Size stabilization (platform-agnostic)
        last_size = -1
        stable_time_limit = 15.0
        start_time = time.time()
        while time.time() - start_time < stable_time_limit:
            try:
                current_size = os.path.getsize(abs_path)
            except OSError:
                current_size = -1
            if current_size == last_size and current_size != -1:
                break
            last_size = current_size
            time.sleep(0.3)

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

        # 2. File opening with exponential backoff for locking/PermissionError
        f = None
        retries = 3
        backoff = 1.0
        for attempt in range(retries + 1):
            try:
                f = open(abs_path, "rb")
                break
            except (PermissionError, OSError) as exc:
                if attempt < retries:
                    logger.warning("File %s locked or inaccessible: %s. Retrying in %.1fs...", abs_path, exc, backoff)
                    time.sleep(backoff)
                    backoff *= 2.0
                else:
                    logger.error("Failed to open file %s after %d retries: %s", abs_path, retries, exc)
                    return

        try:
            previous_doc_id = previous_entry.get("document_id")

            with f:
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
        BATCH_SIZE = 50
        MAX_CONCURRENT = 10

        def get_connector(uri: str):
            """Return appropriate connector based on URI scheme."""
            if uri.lower().startswith("smb://"):
                return SMBDataSourceConnector()
            else:
                return LocalFileSystemConnector()

        async def _process_batch_async(batch):
            """Process a batch of entries with concurrency limited by semaphore."""
            semaphore = asyncio.Semaphore(MAX_CONCURRENT)

            async def _ingest_entry(entry):
                uri = entry["path"]
                content_hash = entry["content_hash"]
                filename = entry["filename"]
                size_bytes = entry["size_bytes"]
                connector = get_connector(uri)
                try:
                    # Read file content via connector
                    content = connector.read(uri)
                    if content is None:
                        logger.warning("Connector.read returned None for %s", uri)
                        return
                    # Wrap in BytesIO for ingest_file
                    file_obj = io.BytesIO(content)
                    metadata = {
                        "source": "initial_scan",
                        "source_path": uri,
                        "filename": filename,
                        "content_hash": content_hash,
                        "size_bytes": size_bytes,
                    }
                    async with semaphore:
                        result = await self.service.ingest_file(
                            namespace=self.namespace,
                            file_obj=file_obj,
                            filename=filename,
                            metadata=metadata,
                        )
                    if result.get("status") == "success":
                        self._handler._ingested_hashes[uri] = content_hash
                        self._handler._manifest[uri] = {
                            "content_hash": content_hash,
                            "document_id": result.get("document_id"),
                            "filename": filename,
                            "source_path": uri,
                            "size_bytes": size_bytes,
                            "status": "indexed",
                        }
                        _save_manifest(
                            self._handler.manifest_path,
                            self._handler._manifest,
                        )
                        nonlocal total_ingested
                        total_ingested += 1
                        logger.debug(
                            "Scan: ingested %s (%d chunks)",
                            filename,
                            result.get("chunks_count", 1),
                        )
                    else:
                        logger.warning(
                            "Scan: ingest failed for %s: %s",
                            uri, result,
                        )
                except Exception as exc:
                    logger.error("Scan: error ingesting %s: %s", uri, exc)

            # Gather all entry tasks
            tasks = [_ingest_entry(entry) for entry in batch]
            if tasks:
                await asyncio.gather(*tasks)

        total_ingested = 0
        total_skipped = 0

        for directory in self.directories:
            batch = []
            connector = get_connector(directory)  # determine connector type for this directory
            for entry in connector.scan(directory):
                uri = entry["path"]
                content_hash = entry["content_hash"]
                # Check if this exact version is already indexed
                previous_hash = self._handler._ingested_hashes.get(uri)
                if content_hash == previous_hash:
                    previous_entry = self._handler._manifest.get(uri, {})
                    pending_delete_ids = previous_entry.get(
                        "pending_delete_document_ids",
                        [],
                    )
                    if pending_delete_ids:
                        remaining = self._handler._cleanup_stale_documents(
                            uri,
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

                # Not yet indexed, add to batch
                batch.append(entry)
                if len(batch) >= BATCH_SIZE:
                    # Process the batch
                    asyncio.run_coroutine_threadsafe(
                        _process_batch_async(batch), self.loop
                    ).result()
                    batch.clear()
            # Process any remaining entries in the batch for this directory
            if batch:
                asyncio.run_coroutine_threadsafe(
                    _process_batch_async(batch), self.loop
                ).result()
                batch.clear()

        logger.info(
            "📂 Initial scan complete: %d ingested, %d skipped (unchanged).",
            total_ingested,
            total_skipped,
        )

    def stop(self):
        if self._handler is not None:
            self._handler.cancel_all()
        self.observer.stop()
        self.observer.join()
        logger.info("🛑 SES Watcher stopped.")