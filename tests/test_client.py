from typing import cast

import httpx

from attackiq_cli.client import (
    AttackIQClient,
    AuthContext,
    fetch_by_ids,
    paginate_results,
    redact_headers,
    validate_auth_for_operation,
)
from attackiq_cli.spec import Operation


def test_redact_headers_masks_authorization():
    headers = {
        "Authorization": "Bearer secret",
        "X-Request-Id": "abc123",
    }
    redacted = redact_headers(headers)
    assert redacted["Authorization"] == "***"
    assert redacted["X-Request-Id"] == "abc123"


def test_redact_headers_masks_common_token_headers():
    headers = {
        "X-Api-Key": "secret",
        "X-Access-Token": "secret",
        "X-Auth-Token": "secret",
        "X-JWT": "secret",
        "Proxy-Authorization": "secret",
        "X-Request-Id": "abc123",
    }
    redacted = redact_headers(headers)
    assert redacted["X-Api-Key"] == "***"
    assert redacted["X-Access-Token"] == "***"
    assert redacted["X-Auth-Token"] == "***"
    assert redacted["X-JWT"] == "***"
    assert redacted["Proxy-Authorization"] == "***"
    assert redacted["X-Request-Id"] == "abc123"


def test_redact_headers_masks_cookie_headers():
    headers = {
        "Cookie": "session=alpha; theme=dark",
        "Set-Cookie": "session=alpha; HttpOnly",
        "X-Request-Id": "abc123",
    }
    redacted = redact_headers(headers)
    assert redacted["Cookie"] == "***"
    assert redacted["Set-Cookie"] == "***"
    assert redacted["X-Request-Id"] == "abc123"


def test_validate_auth_missing_account_token():
    operation = Operation(
        operation_id="op",
        method="get",
        path="/",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[{"Account Token": []}],
    )
    auth = AuthContext(account_token=None, jwt=None, preferred_scheme="account-token")
    errors, warnings = validate_auth_for_operation(operation, auth)
    assert errors
    assert not warnings


def test_validate_auth_missing_jwt():
    operation = Operation(
        operation_id="op",
        method="get",
        path="/",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[{"JSON Web Token": []}],
    )
    auth = AuthContext(account_token=None, jwt=None, preferred_scheme="jwt")
    errors, warnings = validate_auth_for_operation(operation, auth)
    assert errors
    assert not warnings


def test_validate_auth_prefers_warning_for_auth_scheme_none():
    operation = Operation(
        operation_id="op",
        method="get",
        path="/",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[{"Account Token": []}],
    )
    auth = AuthContext(account_token=None, jwt=None, preferred_scheme="none")
    errors, warnings = validate_auth_for_operation(operation, auth)
    assert not errors
    assert warnings


def test_paginate_results_yields_all_items():
    operation = Operation(
        operation_id="op",
        method="get",
        path="/items",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class ResponseStub:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class ClientStub:
        def __init__(self):
            self.calls = []

        def send(self, _op, **kwargs):
            query_params = kwargs["query_params"]
            self.calls.append(query_params["page"])
            if query_params["page"] == 1:
                return ResponseStub({"results": [{"id": 1}], "next": "page=2"})
            return ResponseStub({"results": [{"id": 2}], "next": None})

    client = ClientStub()
    items = list(paginate_results(cast(AttackIQClient, client), operation, page_size=1))
    assert items == [{"id": 1}, {"id": 2}]
    assert client.calls == [1, 2]


def test_paginate_results_respects_max_pages():
    operation = Operation(
        operation_id="op",
        method="get",
        path="/items",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class ResponseStub:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class ClientStub:
        def __init__(self):
            self.calls = []

        def send(self, _op, **kwargs):
            query_params = kwargs["query_params"]
            self.calls.append(query_params["page"])
            return ResponseStub({"results": [{"id": query_params["page"]}], "next": "page=2"})

    client = ClientStub()
    items = list(
        paginate_results(cast(AttackIQClient, client), operation, page_size=1, max_pages=1)
    )
    assert items == [{"id": 1}]
    assert client.calls == [1]


def test_paginate_results_uses_page_as_starting_point():
    operation = Operation(
        operation_id="op",
        method="get",
        path="/items",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class ResponseStub:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class ClientStub:
        def __init__(self):
            self.calls = []

        def send(self, _op, **kwargs):
            query_params = kwargs["query_params"]
            page = query_params["page"]
            self.calls.append(page)
            if page < 4:
                return ResponseStub({"results": [{"id": page}], "next": "next-page"})
            return ResponseStub({"results": [{"id": page}], "next": None})

    client = ClientStub()
    items = list(
        paginate_results(
            cast(AttackIQClient, client), operation, page_size=10, query_params={"page": 2}
        )
    )
    assert items == [{"id": 2}, {"id": 3}, {"id": 4}]
    assert client.calls == [2, 3, 4]


def test_fetch_by_ids_sequential():
    operation = Operation(
        operation_id="op",
        method="get",
        path="/items/{id}",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )

    class ResponseStub:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class ClientStub:
        def __init__(self):
            self.calls = []

        def send(self, _op, **kwargs):
            item_id = kwargs["path_params"]["id"]
            self.calls.append(item_id)
            return ResponseStub({"id": item_id})

    client = ClientStub()
    results = fetch_by_ids(cast(AttackIQClient, client), operation, ["a", "b"], max_workers=1)
    assert results == {"a": {"id": "a"}, "b": {"id": "b"}}
    assert client.calls == ["a", "b"]


def test_send_retries_safe_get_requests():
    operation = Operation(
        operation_id="op",
        method="get",
        path="/items",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )
    request = httpx.Request("GET", "https://example.com/items")
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ConnectTimeout("timeout", request=request)
        return httpx.Response(200, request=request, json={"ok": True})

    transport = httpx.MockTransport(handler)
    raw_client = httpx.Client(transport=transport)
    client = AttackIQClient(
        base_url="https://example.com",
        auth=AuthContext(account_token=None, jwt=None),
        client=raw_client,
    )

    response = client.send(operation, path_params={}, query_params={}, headers={})
    assert response.json() == {"ok": True}
    assert attempts["count"] == 2


def test_send_does_not_retry_non_idempotent_post_requests():
    operation = Operation(
        operation_id="op",
        method="post",
        path="/items",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )
    request = httpx.Request("POST", "https://example.com/items")
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ConnectTimeout("timeout", request=request)

    transport = httpx.MockTransport(handler)
    raw_client = httpx.Client(transport=transport)
    client = AttackIQClient(
        base_url="https://example.com",
        auth=AuthContext(account_token=None, jwt=None),
        client=raw_client,
    )

    try:
        client.send(operation, path_params={}, query_params={}, headers={})
    except httpx.ConnectTimeout:
        pass
    else:
        raise AssertionError("Expected timeout for POST request")
    assert attempts["count"] == 1
