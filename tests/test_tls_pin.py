"""Tests for TLS SPKI pinning helpers."""
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from mcp_secure_remote.tls_pin import (
    compute_spki_pin,
    normalize_tls_pin,
    parse_tls_pins,
    verify_spki_pin,
)


def _make_cert_der() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        .not_valid_after(__import__("datetime").datetime.now(__import__("datetime").timezone.utc) + __import__("datetime").timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)


def test_normalize_tls_pin():
    assert normalize_tls_pin("sha256/abc123==") == "abc123=="


def test_parse_tls_pins_accepts_base64_and_hex():
    hex_pin = "a" * 64
    assert parse_tls_pins(["abc123==", hex_pin], "--tls-pin-sha256") == ["abc123==", hex_pin]


def test_parse_tls_pins_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        parse_tls_pins([], "--tls-pin-sha256")


def test_verify_spki_pin_accepts_matching_pin():
    der = _make_cert_der()
    b64, _hex = compute_spki_pin(der)
    verify_spki_pin(der, [b64])


def test_verify_spki_pin_rejects_mismatch():
    der = _make_cert_der()
    with pytest.raises(Exception, match="pin mismatch"):
        verify_spki_pin(der, ["AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="])
