"""Unit tests for the PQ_S3_* -> AWS_*/MLFLOW_S3_ENDPOINT_URL shim.

The shim exists because boto3 + MLflow's S3 artifact store read non-PQ
env names directly. Tests pin three behaviors:
  1. with no pre-existing AWS_* set, the shim populates them from PQ_S3_*
  2. with a matching pre-existing AWS_* set, the shim is silent
  3. with a CONFLICTING pre-existing AWS_* set, the shim warns AND overrides
"""
from __future__ import annotations

import logging

import pytest

from quantplatform.sdk._config import apply_mlflow_s3_env


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear AWS_*/MLFLOW_S3 + set PQ_S3_* to known canaries each test."""
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "MLFLOW_S3_ENDPOINT_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PQ_S3_ACCESS_KEY", "test-access-key-from-pq")
    monkeypatch.setenv("PQ_S3_SECRET_KEY", "test-secret-key-from-pq")
    monkeypatch.setenv("PQ_S3_ENDPOINT_URL", "http://test-minio:19000")


def test_shim_populates_aws_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    apply_mlflow_s3_env()

    assert os.environ["AWS_ACCESS_KEY_ID"] == "test-access-key-from-pq"
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == "test-secret-key-from-pq"
    assert os.environ["MLFLOW_S3_ENDPOINT_URL"] == "http://test-minio:19000"


def test_shim_silent_when_aws_already_matches(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access-key-from-pq")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key-from-pq")
    monkeypatch.setenv("MLFLOW_S3_ENDPOINT_URL", "http://test-minio:19000")

    with caplog.at_level(logging.WARNING, logger="quantplatform.sdk._config"):
        apply_mlflow_s3_env()

    # No warnings emitted because pre-existing values match what we'd set.
    assert not any(
        rec.levelno == logging.WARNING for rec in caplog.records
    ), [r.message for r in caplog.records]


def test_shim_warns_and_overrides_on_conflict(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Pre-existing AWS_ACCESS_KEY_ID with a DIFFERENT value gets shadowed
    + a warning is logged so the user knows their shell credential was
    overridden for the strategy subprocess."""
    import os

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAREALPRODUCTIONKEY")

    with caplog.at_level(logging.WARNING, logger="quantplatform.sdk._config"):
        apply_mlflow_s3_env()

    # Override happened
    assert os.environ["AWS_ACCESS_KEY_ID"] == "test-access-key-from-pq"
    # Warning emitted
    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("AWS_ACCESS_KEY_ID" in m and "shadowing" in m for m in warning_msgs), (
        f"expected a 'shadowing AWS_ACCESS_KEY_ID' warning; got {warning_msgs}"
    )


def test_shim_redacts_secret_in_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The warning must redact the credential value so it doesn't land in
    log files or terminal scrollback in plaintext."""
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "verylongprodsecretvaluexyz12345")

    with caplog.at_level(logging.WARNING, logger="quantplatform.sdk._config"):
        apply_mlflow_s3_env()

    warning_text = "\n".join(
        rec.getMessage() for rec in caplog.records if rec.levelno == logging.WARNING
    )
    # The redacted form is "ver…345"; the full credential must not appear.
    assert "verylongprodsecretvaluexyz12345" not in warning_text
    assert "ver" in warning_text  # head retained for diagnosis
