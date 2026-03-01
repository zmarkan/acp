"""Tests for redaction module."""

from git_whence.redaction import scan_and_redact, HIGH_CONFIDENCE_TYPES


def test_no_secrets():
    result = scan_and_redact("This is a normal prompt about refactoring")
    assert result.text == "This is a normal prompt about refactoring"
    assert not result.was_redacted
    assert result.secret_count == 0


def test_api_key_sk():
    result = scan_and_redact("Use key sk-abcdefghijklmnopqrstuvwx to authenticate")
    assert "[REDACTED:api-key]" in result.text
    assert "sk-abcdefghijklmnopqrstuvwx" not in result.text
    assert result.was_redacted
    assert result.secret_count == 1


def test_api_key_ghp():
    result = scan_and_redact("Token: ghp_abcdefghijklmnopqrstuvwxyz1234567890")
    assert "[REDACTED:api-key]" in result.text
    assert result.was_redacted


def test_aws_key():
    result = scan_and_redact("Key is AKIAIOSFODNN7EXAMPLE")
    assert "[REDACTED:aws-key]" in result.text
    assert result.was_redacted
    assert "aws-key" in result.high_confidence_types


def test_private_key():
    text = """Here is my key:
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA...
-----END RSA PRIVATE KEY-----
done"""
    result = scan_and_redact(text)
    assert "[REDACTED:private-key]" in result.text
    assert "BEGIN RSA PRIVATE KEY" not in result.text
    assert result.was_redacted
    assert "private-key" in result.high_confidence_types


def test_bearer_token():
    result = scan_and_redact("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.long.token.value")
    assert "[REDACTED:" in result.text
    assert result.was_redacted


def test_jwt():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    result = scan_and_redact(f"Token: {jwt}")
    assert "[REDACTED:" in result.text
    assert result.was_redacted


def test_multiple_secrets():
    text = "Key: sk-abcdefghijklmnopqrstuvwx, AWS: AKIAIOSFODNN7EXAMPLE"
    result = scan_and_redact(text)
    assert result.secret_count >= 2
    assert result.was_redacted


def test_high_confidence_types():
    assert "private-key" in HIGH_CONFIDENCE_TYPES
    assert "aws-key" in HIGH_CONFIDENCE_TYPES
