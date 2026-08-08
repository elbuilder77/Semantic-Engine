"""Tests for watcher reindexing, cleanup recovery, and event filtering."""

import asyncio
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

from ses.watcher.monitor import SESHandler


class _CompletedFuture:
    def __init__(self, result):
        self._result = result

    def result(self, timeout=None):
        return self._result


def _submit_results(*results):
    pending = iter(results)

    def submit(coroutine, loop):
        coroutine.close()
        return _CompletedFuture(next(pending))

    return submit


def _make_handler(tmp_path, source_path, previous_entry):
    manifest_path = tmp_path / "mount-manifest.json"
    manifest_path.write_text(
        json.dumps({"files": {str(source_path): previous_entry}}),
        encoding="utf-8",
    )
    service = MagicMock()
    service.ingest_file = AsyncMock()
    service.delete_document = AsyncMock()
    handler = SESHandler(
        service=service,
        loop=asyncio.new_event_loop(),
        namespace="test_ns",
        debounce_seconds=0.01,
        manifest_path=str(manifest_path),
    )
    return handler, service, manifest_path


def test_unsupported_extension_is_not_scheduled(tmp_path):
    source_path = tmp_path / "image.png"
    source_path.write_bytes(b"png")
    handler, _, _ = _make_handler(tmp_path, source_path, {})

    handler._schedule(str(source_path))

    assert handler._timers == {}
    handler.loop.close()


def test_failed_stale_cleanup_is_persisted_for_retry(tmp_path):
    source_path = tmp_path / "document.txt"
    source_path.write_text("new content", encoding="utf-8")
    previous_entry = {
        "content_hash": hashlib.sha256(b"old content").hexdigest(),
        "document_id": "old-document-id",
        "filename": source_path.name,
        "source_path": str(source_path),
        "status": "indexed",
    }
    handler, service, manifest_path = _make_handler(
        tmp_path,
        source_path,
        previous_entry,
    )

    with patch(
        "ses.watcher.monitor.asyncio.run_coroutine_threadsafe",
        side_effect=_submit_results(
            {"status": "success", "document_id": "new-document-id", "chunks_count": 1},
            False,
        ),
    ):
        handler._debounce_fire(str(source_path))

    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))["files"][
        str(source_path)
    ]
    assert persisted["document_id"] == "new-document-id"
    assert persisted["status"] == "indexed_cleanup_pending"
    assert persisted["pending_delete_document_ids"] == ["old-document-id"]
    service.delete_document.assert_called_once_with("test_ns", "old-document-id")
    handler.loop.close()


def test_pending_cleanup_is_removed_after_successful_retry(tmp_path):
    source_path = tmp_path / "document.txt"
    source_path.write_text("current content", encoding="utf-8")
    current_hash = hashlib.sha256(b"current content").hexdigest()
    previous_entry = {
        "content_hash": current_hash,
        "document_id": "current-document-id",
        "pending_delete_document_ids": ["old-document-id"],
        "status": "indexed_cleanup_pending",
    }
    handler, _, manifest_path = _make_handler(
        tmp_path,
        source_path,
        previous_entry,
    )

    with patch(
        "ses.watcher.monitor.asyncio.run_coroutine_threadsafe",
        side_effect=_submit_results(True),
    ):
        remaining = handler._cleanup_stale_documents(
            str(source_path),
            previous_entry["pending_delete_document_ids"],
        )

    assert remaining == []
    previous_entry.pop("pending_delete_document_ids")
    previous_entry["status"] = "indexed"
    handler._manifest[str(source_path)] = previous_entry
    from ses.watcher.monitor import _save_manifest

    _save_manifest(str(manifest_path), handler._manifest)
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))["files"][
        str(source_path)
    ]
    assert persisted["status"] == "indexed"
    assert "pending_delete_document_ids" not in persisted
    handler.loop.close()


def test_ingest_without_document_id_preserves_previous_manifest(tmp_path):
    source_path = tmp_path / "document.txt"
    source_path.write_text("new content", encoding="utf-8")
    previous_entry = {
        "content_hash": hashlib.sha256(b"old content").hexdigest(),
        "document_id": "old-document-id",
        "status": "indexed",
    }
    handler, service, manifest_path = _make_handler(
        tmp_path,
        source_path,
        previous_entry,
    )

    with patch(
        "ses.watcher.monitor.asyncio.run_coroutine_threadsafe",
        side_effect=_submit_results({"status": "success", "chunks_count": 1}),
    ):
        handler._debounce_fire(str(source_path))

    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))["files"][
        str(source_path)
    ]
    assert persisted == previous_entry
    service.delete_document.assert_not_called()
    handler.loop.close()
