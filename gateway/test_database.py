import hashlib

import pytest

from gateway.database import SQLiteDatabaseAdapter


@pytest.mark.asyncio
async def test_bootstrap_key_has_administrator_role(tmp_path):
    adapter = SQLiteDatabaseAdapter(str(tmp_path / "gateway.db"))
    await adapter.connect()

    raw_key = "ses_test_bootstrap_administrator_key_2026"
    await adapter.bootstrap_admin_key(raw_key)

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    stored = await adapter.get_api_key(key_hash)

    assert stored is not None
    assert stored["role"] == "admin"
    assert stored["key"] == key_hash
    assert raw_key not in stored.values()


@pytest.mark.asyncio
async def test_created_key_is_returned_once_and_cached_as_hash(tmp_path):
    adapter = SQLiteDatabaseAdapter(str(tmp_path / "gateway.db"))
    await adapter.connect()

    result = await adapter.create_api_key(
        name="Test Client",
        namespace="requested_namespace",
        rate_limit=50,
        role="client",
    )

    raw_key = result["key"]
    expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    assert raw_key.startswith("ses_")
    assert result["key_details"]["key"] == expected_hash
    assert result["key_details"]["key"] != raw_key
