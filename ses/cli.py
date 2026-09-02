"""
SES Core Unified Command-Line Interface (CLI).

Provides user-friendly commands:
  - ses mount <dir> [--namespace <ns>] [--watch]
  - ses search "<query>" [--namespace <ns>] [--top-k <k>] [--generate-answer]
  - ses ingest <file> [--namespace <ns>]
  - ses doctor / ses status
  - ses serve [--host <host>] [--port <port>]
"""

import argparse
import asyncio
import os
import sys
import time
from typing import Optional


def _get_engine():
    from ses.core.rag import OfflineRAGEngine
    return OfflineRAGEngine()


async def _run_mount(args):
    directory = os.path.abspath(args.directory)
    namespace = args.namespace or "default"
    watch = getattr(args, "watch", False)

    if not os.path.isdir(directory):
        print(f"❌ Error: Directory does not exist: {directory}", file=sys.stderr)
        sys.exit(1)

    print(f"🚀 [SES Mount] Indexing directory '{directory}' into namespace '{namespace}'...")
    from ses.watcher.scanner import scan_directory
    from ses.core.rag import OfflineRAGEngine

    engine = OfflineRAGEngine()
    start_time = time.perf_counter()
    indexed_count = 0
    failed_count = 0

    for entry in scan_directory(directory):
        fpath = entry["path"]
        fname = entry["filename"]
        try:
            with open(fpath, "rb") as f:
                res = await engine.ingest_file(
                    namespace=namespace,
                    file_obj=f,
                    filename=fname,
                    metadata={"source_path": fpath, "content_hash": entry.get("content_hash", "")}
                )
                if res.get("status") == "success":
                    indexed_count += 1
                    print(f"  ✓ Indexed: {fname} ({res.get('chunks_count', 0)} chunks)")
                else:
                    failed_count += 1
                    print(f"  ⚠️ Skipped/Failed: {fname} -> {res.get('error', 'unknown error')}")
        except Exception as e:
            failed_count += 1
            print(f"  ❌ Error indexing {fname}: {e}")

    elapsed = time.perf_counter() - start_time
    print(f"\n✨ Mount Complete! {indexed_count} files indexed ({failed_count} failed) in {elapsed:.2f}s.")

    if watch:
        print(f"👀 Starting live filesystem watcher on '{directory}' (Press Ctrl+C to stop)...")
        from ses.watcher.monitor import SESWatcher
        watcher = SESWatcher(directories=[directory], namespace=namespace)
        watcher.start()
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n🛑 Stopping watcher...")
            watcher.stop()


async def _run_search(args):
    query = args.query
    namespace = args.namespace or "default"
    top_k = args.top_k or 5
    generate_answer = getattr(args, "generate_answer", False)

    print(f"🔍 Searching namespace '{namespace}' for: \"{query}\" (top_k={top_k})...\n")
    engine = _get_engine()
    start_time = time.perf_counter()
    
    results = await engine.search(
        namespace=namespace,
        query=query,
        top_k=top_k,
        generate_answer=generate_answer
    )
    elapsed = (time.perf_counter() - start_time) * 1000

    if not results:
        print("⚠️ No matching documents found.")
        return

    print(f"⚡ Found {len(results)} results in {elapsed:.1f}ms:\n")
    for i, r in enumerate(results, 1):
        score = getattr(r, "score", 0.0)
        content = getattr(r, "content", "")
        meta = getattr(r, "metadata", {}) or {}
        fname = meta.get("filename", "unknown")
        src = meta.get("source_path", fname)
        print(f"  [{i}] Score: {score:.4f} | Source: {src}")
        snippet = content.replace("\n", " ")[:200]
        print(f"      \"{snippet}...\"\n")

    if generate_answer:
        # If local LLM generated an answer
        print("─" * 60)
        print("🧠 Synthesized Answer:")
        answer = getattr(engine, "last_generated_answer", None)
        if answer:
            print(f"{answer}\n")
        print("─" * 60)


async def _run_ingest(args):
    file_path = os.path.abspath(args.file)
    namespace = args.namespace or "default"

    if not os.path.isfile(file_path):
        print(f"❌ Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    fname = os.path.basename(file_path)
    print(f"📄 Ingesting '{fname}' into namespace '{namespace}'...")
    engine = _get_engine()

    with open(file_path, "rb") as f:
        res = await engine.ingest_file(
            namespace=namespace,
            file_obj=f,
            filename=fname,
            metadata={"source_path": file_path}
        )

    if res.get("status") == "success":
        print(f"✓ Successfully indexed '{fname}' ({res.get('chunks_count', 0)} chunks, {res.get('points_count', 0)} vectors in Qdrant).")
    else:
        print(f"❌ Ingestion failed: {res.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)


async def _run_doctor(args):
    print("🩺 Running SES Diagnostic Healthcheck...\n")
    
    # 1. Check Rust Extension
    rust_ok = False
    try:
        import jas_vector_core
        rust_ok = True
        print("  ✓ Rust Core (jas_vector_core): ACTIVE (Hardware-accelerated cosine search)")
    except ImportError:
        print("  ⚠️ Rust Core (jas_vector_core): Not loaded (Falling back to NumPy/Python)")

    # 2. Check Qdrant
    try:
        from ses.core.vector_store import QdrantVectorStore
        store = QdrantVectorStore()
        cols = await store.list_collections()
        col_names = [c.name for c in getattr(cols, "collections", [])] if hasattr(cols, "collections") else []
        print(f"  ✓ Qdrant Vector Store: CONNECTED ({len(col_names)} collections: {col_names})")
    except Exception as e:
        print(f"  ❌ Qdrant Vector Store: CONNECTION FAILED -> {e}")

    # 3. Check Redis
    try:
        import redis.asyncio as aioredis
        from ses.config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
        r = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, socket_timeout=1.0)
        pong = await r.ping()
        if pong:
            print(f"  ✓ Redis Cache: CONNECTED ({REDIS_HOST}:{REDIS_PORT})")
        await r.close()
    except Exception as e:
        print(f"  ⚠️ Redis Cache: Not reachable ({e}) - Engine will run without TTL caching")

    # 4. Check LLM Provider
    try:
        from ses.core.llm import LocalLLMProvider
        llm = LocalLLMProvider()
        print(f"  ✓ Local LLM Provider: Configured ({llm.model_name} at {llm.base_url})")
    except Exception as e:
        print(f"  ⚠️ Local LLM Provider: {e}")

    print("\n✅ Diagnostic Complete.")


def _run_serve(args):
    host = args.host or "0.0.0.0"
    port = args.port or 8000
    print(f"🌐 Starting SES Gateway on http://{host}:{port}...")
    try:
        import uvicorn
        uvicorn.run("gateway.main:app", host=host, port=port, reload=args.reload)
    except ImportError:
        print("❌ Error: Gateway dependencies missing. Run `pip install ses-core[server]` to install.", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="ses",
        description="SES (Semantic Engine) CLI — Offline-first RAG and document intelligence tool."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: mount
    mount_parser = subparsers.add_parser("mount", help="Index a directory into a namespace (Mount Mode)")
    mount_parser.add_argument("directory", type=str, help="Directory path to mount and index")
    mount_parser.add_argument("--namespace", "-n", type=str, default="default", help="Target namespace (default: 'default')")
    mount_parser.add_argument("--watch", "-w", action="store_true", help="Keep running and watch for filesystem changes")

    # Command: search
    search_parser = subparsers.add_parser("search", help="Execute a semantic query across indexed documents")
    search_parser.add_argument("query", type=str, help="Natural language query string")
    search_parser.add_argument("--namespace", "-n", type=str, default="default", help="Namespace to search in")
    search_parser.add_argument("--top-k", "-k", type=int, default=5, help="Number of results to return (default: 5)")
    search_parser.add_argument("--generate-answer", "-g", action="store_true", help="Synthesize natural answer with local LLM")

    # Command: ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a single document file")
    ingest_parser.add_argument("file", type=str, help="Path to document (PDF, DOCX, XLSX, CSV, TXT, MD)")
    ingest_parser.add_argument("--namespace", "-n", type=str, default="default", help="Target namespace")

    # Command: doctor / status
    subparsers.add_parser("doctor", help="Run system diagnostics and service connectivity tests")
    subparsers.add_parser("status", help="Alias for doctor")

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Launch the FastAPI Gateway server")
    serve_parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    serve_parser.add_argument("--port", "-p", type=int, default=8000, help="Port number (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "mount":
        asyncio.run(_run_mount(args))
    elif args.command == "search":
        asyncio.run(_run_search(args))
    elif args.command == "ingest":
        asyncio.run(_run_ingest(args))
    elif args.command in ("doctor", "status"):
        asyncio.run(_run_doctor(args))
    elif args.command == "serve":
        _run_serve(args)


if __name__ == "__main__":
    main()
