"""Single source of truth for GraphQL operation classification.

Both `app.bff.dagster_proxy` (browser-facing, cookie auth) and
`app.api.dagster_graphql` (SDK-facing, Bearer-token auth) gate
`mutation` and `subscription` operations to the `quant` / `admin`
roles. They MUST classify operations identically — that is what this
module exists to guarantee.
"""

from __future__ import annotations

import re
from typing import Literal

_OPERATION_RE = re.compile(r"^\s*(query|mutation|subscription)\b", re.IGNORECASE)

GraphQLOperation = Literal["query", "mutation", "subscription", "unknown"]


def classify_graphql_operation(body_text: str) -> GraphQLOperation:
    """Return 'query', 'mutation', 'subscription', or 'unknown'.

    The classifier is intentionally textual — it walks lines, skips
    comments and blanks, then matches the first significant token. An
    anonymous shorthand `{ ... }` is treated as a query (matching the
    GraphQL spec).
    """
    if not isinstance(body_text, str):
        return "unknown"
    for raw_line in body_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _OPERATION_RE.match(line)
        if match:
            return match.group(1).lower()  # type: ignore[return-value]
        if line.startswith("{"):
            return "query"
        break
    return "unknown"
