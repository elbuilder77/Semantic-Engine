import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from ses.core.rag import OfflineRAGEngine

@pytest.mark.asyncio
async def test_engine_search_no_rust():
    with patch("ses.core.rag.RUST_AVAILABLE", False):
        service = OfflineRAGEngine()
        service.model = MagicMock()
        service.model.encode.return_value = [0.1] * 384
        service.vector_store = MagicMock()
        service.vector_store.search = AsyncMock(return_value=[])
        
        res = await service.search("test_ns", "hello")
        assert res["results"] == []
        assert "processing_time_ms" in res

@pytest.mark.asyncio
async def test_engine_ingest_file_flow():
    service = OfflineRAGEngine()
    service.model = MagicMock()
    mock_res = MagicMock()
    mock_res.tolist.return_value = [[0.1] * 384]
    service.model.encode.return_value = mock_res
    service.vector_store = MagicMock()
    service.vector_store.ensure_collection = AsyncMock()
    service.vector_store.upsert_points = AsyncMock()
    
    from io import BytesIO
    file_obj = BytesIO(b"some dummy text content")
    
    with patch("ses.core.parsers.extract_text_content", return_value="some dummy text content"):
        result = await service.ingest_file("test_ns", file_obj, "test.txt", {})
        
    assert result["status"] == "success"
    assert result["chunks_count"] > 0
    service.vector_store.upsert_points.assert_called_once()

@pytest.mark.asyncio
async def test_ingest_file_uses_deterministic_mount_ids():
    service = OfflineRAGEngine()
    service.model = MagicMock()
    mock_res = MagicMock()
    mock_res.tolist.return_value = [[0.1] * 384]
    service.model.encode.return_value = mock_res
    service.vector_store = MagicMock()
    service.vector_store.ensure_collection = AsyncMock()
    service.vector_store.upsert_points = AsyncMock()

    from io import BytesIO
    metadata = {
        "source_path": "/mnt/contracts/a.txt",
        "content_hash": "abc123",
    }

    with patch("ses.core.parsers.extract_text_content", return_value="same text"):
        first = await service.ingest_file("test_ns", BytesIO(b"same text"), "a.txt", metadata)
        first_points = service.vector_store.upsert_points.call_args.kwargs["points"]
        service.vector_store.upsert_points.reset_mock()
        second = await service.ingest_file("test_ns", BytesIO(b"same text"), "a.txt", metadata)
        second_points = service.vector_store.upsert_points.call_args.kwargs["points"]

    assert first["document_id"] == second["document_id"]
    assert [p.id for p in first_points] == [p.id for p in second_points]
