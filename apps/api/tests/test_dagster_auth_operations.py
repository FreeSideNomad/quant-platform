"""Unit tests for the shared GraphQL operation classifier.

Lives in `app.dagster_auth.operations` (not under `app.bff.*`) because it
is the single source of truth for both:
  * the BFF reverse proxy (`app.bff.dagster_proxy`, this task), and
  * the API passthrough (`app.api.dagster_graphql`, Task 1.5.4).

Both surfaces gate `mutation` and `subscription` to the `quant` / `admin`
roles, so they must classify identically.
"""

from __future__ import annotations

import pytest

from app.dagster_auth.operations import classify_graphql_operation


@pytest.mark.unit
@pytest.mark.parametrize(
    ("body_text", "expected"),
    [
        ("query Foo { instance { info } }", "query"),
        ("  query  Foo  { instance { info } }", "query"),
        ("mutation Terminate($id: String!) { terminateRun(runId: $id) { __typename } }", "mutation"),
        ("subscription Logs($id: ID!) { pipelineRunLogs(runId: $id) { __typename } }", "subscription"),
        ("{ instance { info } }", "query"),  # anonymous shorthand
        ("# leading comment\nquery Foo { instance { info } }", "query"),
        ("# only a comment", "unknown"),
        ("", "unknown"),
        ("not graphql at all", "unknown"),
        ("QUERY Foo { instance { info } }", "query"),  # case-insensitive
        ("\n\n  mutation { x }", "mutation"),
    ],
)
def test_classify_graphql_operation_table(body_text: str, expected: str):
    assert classify_graphql_operation(body_text) == expected
