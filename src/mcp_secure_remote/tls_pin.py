"""TLS SPKI certificate pinning helpers."""
from __future__ import annotations

import base64
import hashlib
import re
import ssl
from typing import Callable

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

_BASE64_PIN_RE = re.compile(r"^[A-Za-z0-9+/=]+$")
_HEX_PIN_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def normalize_tls_pin(pin: str) -> str:
    trimmed = pin.strip()
    if trimmed.startswith("sha256/"):
        return trimmed[len("sha256/") :]
    return trimmed


def parse_tls_pins(raw_pins: list[str], flag: str) -> list[str]:
    pins = [normalize_tls_pin(pin) for pin in raw_pins if normalize_tls_pin(pin)]
    if not pins:
        raise ValueError(f"{flag} requires at least one non-empty SHA-256 SPKI pin")
    for pin in pins:
        if not (_BASE64_PIN_RE.match(pin) or _HEX_PIN_RE.match(pin)):
            raise ValueError(
                f'{flag} pin "{pin}" must be base64 or hex SHA-256 of the server certificate SPKI'
            )
    return pins


def compute_spki_pin(cert_der: bytes) -> tuple[str, str]:
    cert = x509.load_der_x509_certificate(cert_der)
    spki = cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    digest = hashlib.sha256(spki).digest()
    return base64.b64encode(digest).decode("ascii"), digest.hex()


def verify_spki_pin(cert_der: bytes, pins: list[str]) -> None:
    b64, hex_ = compute_spki_pin(cert_der)
    normalized = {normalize_tls_pin(pin) for pin in pins}
    if b64 not in normalized and hex_ not in normalized:
        raise ssl.SSLError("TLS certificate SPKI pin mismatch")


def apply_tls_pins(ctx: ssl.SSLContext, pins: list[str]) -> None:
    normalized = parse_tls_pins(pins, "--tls-pin-sha256")

    def _verify_callback(
        _conn: ssl.SSLSocket,
        cert: bytes,
        _errnum: int,
        depth: int,
        ok: bool,
    ) -> bool:
        if not ok:
            return False
        if depth == 0:
            verify_spki_pin(cert, normalized)
        return True

    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.set_verify(ssl.CERT_REQUIRED, _verify_callback)
