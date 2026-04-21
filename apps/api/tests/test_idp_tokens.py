"""Unit tests for the IdP: JWKS shape, token minting, verification."""

from __future__ import annotations

import jwt
import pytest

from app.config import get_settings
from app.idp.keys import current_signing_key, jwks_document
from app.idp.tokens import UpstreamIdentity, mint_tokens, verify_token


@pytest.fixture
def identity() -> UpstreamIdentity:
    return UpstreamIdentity(
        upstream_idp="mock",
        upstream_sub="mock|admin",
        email="admin@example.test",
        name="Admin User",
        roles=["admin", "quant", "viewer"],
        tenant_id="acme",
    )


@pytest.mark.unit
def test_jwks_document_shape() -> None:
    doc = jwks_document()
    assert "keys" in doc
    assert len(doc["keys"]) == 1
    k = doc["keys"][0]
    assert k["kty"] == "RSA"
    assert k["alg"] == "RS256"
    assert k["use"] == "sig"
    assert "kid" in k
    assert "n" in k and "e" in k


@pytest.mark.unit
def test_mint_access_token_claims(identity: UpstreamIdentity) -> None:
    tokens = mint_tokens(identity)
    claims = verify_token(tokens.access_token, expected_kind="access")
    settings = get_settings()
    assert claims["iss"] == settings.idp_issuer
    assert claims["aud"] == settings.idp_token_audience
    assert claims["sub"].startswith("qp|mock|")
    assert claims["email"] == "admin@example.test"
    assert set(claims["roles"]) == {"admin", "quant", "viewer"}
    assert claims["tenant_id"] == "acme"
    assert claims["typ"] == "access"
    assert claims["upstream_idp"] == "mock"
    assert "jti" in claims
    assert claims["exp"] > claims["iat"]


@pytest.mark.unit
def test_mint_id_and_refresh_distinct(identity: UpstreamIdentity) -> None:
    tokens = mint_tokens(identity)
    id_claims = verify_token(tokens.id_token, expected_kind="id")
    refresh_claims = verify_token(tokens.refresh_token, expected_kind="refresh")
    assert id_claims["typ"] == "id"
    assert refresh_claims["typ"] == "refresh"
    # Refresh TTL is substantially longer than access TTL.
    assert refresh_claims["exp"] > id_claims["exp"] + 3600


@pytest.mark.unit
def test_verify_rejects_wrong_kind(identity: UpstreamIdentity) -> None:
    tokens = mint_tokens(identity)
    with pytest.raises(jwt.InvalidTokenError):
        verify_token(tokens.refresh_token, expected_kind="access")


@pytest.mark.unit
def test_token_header_carries_kid(identity: UpstreamIdentity) -> None:
    tokens = mint_tokens(identity)
    headers = jwt.get_unverified_header(tokens.access_token)
    assert headers["kid"] == current_signing_key().kid
    assert headers["alg"] == "RS256"
