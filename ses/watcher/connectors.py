"""
Connectors for various data sources (local filesystem, SMB, etc.) used by SES Watcher.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Generator, Optional

logger = logging.getLogger(__name__)


class DataSourceConnector(ABC):
    """Abstract base class for data source connectors."""

    @abstractmethod
    def scan(self, uri: str) -> Generator[Dict[str, str], None, None]:
        """
        Scan the given URI and yield file metadata entries.

        Each entry is a dict with:
        - ``path``: absolute path or URI
        - ``filename``: basename
        - ``content_hash``: SHA-256 hex digest
        - ``size_bytes``: file size as string
        """
        pass

    @abstractmethod
    def read(self, uri: str) -> Optional[bytes]:
        """
        Read the file at *uri* and return its raw bytes, or None if unreadable.
        """
        pass


class LocalFileSystemConnector(DataSourceConnector):
    """Connector for local filesystem (default)."""

    def scan(self, directory: str) -> Generator[Dict[str, str], None, None]:
        """Delegate to the existing scanner function."""
        from .scanner import scan_directory

        yield from scan_directory(directory)

    def read(self, path: str) -> Optional[bytes]:
        """Read a local file."""
        try:
            with open(path, "rb") as f:
                return f.read()
        except (OSError, IOError) as exc:
            logger.warning("Cannot read local file %s: %s", path, exc)
            return None


# Optional SMB connector – only available if smbprotocol is installed
try:
    from smbprotocol.connection import Connection
    from smbprotocol.tree import TreeConnect
    from smbprotocol.file import File
    from smbprotocol.structures import FileAttributes
    import hashlib

    class SMBDataSourceConnector(DataSourceConnector):
        """Connector for SMB/CIFS network shares."""

        def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
            """
            Args:
                username: SMB username (optional; can be inferred from environment)
                password: SMB password (optional; can be inferred from environment)
            """
            self.username = username
            self.password = password
            self._connections: Dict[str, Connection] = {}
            self._trees: Dict[str, TreeConnect] = {}

        def _get_connection(self, host: str) -> Connection:
            """Get or create an SMB connection to *host*."""
            if host not in self._connections:
                conn = Connection(host, 445)
                if self.username and self.password:
                    conn.set_credentials(self.username, self.password)
                conn.connect()
                self._connections[host] = conn
            return self._connections[host]

        def _get_tree(self, connection: Connection, share_name: str) -> TreeConnect:
            """Get or create a tree connect to a share."""
            key = f"{connection.remote_addr}:{share_name}"
            if key not in self._trees:
                tree = TreeConnect(connection, share_name)
                tree.connect()
                self._trees[key] = tree
            return self._trees[key]

        def scan(self, uri: str) -> Generator[Dict[str, str], None, None]:
            """
            Scan an SMB URI of the form ``smb://host/share/path``.

            Note: This implementation does not support username/password in URI;
            they should be provided via constructor or environment.
            """
            if not uri.lower().startswith("smb://"):
                logger.warning("SMB connector received non-SMB URI: %s", uri)
                return

            # Strip smb:// prefix
            rest = uri[6:]
            # Split into host, share, and optional path
            parts = rest.split("/", 2)
            if len(parts) < 2:
                logger.error("Invalid SMB URI (missing host/share): %s", uri)
                return
            host, share = parts[0], parts[1]
            base_path = parts[2] if len(parts) > 2 else ""

            try:
                conn = self._get_connection(host)
                tree = self._get_tree(conn, share)
            except Exception as exc:
                logger.error("Failed to connect to SMB share %s: %s", uri, exc)
                return

            # Walk the share recursively
            try:
                for root, dirs, files in tree.walk(base_path):
                    for fname in files:
                        # Build full URI for the file
                        file_path = os.path.join(root, fname).replace("\\", "/")
                        file_uri = f"smb://{host}/{share}/{file_path}"
                        # Attempt to read file to compute hash and size
                        content = self.read(file_uri)
                        if content is None:
                            continue
                        content_hash = hashlib.sha256(content).hexdigest()
                        size = len(content)
                        yield {
                            "path": file_uri,
                            "filename": fname,
                            "content_hash": content_hash,
                            "size_bytes": str(size),
                        }
            except Exception as exc:
                logger.error("Error walking SMB share %s: %s", uri, exc)
            finally:
                # Note: We keep connections open for reuse; they will be closed
                # when the connector is garbage-collected or explicit close method added.
                pass

        def read(self, uri: str) -> Optional[bytes]:
            """Read a file from an SMB share."""
            if not uri.lower().startswith("smb://"):
                logger.warning("SMB connector received non-SMB URI for read: %s", uri)
                return None
            rest = uri[6:]
            parts = rest.split("/", 2)
            if len(parts) < 2:
                logger.error("Invalid SMB URI for read: %s", uri)
                return None
            host, share = parts[0], parts[1]
            file_path = parts[2] if len(parts) > 2 else ""
            try:
                conn = self._get_connection(host)
                tree = self._get_tree(conn, share)
                file_obj = File(tree, file_path)
                file_obj.open(desired_access=0x80000000)  # GENERIC_READ
                # Read all content (could be large; but we assume moderate size for indexing)
                content = file_obj.read_all()
                file_obj.close()
                return content
            except Exception as exc:
                logger.warning("Failed to read SMB file %s: %s", uri, exc)
                return None

except ImportError:  # pragma: no cover
    # smbprotocol not installed – provide a stub that logs warnings.
    logger = logging.getLogger(__name__)

    class SMBDataSourceConnector(DataSourceConnector):  # type: ignore
        """Stub SMB connector when smbprotocol is not available."""

        def __init__(self, *args, **kwargs):
            logger.warning(
                "SMBDataSourceConnector instantiated but smbprotocol is not installed. "
                "Install smbprotocol to enable SMB support."
            )

        def scan(self, uri: str) -> Generator[Dict[str, str], None, None]:
            logger.warning("SMB scan requested but smbprotocol not available: %s", uri)
            return

        def read(self, uri: str) -> Optional[bytes]:
            logger.warning("SMB read requested but smbprotocol not available: %s", uri)
            return None