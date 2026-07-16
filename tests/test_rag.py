import asyncio

import pytest
import numpy as np
from types import SimpleNamespace
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


@pytest.mark.asyncio
async def test_engine_search_uses_numpy_rust_path_for_large_candidate_set():
    service = OfflineRAGEngine()
    service.model = MagicMock()
    service.model.encode.return_value = np.array([1.0, 0.0], dtype=np.float32)
    points = [
        SimpleNamespace(
            id=str(index),
            vector=[1.0, 0.0],
            score=0.5,
            payload={"text_snippet": f"document {index}", "indexed_at": 0},
        )
        for index in range(51)
    ]
    service.vector_store = MagicMock()
    service.vector_store.search = AsyncMock(return_value=points)
    service._get_usage_scores = AsyncMock(
        return_value={str(index): 0.0 for index in range(51)}
    )
    service._record_query = AsyncMock()
    service._get_points_count = AsyncMock(return_value=51)

    rust_search = MagicMock(
        return_value=[(index, 1.0 - index / 100.0) for index in range(51)]
    )
    rust_module = SimpleNamespace(
        cosine_similarity_search_numpy=rust_search,
        cosine_similarity_search=MagicMock(),
    )

    with patch("ses.core.rag.RUST_AVAILABLE", True), patch(
        "ses.core.rag.jas_vector_core", rust_module, create=True
    ):
        result = await service.search("test_ns", "hello", top_k=51)
        await asyncio.sleep(0)

    rust_search.assert_called_once()
    query_arg, documents_arg, top_k_arg = rust_search.call_args.args
    assert query_arg.dtype == np.float32
    assert query_arg.shape == (2,)
    assert documents_arg.dtype == np.float32
    assert documents_arg.shape == (51, 2)
    assert top_k_arg == 51
    assert result["rust_acceleration"] is True
