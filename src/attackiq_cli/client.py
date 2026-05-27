from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urljoin

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from attackiq_cli import __version__
from attackiq_cli.spec import Operation


@dataclass
class AuthContext:
    account_token: str | None
    jwt: str | None
    preferred_scheme: str = "auto"  # auto | account-token | jwt | none

    def build_headers(self, operation: Operation) -> dict[str, str]:
        scheme = self._select_scheme(operation)
        if scheme == "account-token":
            if not self.account_token:
                raise ValueError("Account Token required but not configured.")
            return {"Authorization": f"Token {self.account_token}"}
        if scheme == "jwt":
            if not self.jwt:
                raise ValueError("JWT required but not configured.")
            return {"Authorization": f"Bearer {self.jwt}"}
        return {}

    def _select_scheme(self, operation: Operation) -> str:
        if self.preferred_scheme in {"account-token", "jwt", "none"}:
            return self.preferred_scheme
        security_entries = operation.security or []
        scheme_names = [list(entry.keys())[0] for entry in security_entries if entry]
        if "Account Token" in scheme_names and self.account_token:
            return "account-token"
        if "JSON Web Token" in scheme_names and self.jwt:
            return "jwt"
        if self.account_token:
            return "account-token"
        if self.jwt:
            return "jwt"
        return "none"


class AttackIQClient:
    def __init__(
        self,
        base_url: str,
        auth: AuthContext,
        verify_tls: bool = True,
        timeout: float = 30.0,
        logger: logging.Logger | None = None,
        client: httpx.Client | None = None,
        client_factory: Callable[[], httpx.Client] | None = None,
    ):
        if not base_url:
            raise ValueError("Base URL is required.")
        if timeout <= 0:
            raise ValueError("Timeout must be a positive number of seconds.")
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.verify_tls = verify_tls
        self.timeout = timeout
        self.user_agent = f"attackiq-cli/{__version__}"
        self.logger = logger or logging.getLogger(__name__)
        self._client = client
        self._client_factory = client_factory
        self._owns_client = client is None

    def __enter__(self) -> AttackIQClient:
        self._get_client()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._client and self._owns_client:
            self._client.close()

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            if self._client_factory:
                self._client = self._client_factory()
            else:
                self._client = httpx.Client(verify=self.verify_tls, timeout=self.timeout)
        return self._client

    def send(
        self,
        operation: Operation,
        *,
        path_params: dict[str, Any],
        query_params: dict[str, Any],
        headers: dict[str, str],
        json_body: Any = None,
        data_body: Any = None,
        files: list[tuple[str, tuple[str, Any, str | None]]] | None = None,
    ) -> httpx.Response:
        if _is_retry_safe_method(operation.method):
            return self._send_with_retry(
                operation,
                path_params=path_params,
                query_params=query_params,
                headers=headers,
                json_body=json_body,
                data_body=data_body,
                files=files,
            )
        return self._send_once(
            operation,
            path_params=path_params,
            query_params=query_params,
            headers=headers,
            json_body=json_body,
            data_body=data_body,
            files=files,
        )

    @retry(
        retry=retry_if_exception(lambda exc: _is_retryable_exception(exc)),
        wait=wait_exponential(multiplier=0.5, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _send_with_retry(
        self,
        operation: Operation,
        *,
        path_params: dict[str, Any],
        query_params: dict[str, Any],
        headers: dict[str, str],
        json_body: Any = None,
        data_body: Any = None,
        files: list[tuple[str, tuple[str, Any, str | None]]] | None = None,
    ) -> httpx.Response:
        return self._send_once(
            operation,
            path_params=path_params,
            query_params=query_params,
            headers=headers,
            json_body=json_body,
            data_body=data_body,
            files=files,
        )

    def _send_once(
        self,
        operation: Operation,
        *,
        path_params: dict[str, Any],
        query_params: dict[str, Any],
        headers: dict[str, str],
        json_body: Any = None,
        data_body: Any = None,
        files: list[tuple[str, tuple[str, Any, str | None]]] | None = None,
    ) -> httpx.Response:
        url = urljoin(f"{self.base_url}/", render_path(operation.path, path_params).lstrip("/"))
        request_headers = {"User-Agent": self.user_agent}
        request_headers.update(headers)
        request_headers.update(self.auth.build_headers(operation))
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "request.prepared",
                extra={
                    "event": "request.prepared",
                    "fields": {
                        "method": operation.method.upper(),
                        "url": url,
                        "verify_tls": self.verify_tls,
                        "timeout": self.timeout,
                        "path_params": path_params,
                        "query_params": query_params,
                        "headers": redact_headers(request_headers),
                        "has_json_body": json_body is not None,
                        "has_data_body": data_body is not None,
                        "has_files": bool(files),
                    },
                },
            )
        start = time.monotonic()
        try:
            client = self._get_client()
            response = client.request(
                method=operation.method,
                url=url,
                params=query_params or None,
                json=json_body,
                data=data_body,
                files=files,
                headers=request_headers,
            )
        except httpx.RequestError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self.logger.error(
                "request.error",
                extra={
                    "event": "request.error",
                    "fields": {
                        "method": operation.method.upper(),
                        "url": url,
                        "duration_ms": elapsed_ms,
                        "error": exc.__class__.__name__,
                    },
                },
            )
            raise
        elapsed_ms = int((time.monotonic() - start) * 1000)
        level = logging.INFO
        if response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING
        self.logger.log(
            level,
            "request.completed",
            extra={
                "event": "request.completed",
                "fields": {
                    "method": operation.method.upper(),
                    "url": url,
                    "status_code": response.status_code,
                    "duration_ms": elapsed_ms,
                },
            },
        )
        response.raise_for_status()
        return response


def paginate_results(
    client: AttackIQClient,
    operation: Operation,
    *,
    page_size: int,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    max_pages: int | None = None,
) -> Iterable[dict[str, Any]]:
    page = 1
    base_params: dict[str, Any] = {}
    if query_params:
        base_params = dict(query_params)
        requested_page = base_params.pop("page", None)
        if requested_page is not None:
            page = int(requested_page)
            if page < 1:
                raise ValueError("page must be >= 1.")
    path_params = path_params or {}
    headers = headers or {}
    while True:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if base_params:
            params.update(base_params)
        data = client.send(
            operation,
            path_params=path_params,
            query_params=params,
            headers=headers,
        ).json()
        items = data.get("results", [])
        if not items:
            break
        yield from items
        if not data.get("next"):
            break
        page += 1
        if max_pages is not None and page > max_pages:
            break


def fetch_by_ids(
    client: AttackIQClient,
    operation: Operation,
    ids: Iterable[str],
    *,
    path_param: str = "id",
    query_params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    max_workers: int = 4,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    id_list = [item for item in ids if item]
    if max_workers <= 1 or len(id_list) <= 1:
        for item_id in id_list:
            results[item_id] = client.send(
                operation,
                path_params={path_param: item_id},
                query_params=query_params or {},
                headers=headers or {},
            ).json()
        return results

    import concurrent.futures

    headers = headers or {}
    query_params = query_params or {}

    def fetch_one(item_id: str) -> tuple[str, dict[str, Any]]:
        payload = client.send(
            operation,
            path_params={path_param: item_id},
            query_params=query_params,
            headers=headers,
        ).json()
        return item_id, payload

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, item_id): item_id for item_id in id_list}
        for future in concurrent.futures.as_completed(futures):
            item_id = futures[future]
            try:
                fetched_id, payload = future.result()
            except Exception as exc:
                raise RuntimeError(f"Failed to fetch {path_param}={item_id}") from exc
            results[fetched_id] = payload
    return results


SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "x-access-token",
    "x-jwt",
    "api-key",
}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if key_lower in SENSITIVE_HEADERS or "token" in key_lower or "jwt" in key_lower:
            redacted[key] = "***"
        else:
            redacted[key] = value
    return redacted


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    # Backward-compatible alias for existing imports/tests.
    return redact_headers(headers)


def validate_auth_for_operation(
    operation: Operation,
    auth: AuthContext,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    requires_auth = bool(operation.security)
    scheme = auth._select_scheme(operation)

    if scheme == "account-token" and not auth.account_token:
        errors.append(
            "Account Token required for this request. Set --account-token or "
            "ATTACKIQ_ACCOUNT_TOKEN."
        )
    elif scheme == "jwt" and not auth.jwt:
        errors.append("JWT required for this request. Set --jwt or ATTACKIQ_JWT.")
    elif requires_auth and scheme == "none":
        if auth.preferred_scheme == "none":
            warnings.append(
                "Operation declares authentication but --auth-scheme none was selected."
            )
        else:
            errors.append(
                "No auth token configured for this operation. Use attackiq auth set or env vars."
            )

    return errors, warnings


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status >= 500 or status == 429
    return False


def _is_retry_safe_method(method: str) -> bool:
    return method.strip().lower() in {"get", "head", "options"}


def render_path(path_template: str, path_params: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in path_params:
            raise KeyError(f"Missing path parameter '{key}'.")
        return quote(str(path_params[key]), safe="")

    return re.sub(r"{([^}]+)}", replace, path_template)
