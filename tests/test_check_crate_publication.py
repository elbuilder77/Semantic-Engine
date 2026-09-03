from urllib.error import HTTPError, URLError

import pytest

from scripts.check_crate_publication import USER_AGENT, publication_status


class Response:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def test_existing_crate_version_uses_identified_request():
    def opener(request, timeout):
        assert request.full_url.endswith("/jas_vector_core/0.1.0")
        assert request.get_header("User-agent") == USER_AGENT
        assert timeout == 20
        return Response(200)

    assert publication_status("jas_vector_core", "0.1.0", opener) is True


def test_missing_crate_version_is_available_for_publication():
    def opener(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", {}, None)

    assert publication_status("jas_vector_core", "9.9.9", opener) is False


def test_unexpected_http_status_fails_closed():
    def opener(request, timeout):
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

    with pytest.raises(RuntimeError, match="unexpected HTTP 403"):
        publication_status("jas_vector_core", "0.1.0", opener)


def test_network_error_fails_closed():
    def opener(request, timeout):
        raise URLError("offline")

    with pytest.raises(RuntimeError, match="request failed: offline"):
        publication_status("jas_vector_core", "0.1.0", opener)
