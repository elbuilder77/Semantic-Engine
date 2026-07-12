import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import redis.asyncio as aioredis

os.environ.setdefault("DEBUG", "true")

from ses.config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD

@pytest.fixture(autouse=True)
def mock_external_dependencies():
    # 1. Mock SentenceTransformer
    mock_model = MagicMock()
    mock_encode_res = MagicMock()
    mock_encode_res.tolist.return_value = [[0.1] * 384]
    mock_model.encode.return_value = mock_encode_res
    
    # 2. Mock AsyncQdrantClient
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection = AsyncMock()
    mock_qdrant.create_collection = AsyncMock()
    mock_qdrant.upsert = AsyncMock()
    
    mock_res = MagicMock()
    mock_res.points = []
    mock_qdrant.query_points = AsyncMock(return_value=mock_res)
    mock_qdrant.query_batch_points = AsyncMock(return_value=[])
    mock_qdrant.retrieve = AsyncMock(return_value=[])
    mock_qdrant.delete = AsyncMock()
    mock_qdrant.delete_collection = AsyncMock()
    
    # 3. Mock Redis
    mock_redis = AsyncMock()
    mock_redis.hget = AsyncMock(return_value=None)
    mock_redis.sadd = AsyncMock()
    mock_redis.smembers = AsyncMock(return_value=set())
    mock_redis.keys = AsyncMock(return_value=[])
    mock_redis.delete = AsyncMock()
    mock_redis.close = AsyncMock()
    
    # Apply patches
    with patch("ses.core.rag.SentenceTransformer", return_value=mock_model), \
         patch("ses.core.vector_store.AsyncQdrantClient", return_value=mock_qdrant), \
         patch("ses.core.rag.redis.Redis", return_value=mock_redis):
        
        yield {
            "model": mock_model,
            "qdrant": mock_qdrant,
            "redis": mock_redis
        }
