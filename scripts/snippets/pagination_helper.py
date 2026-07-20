from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from attackiq_cli.client import AttackIQClient, paginate_results
from attackiq_cli.spec import Operation


# Reuse the built-in pagination helper for export-style flows.
# Copy this into a script or module and customize query params or max_pages.

def iter_paginated(
    client: AttackIQClient,
    operation: Operation,
    *,
    page_size: int,
    query_params: dict[str, Any] | None = None,
    max_pages: int | None = None,
) -> Iterable[dict[str, Any]]:
    return paginate_results(
        client,
        operation,
        page_size=page_size,
        query_params=query_params,
        max_pages=max_pages,
    )


# Example usage:
# for item in iter_paginated(client, operation, page_size=200, query_params={"status": "active"}):
#     handle(item)
