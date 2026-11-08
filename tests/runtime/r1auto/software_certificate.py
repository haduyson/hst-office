# SPDX-License-Identifier: AGPL-3.0-only
"""A disposable native certificate for W14; never upload private material."""
import os
from pathlib import Path
import secrets
import subprocess
import tempfile


def install():
    from support import RUNTIME
    import sys
    sys.path.insert(0, str(RUNTIME))
    from pdf_signature_fixtures import _throwaway_signer
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    with tempfile.TemporaryDirectory(prefix="r1-certificate-") as folder:
        path = Path(folder)
        _throwaway_signer(folder)
        key = serialization.load_pem_private_key((path / "throwaway-key.pem").read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate((path / "throwaway-cert.pem").read_bytes())
        password = secrets.token_urlsafe(24)
        bundle = path / "certificate.pfx"
        bundle.write_bytes(pkcs12.serialize_key_and_certificates(b"R1 synthetic", key, cert, None,
                           serialization.BestAvailableEncryption(password.encode())))
        command = ("$ErrorActionPreference='Stop'; $p=ConvertTo-SecureString $env:R1_PFX_PASSWORD -AsPlainText -Force; "
                   "Import-PfxCertificate -FilePath $env:R1_PFX_FILE -CertStoreLocation Cert:\\CurrentUser\\My "
                   "-Password $p | Out-Null")
        done = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True,
                              env=dict(os.environ, R1_PFX_PASSWORD=password, R1_PFX_FILE=str(bundle)))
        if done.returncode:
            raise RuntimeError("Không cài được chứng thư kiểm thử vào kho người dùng")
        return cert.fingerprint(hashes.SHA1()).hex().upper()


def remove(thumbprint):
    if len(thumbprint) != 40 or any(c not in "0123456789ABCDEF" for c in thumbprint):
        raise ValueError("Mã chứng thư không hợp lệ")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Remove-Item -LiteralPath 'Cert:\\CurrentUser\\My\\" + thumbprint + "' -Force -ErrorAction Stop"],
                   check=True, capture_output=True)
