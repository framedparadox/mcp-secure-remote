"""mTLS SSL context builder."""
import ssl
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MtlsOptions:
    cert_path: str | None = None
    key_path: str | None = None
    ca_path: str | None = None
    passphrase: str | None = None
    pfx_path: str | None = None
    servername: str | None = None
    min_version: str | None = None        # "TLSv1.2" | "TLSv1.3"
    reject_unauthorized: bool = True


def has_mtls_config(opts: MtlsOptions) -> bool:
    return bool(
        opts.cert_path
        or opts.key_path
        or opts.ca_path
        or opts.pfx_path
        or opts.passphrase
        or opts.servername
        or opts.min_version
        or not opts.reject_unauthorized
    )


def build_ssl_context(opts: MtlsOptions) -> ssl.SSLContext:
    if opts.pfx_path:
        if opts.cert_path or opts.key_path:
            raise ValueError("Use either --tls-pfx OR --tls-cert/--tls-key, not both.")
        ctx = _build_from_pfx(opts)
    else:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if opts.cert_path or opts.key_path:
            if not opts.cert_path or not opts.key_path:
                raise ValueError("Both --tls-cert and --tls-key must be provided together.")
            password = opts.passphrase.encode() if opts.passphrase else None
            try:
                ctx.load_cert_chain(opts.cert_path, opts.key_path, password=password)
            except (FileNotFoundError, OSError) as e:
                raise ValueError(f"Unable to load client cert/key: {e}") from e
        elif opts.passphrase:
            raise ValueError(
                "--tls-passphrase requires --tls-pfx OR --tls-cert/--tls-key; "
                "passphrase alone has nothing to decrypt."
            )

    # Unconditional floor — applies to both PFX and non-PFX contexts.
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    if opts.ca_path:
        try:
            ctx.load_verify_locations(cafile=opts.ca_path)
        except (FileNotFoundError, OSError) as e:
            raise ValueError(f"Unable to load CA bundle at '{opts.ca_path}': {e}") from e

    if opts.min_version:
        if opts.min_version == "TLSv1.3":
            ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        elif opts.min_version == "TLSv1.2":
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        else:
            raise ValueError(f"Unknown TLS version: {opts.min_version}")

    if not opts.reject_unauthorized:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    return ctx


def _build_from_pfx(opts: MtlsOptions) -> ssl.SSLContext:
    # `cryptography` is a direct dependency of the `mcp` package — always present.
    from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption  # type: ignore[import]

    password = opts.passphrase.encode() if opts.passphrase else None
    try:
        pfx_data = Path(opts.pfx_path).read_bytes()  # type: ignore[arg-type]
    except (FileNotFoundError, OSError) as e:
        raise ValueError(f"Unable to load PKCS#12 bundle at '{opts.pfx_path}': {e}") from e

    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(pfx_data, password)
    except ValueError as e:
        raise ValueError(f"Unable to decode PKCS#12 bundle at '{opts.pfx_path}': {e}") from e

    if certificate is None or private_key is None:
        raise ValueError(f"PKCS#12 bundle at '{opts.pfx_path}' contains no certificate or private key.")

    cert_pem = certificate.public_bytes(Encoding.PEM)
    key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

    # Chain intermediates if present
    chain_pem = b"".join(c.public_bytes(Encoding.PEM) for c in (additional_certs or []))

    # create_default_context loads system CAs and sets check_hostname=True /
    # verify_mode=CERT_REQUIRED, matching the behaviour of the non-PFX path.
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    import tempfile, os

    # mkstemp gives a raw fd — write and close before ssl reads it, then unlink.
    cert_fd, cert_tmp = tempfile.mkstemp(suffix=".pem")
    key_fd, key_tmp = tempfile.mkstemp(suffix=".pem")
    try:
        try:
            os.write(cert_fd, cert_pem + chain_pem)
        finally:
            os.close(cert_fd)
        try:
            os.write(key_fd, key_pem)
        finally:
            os.close(key_fd)
        ctx.load_cert_chain(cert_tmp, key_tmp)
    finally:
        # Zero-fill before unlinking to limit key exposure window.
        for path, data in ((cert_tmp, cert_pem), (key_tmp, key_pem)):
            try:
                with open(path, "wb") as f:
                    f.write(b"\x00" * len(data))
                os.unlink(path)
            except OSError:
                pass

    return ctx
