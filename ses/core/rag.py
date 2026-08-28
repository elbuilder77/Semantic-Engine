import asyncio
import copy
import functools
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any, BinaryIO, Dict, List, Optional

import numpy as np
from qdrant_client.http import models as qmodels

from . import parsers
from .chunking import chunk_text
from .vector_store import VECTOR_SIZE, QdrantVectorStore
from .providers import ProviderRouter, create_default_router

import redis.asyncio as redis
from ses.config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
HEX32_PATTERN = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)

EXCLUDED_METADATA_KEYS = {"text_snippet", "full_text", "original_id"}

RUST_AVAILABLE = False
try:
    import jas_vector_core

    RUST_AVAILABLE = True
    logger.info("🚀 Rust Core Activado")
except ImportError:
    logger.warning("⚠️ Rust Core no encontrado, usando Python fallback")


# Global provider router instance
_provider_router: Optional[ProviderRouter] = None
_provider_router_lock = threading.Lock()


def get_provider_router() -> ProviderRouter:
    global _provider_router
    if _provider_router is None:
        with _provider_router_lock:
            if _provider_router is None:
                _provider_router = create_default_router()
    return _provider_router


def ttl_cache(seconds: int = 60, maxsize: int = 128, copy_func=copy.deepcopy):
    def decorator(func):
        cache = OrderedDict()
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (
                (args[1:], tuple(sorted(kwargs.items())))
                if args
                else (tuple(), tuple(sorted(kwargs.items())))
            )

            with lock:
                if key in cache:
                    timestamp, val = cache[key]
                    if time.monotonic() - timestamp < seconds:
                        cache.move_to_end(key)
                        return copy_func(val)
                    del cache[key]

            val = func(*args, **kwargs)
            now = time.monotonic()

            with lock:
                cache[key] = (now, val)
                if len(cache) > maxsize:
                    cache.popitem(last=False)

            return copy_func(val)

        return wrapper

    return decorator


def async_ttl_cache(seconds: int = 60, maxsize: int = 128, copy_func=copy.deepcopy):
    def decorator(func):
        cache = OrderedDict()
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key = (
                (args[1:], tuple(sorted(kwargs.items())))
                if args
                else (tuple(), tuple(sorted(kwargs.items())))
            )

            async with lock:
                if key in cache:
                    timestamp, val = cache[key]
                    if time.monotonic() - timestamp < seconds:
                        cache.move_to_end(key)
                        return copy_func(val)
                    del cache[key]

            val = await func(*args, **kwargs)
            now = time.monotonic()

            async with lock:
                cache[key] = (now, val)
                if len(cache) > maxsize:
                    cache.popitem(last=False)

            return copy_func(val)

        return wrapper

    return decorator


class OfflineRAGEngine:
    def __init__(self, router: Optional[ProviderRouter] = None):
        logger.info("🔄 Inicializando OfflineRAGEngine conectado a Qdrant...")

        self.router = router or get_provider_router()
        primary = self.router.get_primary_provider()
        logger.info(
            "🧠 Embedding provider: %s (dim=%d)",
            primary.model_name,
            primary.dimension,
        )

        self.vector_store = QdrantVectorStore()
        self.qdrant = self.vector_store.client

        self.model_name = primary.model_name
        self.embedding_dim = primary.dimension
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )

    def _get_collection_name(self, namespace: str) -> str:
        return f"client_{namespace}"

    async def _get_points_count(self, collection_name: str) -> int:
        """Return the number of points in *collection_name*, 0 on error."""
        try:
            info = await self.vector_store.get_collection(collection_name)
            return info.points_count or 0
        except Exception:
            return 0

    def _to_uuid(self, id_str: str) -> str:
        if isinstance(id_str, uuid.UUID):
            return str(id_str)

        s_id = str(id_str)
        length = len(s_id)

        if length == 36 and UUID_PATTERN.match(s_id):
            return s_id

        if length == 32 and HEX32_PATTERN.match(s_id):
            return s_id

        if length in (36, 38, 45):
            try:
                uuid.UUID(s_id)
                return s_id
            except ValueError:
                pass

        return str(uuid.uuid5(uuid.NAMESPACE_DNS, s_id))

    async def ingest_file(
        self, namespace: str, file_obj: BinaryIO, filename: str, metadata: Dict
    ) -> Dict[str, Any]:
        collection_name = self._get_collection_name(namespace)
        await self.vector_store.ensure_collection(collection_name)

        t_extract_start = time.time()
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        text_content = await asyncio.to_thread(
            parsers.extract_text_content, file_obj, filename
        )
        await asyncio.to_thread(
            logger.info,
            "Text extraction for %s took %.4fs",
            filename,
            time.time() - t_extract_start,
        )

        # --- Chunking ---
        chunks = chunk_text(text_content, CHUNK_SIZE, CHUNK_OVERLAP)
        if not chunks:
            return {
                "status": "error",
                "message": f"No text content could be extracted from {filename}",
            }

        logger.info(
            "Document %s split into %d chunks (size=%d, overlap=%d)",
            filename, len(chunks), CHUNK_SIZE, CHUNK_OVERLAP,
        )

        start_time = time.time()

        # Batch encode all chunks at once for efficiency via provider router
        vectors = await self.router.embed(chunks)

        # Metadata filtering
        safe_metadata = {
            k: v for k, v in metadata.items() if k not in EXCLUDED_METADATA_KEYS
        }
        parent_doc_id = self._file_parent_id(filename, text_content, safe_metadata)

        points = []
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{parent_doc_id}:{idx}"))
            payload = {
                **safe_metadata,
                "filename": filename,
                "parent_document_id": parent_doc_id,
                "chunk_index": idx,
                "text_snippet": chunk[:500],
                "full_text": chunk,
                "indexed_at": time.time(),
            }
            points.append(
                qmodels.PointStruct(
                    id=chunk_id,
                    vector=vector,
                    payload=payload,
                )
            )

        await self.vector_store.upsert_points(
            collection_name=collection_name,
            points=points,
        )

        return {
            "status": "success",
            "document_id": parent_doc_id,
            "file_type": filename.split(".")[-1],
            "content_length": len(text_content),
            "chunks_count": len(chunks),
            "processing_time": time.time() - start_time,
        }

    def _file_parent_id(self, filename: str, text_content: str, metadata: Dict[str, Any]) -> str:
        source_path = metadata.get("source_path") or metadata.get("abs_path")
        content_hash = metadata.get("content_hash")

        if source_path and content_hash:
            identity = f"{source_path}:{content_hash}"
        else:
            text_digest = hashlib.sha256(text_content.encode("utf-8", errors="ignore")).hexdigest()
            identity = f"{filename}:{text_digest}"

        return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))

    async def index_documents(
        self, namespace: str, documents: List[Dict]
    ) -> Dict[str, Any]:
        collection_name = self._get_collection_name(namespace)
        await self.vector_store.ensure_collection(collection_name)

        texts = [doc["text"] for doc in documents]
        vectors = await self.router.embed(texts)

        points = []
        for i, doc in enumerate(documents):
            original_id = doc["id"]
            final_id = self._to_uuid(original_id)

            # Metadata filtering
            metadata = doc.get("metadata", {})
            safe_metadata = {
                k: v for k, v in metadata.items() if k not in EXCLUDED_METADATA_KEYS
            }

            payload = {
                **safe_metadata,
                "original_id": original_id,
                "text_snippet": doc["text"][:500],
                "full_text": doc["text"],
                "indexed_at": time.time(),
            }

            points.append(
                qmodels.PointStruct(id=final_id, vector=vectors[i], payload=payload)
            )

        if points:
            await self.vector_store.upsert_points(
                collection_name=collection_name, points=points
            )

        return {
            "indexed_count": len(points),
            "total_documents": await self._get_points_count(collection_name),
            "namespace": namespace,
        }

    async def _encode_query_cached(self, query: str) -> List[float]:
        return await self.router.embed_query(query)

    def _get_intelligent_snippet(
        self, text: str, query: str, context: int = 150
    ) -> str:
        """Extrae un fragmento de texto que contiene la consulta para mejorar la relevancia visual."""
        if not query:
            return text[: context * 2]

        # Búsqueda simple de palabras clave
        query_words = query.lower().split()
        first_word = query_words[0] if query_words else ""

        idx = text.lower().find(first_word)
        if idx == -1:
            return text[: context * 2]

        start = max(0, idx - context)
        end = min(len(text), idx + context)

        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet

    def _format_search_result(self, point, query: str = "") -> Dict[str, Any]:
        payload = point.payload
        doc_id = payload.get("original_id", str(point.id))
        full_text = payload.get("full_text", "")

        text_snippet = (
            self._get_intelligent_snippet(full_text, query)
            if full_text
            else payload.get("text_snippet", "")
        )

        # Use a dictionary comprehension for filtering metadata to avoid mutation
        metadata = {k: v for k, v in payload.items() if k not in EXCLUDED_METADATA_KEYS}

        return {
            "id": doc_id,
            "score": point.score,
            "text": text_snippet,
            "text_snippet": text_snippet,
            "metadata": metadata,
            "indexed_at": payload.get("indexed_at", 0),
        }

    async def _record_query(self, namespace: str, query: str, doc_ids: List[str]):
        """Registra la consulta y actualiza contadores de uso para el ranking."""
        try:
            today = time.strftime("%Y-%m-%d")
            # 1. Guardar en el historial global del namespace
            pipeline = self.redis.pipeline()
            pipeline.lpush(
                f"history:{namespace}", json.dumps({"q": query, "ts": time.time()})
            )
            pipeline.ltrim(
                f"history:{namespace}", 0, 99
            )  # Mantener últimos 100

            # 2. Incrementar frecuencia de uso de los documentos retornados
            for d_id in doc_ids:
                pipeline.zincrby(f"usage:{namespace}", 1, d_id)

            await pipeline.execute()
        except Exception as e:
            logger.warning(f"Error registrando consulta en Redis: {e}")

    async def _get_usage_scores(
        self, namespace: str, doc_ids: List[str]
    ) -> Dict[str, float]:
        """Obtiene las frecuencias de uso para normalizarlas en el ranking."""
        if not doc_ids:
            return {}
        try:
            pipeline = self.redis.pipeline()
            for d_id in doc_ids:
                pipeline.zscore(f"usage:{namespace}", d_id)
            results = await pipeline.execute()

            scores = {}
            for d_id, s in zip(doc_ids, results):
                scores[d_id] = float(s) if s else 0.0
            return scores
        except Exception:
            return {d_id: 0.0 for d_id in doc_ids}

    def re_rank(
        self, results: List[Dict], usage_scores: Dict[str, float]
    ) -> List[Dict]:
        """
        Ranking mejorado: combina similitud vectorial, frecuencia de uso y recencia.
        Score final = (vector_sim * 0.7) + (normalized_usage * 0.2) + (recency_boost * 0.1)
        """
        if not results:
            return []

        max_usage = max(usage_scores.values()) if usage_scores.values() else 1.0
        if max_usage == 0:
            max_usage = 1.0

        now = time.time()

        for res in results:
            v_score = res["score"]
            u_score = usage_scores.get(res["id"], 0.0) / max_usage

            # Recency boost (documentos de las últimas 24h tienen un pequeño empujón)
            age_days = (now - res.get("indexed_at", 0)) / 86400
            recency_boost = 1.0 / (1.0 + age_days)  # Decay function

            res["score"] = (v_score * 0.7) + (u_score * 0.2) + (recency_boost * 0.1)

        return sorted(results, key=lambda x: x["score"], reverse=True)

    async def search(
        self, namespace: str, query: str, top_k: int = 5, limit: int = None, threshold: float = 0.0
    ) -> Dict[str, Any]:
        if limit is not None:
            top_k = limit
        collection_name = self._get_collection_name(namespace)
        t0 = time.time()

        query_embedding = await self._encode_query_cached(query)

        if isinstance(query_embedding, np.ndarray):
            query_vector_np = query_embedding.astype(np.float32, copy=False)
            query_vector = query_vector_np.tolist()
        else:
            query_vector = (
                query_embedding.tolist()
                if hasattr(query_embedding, "tolist")
                else query_embedding
            )
            query_vector_np = np.array(query_vector, dtype=np.float32)

        try:
            search_result = await self.vector_store.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=threshold,
                with_payload=qmodels.PayloadSelectorExclude(exclude=["full_text"]),
                with_vectors=True if RUST_AVAILABLE else False,
            )
        except Exception as e:
            logger.exception("Error during Qdrant search:")
            return {"status": "error", "results": [], "total_documents": 0, "processing_time_ms": 0}

        final_results_order = []
        rust_accelerated = False

        if RUST_AVAILABLE and len(search_result) > 50:
            try:
                q_vec_np = query_vector_np
                # Offload CPU-bound numpy array creation to a thread to avoid blocking the event loop
                c_vecs_np = await asyncio.to_thread(
                    lambda: np.array(
                        [point.vector for point in search_result], dtype=np.float32
                    )
                )

                reranked_indices = await asyncio.to_thread(
                    getattr(
                        jas_vector_core,
                        "cosine_similarity_search_numpy",
                        jas_vector_core.cosine_similarity_search,
                    ),
                    q_vec_np,
                    c_vecs_np,
                    len(search_result),
                )

                for idx, new_score in reranked_indices:
                    point = search_result[idx]
                    point.score = float(new_score)
                    final_results_order.append(point)
                rust_accelerated = True

            except Exception as exc:
                logger.error(
                    "Error en Rust Acceleration: %s. Usando orden original.",
                    exc,
                    exc_info=True,
                )
                final_results_order = search_result
        else:
            final_results_order = search_result

        results = [
            self._format_search_result(point, query) for point in final_results_order
        ]

        # 4. Re-Ranking Híbrido (Cognitivo)
        usage_scores = await self._get_usage_scores(
            namespace, [r["id"] for r in results]
        )
        reranked_results = self.re_rank(results, usage_scores)

        # 5. Registrar consulta (Background)
        asyncio.create_task(
            self._record_query(
                namespace, query, [r["id"] for r in reranked_results[:3]]
            )
        )

        return {
            "status": "success",
            "results": reranked_results[:top_k],
            "total_documents": await self._get_points_count(collection_name),
            "processing_time_ms": (time.time() - t0) * 1000,
            "rust_acceleration": rust_accelerated,
        }

    async def batch_search(
        self, namespace: str, queries: List[str], top_k: int, threshold: float
    ) -> Dict[str, Any]:
        collection_name = self._get_collection_name(namespace)
        t0 = time.time()

        query_vectors = await self.router.embed(queries)

        search_queries = [
            qmodels.QueryRequest(
                query=vec,
                limit=top_k,
                score_threshold=threshold,
                with_payload=qmodels.PayloadSelectorExclude(exclude=["full_text"]),
            )
            for vec in query_vectors
        ]

        try:
            batch_results = await self.vector_store.search_batch(
                collection_name=collection_name, requests=search_queries
            )
        except Exception:
            return {
                "status": "error",
                "results": [[] for _ in queries],
                "total_documents": 0,
                "processing_time_ms": 0,
            }

        formatter = self._format_search_result
        formatted_results = [
            [formatter(point) for point in result_group]
            for result_group in batch_results
        ]

        return {
            "status": "success",
            "results": formatted_results,
            "total_documents": await self._get_points_count(collection_name),
            "processing_time_ms": (time.time() - t0) * 1000,
        }

    async def delete_document(self, namespace: str, doc_id: str) -> bool:
        collection_name = self._get_collection_name(namespace)
        final_id = self._to_uuid(doc_id)

        try:
            await self.vector_store.delete_by_payload(
                collection_name=collection_name,
                key="parent_document_id",
                value=str(doc_id),
            )
            await self.vector_store.delete(
                collection_name=collection_name,
                points=qmodels.PointIdsList(points=[final_id]),
            )
            return True
        except Exception:
            return False

    async def clear_namespace(self, namespace: str) -> None:
        collection_name = self._get_collection_name(namespace)
        try:
            await self.vector_store.delete_by_payload(
                collection_name=collection_name,
                key="namespace",
                value=namespace
            )
            await self.vector_store.delete_documents_by_namespace(namespace)
        except Exception:
            pass

    @async_ttl_cache(seconds=60, copy_func=copy.copy)
    async def get_stats(self, namespace: str) -> Dict[str, Any]:
        collection_name = self._get_collection_name(namespace)
        try:
            info = await self.vector_store.get_collection(collection_name)
            return {
                "total_documents": info.points_count,
                "embedding_dimension": VECTOR_SIZE,
                "rust_acceleration": RUST_AVAILABLE,
                "storage": "Qdrant Persistent",
            }
        except Exception:
            return {
                "total_documents": 0,
                "embedding_dimension": VECTOR_SIZE,
                "rust_acceleration": RUST_AVAILABLE,
            }

    async def get_document(
        self, namespace: str, doc_id: str
    ) -> Optional[Dict[str, Any]]:
        collection_name = self._get_collection_name(namespace)

        ids_to_try = []
        try:
            uuid.UUID(doc_id)
            ids_to_try.append(doc_id)
        except ValueError:
            pass
        hashed_id = self._to_uuid(doc_id)
        if hashed_id not in ids_to_try:
            ids_to_try.append(hashed_id)

        try:
            points = await self.vector_store.retrieve(
                collection_name=collection_name,
                ids=ids_to_try,
                with_payload=True,
            )
            if points:
                p = points[0]
                original_id = p.payload.get("original_id", str(p.id))
                return {
                    "id": original_id,
                    "text": p.payload.get("full_text", ""),
                    "metadata": p.payload,
                    "indexed_at": p.payload.get("indexed_at"),
                }
        except Exception:
            pass
        return None

    async def list_documents(
        self, namespace: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Lista los documentos más recientes indexados"""
        collection_name = self._get_collection_name(namespace)
        try:
            # Usamos un scroll para obtener los puntos
            result = await self.qdrant.scroll(
                collection_name=collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            points = result[0]

            docs = []
            for p in points:
                docs.append(
                    {
                        "id": p.payload.get("original_id", str(p.id)),
                        "text_snippet": p.payload.get("text_snippet", ""),
                        "metadata": {
                            k: v
                            for k, v in p.payload.items()
                            if k not in EXCLUDED_METADATA_KEYS
                        },
                        "indexed_at": p.payload.get("indexed_at"),
                    }
                )
            return docs
        except Exception:
            return []

    async def _ensure_initialized(self) -> None:
        """Ensure all client connections are ready (for integration tests)."""
        # Test redis connection
        await self.redis.ping()
        # Test qdrant connection by getting any collection
        try:
            await self.vector_store.get_collection("health_check_dummy")
        except Exception:
            pass  # Collection doesn't exist, but connection works


_service_instance = None
_service_lock = threading.Lock()


def get_vector_service() -> OfflineRAGEngine:
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = OfflineRAGEngine()
    return _service_instance
