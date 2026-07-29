"""Real loopback failure-path checks for external service clients."""

import secrets

import pytest
import redis.asyncio as redis
from redis.exceptions import RedisError

from ses.core.llm import LocalLLMProvider
from ses.core.vector_store import QdrantVectorStore


@pytest.mark.asyncio
async def test_qdrant_connection_failure_is_observable(unused_tcp_port):
    store = QdrantVectorStore(
        url=f"http://127.0.0.1:{unused_tcp_port}",
        api_key=secrets.token_hex(16),
    )
    try:
        with pytest.raises(Exception):
            await store.client.get_collections()
    finally:
        await store.client.close()


@pytest.mark.asyncio
async def test_redis_connection_failure_is_observable(unused_tcp_port):
    client = redis.Redis(
        host="127.0.0.1",
        port=unused_tcp_port,
        socket_connect_timeout=0.25,
        socket_timeout=0.25,
    )
    try:
        with pytest.raises(RedisError):
            await client.ping()
    finally:
        await client.aclose()


def test_ollama_connection_failure_returns_documented_fallback(unused_tcp_port):
    provider = LocalLLMProvider(model_override="test-model")
    provider.ollama_url = f"http://127.0.0.1:{unused_tcp_port}/api/generate"

    result = provider.generate_answer(
        query="test query",
        context_docs=[{"text": "test context"}],
    )

    assert result == (
        "No fue posible generar una respuesta con el proveedor LLM local. "
        "Verifique que Ollama esté en ejecución."
    )
