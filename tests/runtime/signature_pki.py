# SPDX-License-Identifier: AGPL-3.0-only
"""Throw-away PKI on a virtual USB token for the digital-signature runtime check.

Builds, under one work directory: a SoftHSM2 token (PKCS#11, like a VNPT-CA/Viettel-CA/BKAV
USB token), a test root CA and a user certificate with a Vietnamese subject whose private key
lives only on the token, and an NSS database (what HST Office reads on Linux) with the token
module registered (modutil) and the test CA trusted. All key material is test-only, stays in
the work directory and must never be committed.
"""
import glob
import os
import shutil
import subprocess

TOKEN_LABEL = "HST-TEST-TOKEN"
USER_PIN = "123456"          # throw-away test PIN
SO_PIN = "12345678"          # throw-away test SO PIN
USER_CN = "Nguyễn Văn Thử"
MODULE_NAME = "HST Test Token"
TOOLS = ("softhsm2-util", "pkcs11-tool", "certutil", "modutil", "openssl")
SOFTHSM_CANDIDATES = ("/usr/lib/softhsm/libsofthsm2.so", "/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so",
                      "/usr/lib64/pkcs11/libsofthsm2.so", "/usr/local/lib/softhsm/libsofthsm2.so")


def missing_tools():
    missing = [tool for tool in TOOLS if not shutil.which(tool)]
    if not softhsm_module():
        missing.append("libsofthsm2.so")
    return missing


def softhsm_module():
    for path in SOFTHSM_CANDIDATES + tuple(glob.glob("/usr/lib/*/softhsm/libsofthsm2.so")):
        if os.path.exists(path):
            return path
    return None


def _run(args, env=None, stdin=None):
    result = subprocess.run(args, env=env, input=stdin, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("%s failed (%d): %s" % (args[0], result.returncode, (result.stderr or result.stdout)[-800:]))
    return result.stdout


class TokenPki:
    """Creates (once) and describes the token, certificates and NSS DB under `base`."""

    def __init__(self, base):
        self.base = os.path.abspath(base)
        self.module = softhsm_module()
        self.conf = os.path.join(self.base, "softhsm2.conf")
        self.nssdb = os.path.join(self.base, "nssdb")
        self.ca_pem = os.path.join(self.base, "ca.pem")
        self.user_pem = os.path.join(self.base, "user.pem")

    @property
    def env(self):
        return dict(os.environ, SOFTHSM2_CONF=self.conf)

    def create(self):
        if os.path.exists(os.path.join(self.nssdb, "cert9.db")):
            return self
        os.makedirs(os.path.join(self.base, "tokens"), exist_ok=True)
        with open(self.conf, "w", encoding="utf-8") as handle:
            handle.write("directories.tokendir = %s\nobjectstore.backend = file\nlog.level = ERROR\n"
                         % os.path.join(self.base, "tokens"))
        _run(["softhsm2-util", "--init-token", "--free", "--label", TOKEN_LABEL, "--pin", USER_PIN,
              "--so-pin", SO_PIN], env=self.env)
        self._certificates()
        key_der, cert_der = os.path.join(self.base, "user.key.der"), os.path.join(self.base, "user.der")
        _run(["openssl", "pkcs8", "-topk8", "-nocrypt", "-in", os.path.join(self.base, "user.key"),
              "-outform", "DER", "-out", key_der])
        _run(["openssl", "x509", "-in", self.user_pem, "-outform", "DER", "-out", cert_der])
        for path, kind in ((key_der, "privkey"), (cert_der, "cert")):
            _run(["pkcs11-tool", "--module", self.module, "--login", "--pin", USER_PIN, "--write-object", path,
                  "--type", kind, "--id", "01", "--label", "Nguyen Van Thu"], env=self.env)
        # the user key exists only on the token from here on
        for path in (key_der, os.path.join(self.base, "user.key")):
            os.remove(path)
        os.makedirs(self.nssdb, exist_ok=True)
        db = "sql:" + self.nssdb
        _run(["certutil", "-N", "-d", db, "--empty-password"])
        _run(["modutil", "-dbdir", db, "-add", MODULE_NAME, "-libfile", self.module, "-force"], env=self.env)
        _run(["certutil", "-A", "-d", db, "-n", "HST Test Root CA", "-t", "CT,C,C", "-a", "-i", self.ca_pem])
        return self

    def _certificates(self):
        b = self.base
        _run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", os.path.join(b, "ca.key"),
              "-out", self.ca_pem, "-days", "30", "-subj", "/C=VN/O=HST Test CA/CN=HST Test Root CA",
              "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign"])
        _run(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", os.path.join(b, "user.key"),
              "-out", os.path.join(b, "user.csr"), "-utf8",
              "-subj", "/C=VN/L=Đà Nẵng/O=HST Kiểm thử/CN=%s" % USER_CN])
        ext = os.path.join(b, "user.ext")
        with open(ext, "w", encoding="utf-8") as handle:
            handle.write("basicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature,nonRepudiation\n"
                         "extendedKeyUsage=emailProtection,clientAuth\nsubjectKeyIdentifier=hash\n"
                         "authorityKeyIdentifier=keyid\n")
        _run(["openssl", "x509", "-req", "-in", os.path.join(b, "user.csr"), "-CA", self.ca_pem,
              "-CAkey", os.path.join(b, "ca.key"), "-CAcreateserial", "-days", "30", "-sha256",
              "-out", self.user_pem, "-extfile", ext])

    def describe(self):
        """certutil view of the NSS DB: modules and the certificates NSS sees on the token."""
        db = "sql:" + self.nssdb
        pinfile = os.path.join(self.base, "pin.txt")
        with open(pinfile, "w", encoding="utf-8") as handle:
            handle.write(USER_PIN + "\n")
        modules = _run(["modutil", "-dbdir", db, "-list"], env=self.env)
        certs = _run(["certutil", "-L", "-d", db, "-h", "all", "-f", pinfile], env=self.env)
        return modules, certs
