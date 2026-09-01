import asyncio
import copy
import hashlib
import hmac
import io
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    FastAPI,
    Request,
    HTTPException,
    Security,
    Depends,
    status,
    File,
    UploadFile,
    Form
)
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel, Field

# Core imports
from ses.core.rag import get_vector_service, OfflineRAGEngine
from ses.core.llm import LocalLLMProvider
from ses.config import DEBUG, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD

# Database imports
from gateway.database import get_database_adapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ses_enterprise_gateway")

_LEGACY_COMPROMISED_ADMIN_KEY = "ses_dev_secret_key"
_MIN_ADMIN_KEY_LENGTH = 32


def require_gateway_admin_key() -> str:
    """Return a configured bootstrap key or fail before serving traffic."""
    admin_key = os.getenv("GATEWAY_ADMIN_KEY", "").strip()
    if not admin_key:
        raise RuntimeError(
            "GATEWAY_ADMIN_KEY is required. Run scripts/rotate_local_secrets.py "
            "for local development or inject it through a production secret manager."
        )
    if hmac.compare_digest(admin_key, _LEGACY_COMPROMISED_ADMIN_KEY):
        raise RuntimeError("GATEWAY_ADMIN_KEY uses the revoked legacy development key.")
    if admin_key.lower().startswith(("replace_", "change_me")):
        raise RuntimeError("GATEWAY_ADMIN_KEY still contains an example placeholder.")
    if len(admin_key) < _MIN_ADMIN_KEY_LENGTH:
        raise RuntimeError(
            f"GATEWAY_ADMIN_KEY must contain at least {_MIN_ADMIN_KEY_LENGTH} characters."
        )
    return admin_key


def configured_cors_origins() -> List[str]:
    raw_origins = os.getenv(
        "GATEWAY_CORS_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,http://localhost:3000",
    )
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if "*" in origins:
        raise RuntimeError("GATEWAY_CORS_ORIGINS cannot contain a wildcard origin.")
    return origins


@asynccontextmanager
async def gateway_lifespan(_app: FastAPI):
    """Initialize persistent Gateway state before accepting traffic."""
    global redis_available
    if redis_client is not None:
        try:
            await redis_client.ping()
            redis_available = True
            logger.info("🔌 Connected to Redis for Enterprise Rate Limiting & Cache.")
        except Exception as e:
            redis_available = False
            logger.warning(f"⚠️ Redis ping failed: {e}. Falling back to local/in-memory limiters.")

    db = get_database_adapter()
    await db.connect()

    await db.revoke_api_key(_LEGACY_COMPROMISED_ADMIN_KEY)
    if redis_available:
        legacy_hash = hashlib.sha256(_LEGACY_COMPROMISED_ADMIN_KEY.encode()).hexdigest()
        try:
            await redis_client.delete(f"gateway:key:{legacy_hash}")
        except Exception:
            pass

    await db.bootstrap_admin_key(require_gateway_admin_key())
    yield


app = FastAPI(
    title="SES Enterprise Gateway",
    description="Commercial API Layer for SES Offline RAG Engine",
    version="1.0.0",
    lifespan=gateway_lifespan,
)

# CORS Middleware for client dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Helper to check Redis connection
redis_available = False
redis_client = None

try:
    import redis.asyncio as redis
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )
except Exception as e:
    redis_available = False
    logger.warning(f"⚠️ Redis client could not be initialized: {e}. Using In-Memory limiters.")


# --- MIDDLEWARES & AUTHENTICATOR ADAPTER ---

async def get_api_key_details(api_key: str = Depends(API_KEY_HEADER)) -> Dict[str, Any]:
    """
    Adapter Pattern for API Key Verification.
    Validates api_key against Redis cache, with automatic miss query to database.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key in header X-API-Key"
        )
    
    # Calculate SHA-256 hash
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # 1. Check Redis Cache
    if redis_available:
        try:
            redis_key_data = await redis_client.get(f"gateway:key:{key_hash}")
            if redis_key_data:
                return json.loads(redis_key_data)
        except Exception as e:
            logger.error(f"Redis get key error: {e}")

    # 2. Query Persistent SQL Database (SQLite/PostgreSQL)
    try:
        db = get_database_adapter()
        key_data = await db.get_api_key(key_hash)
        
        if key_data:
            # Sync to Redis cache (expire in 5 minutes)
            if redis_available:
                try:
                    await redis_client.setex(f"gateway:key:{key_hash}", 300, json.dumps(key_data))
                except Exception:
                    pass
            return key_data
    except Exception as e:
        logger.error(f"Database api key retrieval failed: {e}")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid or expired API Key"
    )

async def check_rate_limit(key_data: Dict[str, Any]):
    api_key_hash = key_data["key"]  # SHA-256 hash
    rate_limit = key_data.get("rate_limit", 60)
    
    current_minute = int(time.time() // 60)
    
    if redis_available:
        try:
            redis_limit_key = f"gateway:rate:{api_key_hash}:{current_minute}"
            requests_count = await redis_client.incr(redis_limit_key)
            if requests_count == 1:
                await redis_client.expire(redis_limit_key, 65)
            
            if requests_count > rate_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Allowed: {rate_limit} req/min."
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")

            if not DEBUG:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Rate limiting service unavailable.",
                )

    if not redis_available and not DEBUG:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service unavailable.",
        )

    # In-memory rate limiting fallback
    limit_key = f"{api_key_hash}:{current_minute}"
    
    # Prune old metrics keys
    pruned_limits = {k: v for k, v in in_memory_rate_limits.items() if k.endswith(str(current_minute))}
    in_memory_rate_limits.clear()
    in_memory_rate_limits.update(pruned_limits)
    
    count = in_memory_rate_limits.get(limit_key, 0) + 1
    in_memory_rate_limits[limit_key] = count
    
    if count > rate_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Allowed: {rate_limit} req/min."
        )

in_memory_rate_limits = {}

async def log_request_metric(key_data: Dict[str, Any], endpoint: str, status_code: int, latency_ms: float, tokens: int = 0):
    tenant_id = key_data.get("tenant_id")
    api_key_id = key_data.get("id")
    api_key_hash = key_data.get("key")
    key_name = key_data.get("name")
    namespace = key_data.get("namespace")
    
    # 1. Log to persistent SQL database
    try:
        db = get_database_adapter()
        await db.log_usage(
            tenant_id=tenant_id,
            api_key_id=api_key_id,
            endpoint=endpoint,
            tokens=tokens,
            latency_ms=latency_ms
        )
    except Exception as e:
        logger.error(f"Failed to log usage metrics to SQL Database: {e}")
        
    # 2. Redis dynamic charts / cache updates
    if redis_available:
        try:
            await redis_client.incr("gateway:metrics:total_requests")
            if status_code >= 400:
                await redis_client.incr("gateway:metrics:total_errors")
            if "search" in endpoint:
                await redis_client.incr("gateway:metrics:total_searches")
            elif "ingest" in endpoint:
                await redis_client.incr("gateway:metrics:total_ingestions")
                
            # Log to list
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "key_name": key_name,
                "namespace": namespace,
                "endpoint": endpoint,
                "status_code": status_code,
                "latency_ms": latency_ms
            }
            await redis_client.lpush("gateway:metrics:recent_logs", json.dumps(log_entry))
            await redis_client.ltrim("gateway:metrics:recent_logs", 0, 99) # Keep 100 logs
        except Exception as e:
            logger.error(f"Redis metrics update failed: {e}")


# --- REQUEST & RESPONSE SCHEMAS ---

class SearchRequestPayload(BaseModel):
    query: str = Field(..., description="Query string for search")
    top_k: int = Field(5, description="Number of results to return")
    threshold: float = Field(0.0, description="Minimum confidence score threshold")
    generate_answer: bool = Field(True, description="Generate natural language response using LLM")
    model_override: Optional[str] = Field(None, description="Override default Ollama model")

class IngestTextRequestPayload(BaseModel):
    text: str = Field(..., description="Raw text content to index")
    filename: str = Field(..., description="Simulated filename for the document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary")

class APIKeyCreatePayload(BaseModel):
    name: str = Field(..., description="Descriptive name for the API key client")
    namespace: str = Field("personal_default", description="Isolate search directory namespace")
    rate_limit: int = Field(60, description="Maximum requests per minute")
    role: str = Field("client", description="Security role (admin or client)")


# --- API ROUTES ---

@app.post("/api/v1/search", summary="Search vector store and generate RAG responses")
async def api_search(payload: SearchRequestPayload, key_data: Dict[str, Any] = Depends(get_api_key_details)):
    await check_rate_limit(key_data)
    t0 = time.time()
    status_code = 200
    namespace = key_data["namespace"]
    
    try:
        engine = get_vector_service()
        # 1. Vector Search
        search_result = await engine.search(
            namespace=namespace,
            query=payload.query,
            top_k=payload.top_k,
            threshold=payload.threshold
        )
        
        answer = None
        llm_status = "success"
        if payload.generate_answer:
            try:
                llm = LocalLLMProvider(model_override=payload.model_override)
                answer = await llm.generate_answer(payload.query, search_result.get("results", []))
                if "No fue posible generar una respuesta con el proveedor LLM local" in answer:
                    llm_status = "failed"
            except Exception as e:
                logger.error(f"LLM Generation failed: {e}")
                answer = f"Error generating answer with local LLM. Context search completed."
                llm_status = "failed"

        latency_ms = (time.time() - t0) * 1000
        
        # Approximate tokens/words as billing metric
        tokens_count = len(payload.query.split()) + sum(len(doc.get("text", "").split()) for doc in search_result.get("results", []))
        
        response_data = {
            "query": payload.query,
            "namespace": namespace,
            "results": search_result.get("results", []),
            "answer": answer,
            "total_documents": search_result.get("total_documents", 0),
            "search_time_ms": search_result.get("processing_time_ms", 0),
            "total_time_ms": latency_ms,
            "rust_accelerated": search_result.get("rust_acceleration", False),
            "metadata": {
                "llm_status": llm_status,
                "search_time_ms": search_result.get("processing_time_ms", 0),
                "total_time_ms": latency_ms,
            }
        }
        
        # Log metrics in background
        asyncio.create_task(
            log_request_metric(key_data, "/api/v1/search", status_code, latency_ms, tokens=tokens_count)
        )
        
        return response_data
    except Exception as e:
        status_code = 500
        latency_ms = (time.time() - t0) * 1000
        asyncio.create_task(
            log_request_metric(key_data, "/api/v1/search", status_code, latency_ms)
        )
        logger.exception("Error during search endpoint execution:")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/ingest/file", summary="Upload and index files (PDF, DOCX, XLSX, TXT)")
async def api_ingest_file(
    file: UploadFile = File(...),
    metadata_json: Optional[str] = Form(None),
    key_data: Dict[str, Any] = Depends(get_api_key_details)
):
    await check_rate_limit(key_data)
    t0 = time.time()
    status_code = 200
    namespace = key_data["namespace"]
    
    metadata = {}
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON in metadata_json")
            
    # Add upload audit metadata
    metadata["source_path"] = f"api_upload://{file.filename}"
    metadata["uploaded_by"] = key_data["name"]
    metadata["upload_time"] = datetime.now(timezone.utc).isoformat()
    
    try:
        engine = get_vector_service()
        
        contents = await file.read()
        file_obj = io_bytes_wrapper(contents)
        
        result = await engine.ingest_file(
            namespace=namespace,
            file_obj=file_obj,
            filename=file.filename,
            metadata=metadata
        )
        
        latency_ms = (time.time() - t0) * 1000
        
        # Calculate approximate words as tokens consumed
        tokens_count = len(contents) // 4
        
        asyncio.create_task(
            log_request_metric(key_data, "/api/v1/ingest/file", status_code, latency_ms, tokens=tokens_count)
        )
        
        return {
            "status": "success",
            "filename": file.filename,
            "namespace": namespace,
            "details": result,
            "time_ms": latency_ms
        }
    except Exception as e:
        status_code = 500
        latency_ms = (time.time() - t0) * 1000
        asyncio.create_task(
            log_request_metric(key_data, "/api/v1/ingest/file", status_code, latency_ms)
        )
        logger.exception("Error during file ingest endpoint execution:")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/ingest/text", summary="Directly index raw text content")
async def api_ingest_text(payload: IngestTextRequestPayload, key_data: Dict[str, Any] = Depends(get_api_key_details)):
    await check_rate_limit(key_data)
    t0 = time.time()
    status_code = 200
    namespace = key_data["namespace"]
    
    try:
        engine = get_vector_service()
        
        doc = {
            "id": str(uuid.uuid4()),
            "text": payload.text,
            "metadata": {
                **payload.metadata,
                "filename": payload.filename,
                "source_path": f"api_text://{payload.filename}",
                "uploaded_by": key_data["name"],
                "upload_time": datetime.now(timezone.utc).isoformat()
            }
        }
        
        result = await engine.index_documents(namespace=namespace, documents=[doc])
        latency_ms = (time.time() - t0) * 1000
        
        tokens_count = len(payload.text.split())
        
        asyncio.create_task(
            log_request_metric(key_data, "/api/v1/ingest/text", status_code, latency_ms, tokens=tokens_count)
        )
        
        return {
            "status": "success",
            "document_id": doc["id"],
            "namespace": namespace,
            "details": result,
            "time_ms": latency_ms
        }
    except Exception as e:
        status_code = 500
        latency_ms = (time.time() - t0) * 1000
        asyncio.create_task(
            log_request_metric(key_data, "/api/v1/ingest/text", status_code, latency_ms)
        )
        logger.exception("Error during text ingest endpoint:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/documents", summary="List documents indexed in the namespace")
async def api_list_documents(limit: int = 50, key_data: Dict[str, Any] = Depends(get_api_key_details)):
    await check_rate_limit(key_data)
    namespace = key_data["namespace"]
    try:
        engine = get_vector_service()
        docs = await engine.list_documents(namespace=namespace, limit=limit)
        return {"documents": docs, "count": len(docs), "namespace": namespace}
    except Exception as e:
        logger.exception("Error listing documents:")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/documents/{doc_id}", summary="Delete a document by ID")
async def api_delete_document(doc_id: str, key_data: Dict[str, Any] = Depends(get_api_key_details)):
    await check_rate_limit(key_data)
    namespace = key_data["namespace"]
    try:
        engine = get_vector_service()
        success = await engine.delete_document(namespace=namespace, doc_id=doc_id)
        if success:
            return {"status": "success", "message": f"Document {doc_id} deleted successfully."}
        else:
            raise HTTPException(status_code=404, detail="Document not found or could not be deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting document:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/stats", summary="Get current namespace RAG statistics")
async def api_stats(key_data: Dict[str, Any] = Depends(get_api_key_details)):
    await check_rate_limit(key_data)
    namespace = key_data["namespace"]
    try:
        engine = get_vector_service()
        stats = await engine.get_stats(namespace=namespace)
        return {"stats": stats, "namespace": namespace}
    except Exception as e:
        logger.exception("Error getting stats:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/health", summary="Detailed health monitor of satellite services")
async def api_health():
    qdrant_ok = False
    redis_ok = False
    ollama_ok = False
    
    # Check Qdrant
    try:
        engine = get_vector_service()
        await engine.vector_store.client.get_collections()
        qdrant_ok = True
    except Exception:
        pass
        
    # Check Redis
    if redis_available:
        try:
            await redis_client.ping()
            redis_ok = True
        except Exception:
            pass
            
    # Check Ollama
    try:
        from ses.config import OLLAMA_BASE_URL
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_BASE_URL.rstrip('/')}/")
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                ollama_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if qdrant_ok and (not redis_available or redis_ok) else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "services": {
            "qdrant": "connected" if qdrant_ok else "disconnected",
            "redis": "connected" if redis_ok else ("disabled" if not redis_available else "disconnected"),
            "ollama_api": "connected" if ollama_ok else "disconnected",
            "rust_acceleration": "active" if RUST_AVAILABLE_FALLBACK() else "inactive"
        }
    }


# --- ADMIN MONETIZATION & MANAGEMENT ROUTES ---

def verify_admin_key(key_data: Dict[str, Any] = Depends(get_api_key_details)):
    if key_data.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden. Admin privileges required."
        )
    return key_data

@app.get("/api/v1/admin/keys", summary="Admin endpoint to list API keys")
async def admin_list_keys(admin_data: Dict[str, Any] = Depends(verify_admin_key)):
    try:
        db = get_database_adapter()
        keys = await db.list_api_keys()
        return {"keys": keys}
    except Exception as e:
        logger.exception("Error listing keys:")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/admin/keys", summary="Admin endpoint to create API keys")
async def admin_create_key(payload: APIKeyCreatePayload, admin_data: Dict[str, Any] = Depends(verify_admin_key)):
    try:
        db = get_database_adapter()
        result = await db.create_api_key(
            name=payload.name,
            namespace=payload.namespace,
            rate_limit=payload.rate_limit,
            role=payload.role
        )
        
        # Save to Redis cache for instant activation
        if redis_available:
            new_key_data = result["key_details"]
            new_key_raw = result["key"]
            new_hash = hashlib.sha256(new_key_raw.encode()).hexdigest()
            try:
                await redis_client.setex(f"gateway:key:{new_hash}", 300, json.dumps(new_key_data))
            except Exception:
                pass
                
        logger.info(f"🔑 Created new API key for client '{payload.name}' in namespace '{payload.namespace}'")
        return result
    except Exception as e:
        logger.exception("Error creating API key:")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/admin/keys/{key_to_delete}", summary="Admin endpoint to revoke API keys")
async def admin_delete_key(key_to_delete: str, admin_data: Dict[str, Any] = Depends(verify_admin_key)):
    try:
        db = get_database_adapter()
        success = await db.revoke_api_key(key_to_delete)
        if not success:
            raise HTTPException(status_code=404, detail="API Key not found or already revoked.")
            
        # Delete from Redis cache
        if redis_available:
            try:
                # If a full key token is provided, delete its specific hash
                if key_to_delete.startswith("ses_") and len(key_to_delete) == 28:
                    key_hash = hashlib.sha256(key_to_delete.encode()).hexdigest()
                    await redis_client.delete(f"gateway:key:{key_hash}")
            except Exception as e:
                logger.error(f"Failed to clear key from Redis: {e}")
                
        logger.info(f"🚫 Revoked API key token.")
        return {"status": "success", "message": "API Key revoked successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error revoking API key:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/analytics", summary="Aggregated business and usage analytics")
async def admin_analytics(admin_data: Dict[str, Any] = Depends(verify_admin_key)):
    try:
        db = get_database_adapter()
        analytics = await db.get_analytics()
        
        # Merge with Redis live data if available
        if redis_available:
            try:
                total_reqs = await redis_client.get("gateway:metrics:total_requests")
                if total_reqs:
                    analytics["total_requests"] = int(total_reqs)
                    
                total_errs = await redis_client.get("gateway:metrics:total_errors")
                if total_errs:
                    analytics["total_errors"] = int(total_errs)
                    
                total_srch = await redis_client.get("gateway:metrics:total_searches")
                if total_srch:
                    analytics["total_searches"] = int(total_srch)
                    
                total_ingst = await redis_client.get("gateway:metrics:total_ingestions")
                if total_ingst:
                    analytics["total_ingestions"] = int(total_ingst)
            except Exception as e:
                logger.error(f"Failed to fetch live Redis analytics: {e}")
                
        return analytics
    except Exception as e:
        logger.exception("Error getting admin analytics:")
        raise HTTPException(status_code=500, detail=str(e))


# --- REPORT ENDPOINTS ---

from ses.core.reports import get_report_service

@app.post("/api/v1/reports/evidence", summary="Generate PDF audit report for a search query")
async def api_generate_evidence_report(payload: SearchRequestPayload, key_data: Dict[str, Any] = Depends(get_api_key_details)):
    await check_rate_limit(key_data)
    t0 = time.time()
    namespace = key_data["namespace"]
    
    try:
        engine = get_vector_service()
        # 1. Execute search
        search_result = await engine.search(
            namespace=namespace,
            query=payload.query,
            top_k=payload.top_k,
            threshold=payload.threshold
        )
        
        # 2. Generate LLM answer
        answer = "LLM answer generation not available."
        if payload.generate_answer:
            try:
                llm = LocalLLMProvider(model_override=payload.model_override)
                answer = await llm.generate_answer(payload.query, search_result.get("results", []))
            except Exception as e:
                logger.error(f"LLM Generation failed for report: {e}")
                answer = f"Error generating answer with local LLM. Search completed successfully."
        
        # 3. Generate PDF
        report_svc = get_report_service()
        pdf_path = report_svc.generate_evidence_pdf(
            query=payload.query,
            answer=answer,
            sources=search_result.get("results", []),
            client_id=key_data.get("name", "unknown"),
            watermark=None,
        )
        
        latency_ms = (time.time() - t0) * 1000
        asyncio.create_task(
            log_request_metric(key_data, "/api/v1/reports/evidence", 200, latency_ms)
        )
        
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path),
        )
    except Exception as e:
        latency_ms = (time.time() - t0) * 1000
        asyncio.create_task(
            log_request_metric(key_data, "/api/v1/reports/evidence", 500, latency_ms)
        )
        logger.exception("Error generating evidence report:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/admin/reports/usage", summary="Generate usage analytics PDF report")
async def admin_usage_report(admin_data: Dict[str, Any] = Depends(verify_admin_key)):
    try:
        db = get_database_adapter()
        analytics = await db.get_analytics()
        
        report_svc = get_report_service()
        pdf_path = report_svc.generate_usage_report_pdf(
            analytics_data=analytics,
            tenant_name=admin_data.get("name", "Admin"),
            period="Monthly",
        )
        
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path),
        )
    except Exception as e:
        logger.exception("Error generating usage report:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/admin/reports/health", summary="Generate system health PDF report")
async def admin_health_report(admin_data: Dict[str, Any] = Depends(verify_admin_key)):
    try:
        # Get health data
        health_resp = await api_health()
        
        # Get analytics
        db = get_database_adapter()
        analytics = await db.get_analytics()
        
        report_svc = get_report_service()
        pdf_path = report_svc.generate_system_health_pdf(
            health_data=health_resp,
            analytics_data=analytics,
            tenant_name=admin_data.get("name", "Admin"),
        )
        
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path),
        )
    except Exception as e:
        logger.exception("Error generating health report:")
        raise HTTPException(status_code=500, detail=str(e))


# --- IO WRAPPER ---

def io_bytes_wrapper(data: bytes) -> io.BytesIO:
    return io.BytesIO(data)

def RUST_AVAILABLE_FALLBACK() -> bool:
    try:
        import jas_vector_core
        return True
    except ImportError:
        return False


# --- SERVING STATIC DASHBOARD ---

@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard_root():
    static_file_path = "gateway/static/index.html"
    if os.path.exists(static_file_path):
        with open(static_file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>SES Enterprise Gateway</h1><p>Dashboard static files missing.</p>")

# Mount static files directory
if os.path.exists("gateway/static"):
    app.mount("/static", StaticFiles(directory="gateway/static"), name="static")
