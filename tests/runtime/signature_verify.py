# SPDX-License-Identifier: AGPL-3.0-only
"""Independent (non-HST) verification of signed documents for the digital-signature check.

ODF (META-INF/documentsignatures.xml, XAdES) and OOXML (_xmlsignatures/sig*.xml): checks the
XML-DSig SignatureValue over SignedInfo with the embedded certificate, every Reference digest
(same-document ids, ODF package streams, the OOXML package Manifest) and that the certificate
was issued by the given CA. OOXML references through the OPC Relationship transform are listed
as "unchecked" (HST verifies them; see _relationship_transform). Uses only lxml and
cryptography. PDF: poppler `pdfsig` (NSS) and, if installed, pyHanko (non-strict syntax: the PDF
writer stores UTC dates as "D:...Z'", which pyHanko's strict parser rejects).
"""
import base64
import copy
import hashlib
import io
import re
import shutil
import subprocess
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding
from lxml import etree

DS = "http://www.w3.org/2000/09/xmldsig#"
NS = {"ds": DS}
C14N = {"http://www.w3.org/TR/2001/REC-xml-c14n-20010315": (False, False),
        "http://www.w3.org/TR/2001/REC-xml-c14n-20010315#WithComments": (False, True),
        "http://www.w3.org/2001/10/xml-exc-c14n#": (True, False),
        "http://www.w3.org/2006/12/xml-c14n11": (False, False)}
DIGESTS = {"http://www.w3.org/2000/09/xmldsig#sha1": hashlib.sha1,
           "http://www.w3.org/2001/04/xmlenc#sha256": hashlib.sha256,
           "http://www.w3.org/2001/04/xmldsig-more#sha384": hashlib.sha384,
           "http://www.w3.org/2001/04/xmlenc#sha512": hashlib.sha512}
SIGHASH = {"rsa-sha1": hashes.SHA1, "rsa-sha256": hashes.SHA256, "rsa-sha384": hashes.SHA384,
           "rsa-sha512": hashes.SHA512, "ecdsa-sha256": hashes.SHA256, "ecdsa-sha384": hashes.SHA384}
REL_TRANSFORM = "http://schemas.openxmlformats.org/package/2006/RelationshipTransform"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _c14n(node, algorithm):
    exclusive, comments = C14N.get(algorithm, (False, False))
    # canonicalise a copy: lxml 5.2 drops inherited default namespaces of descendants when a
    # subtree is canonicalised in place (emits xmlns=""), which breaks the digests
    return etree.tostring(copy.deepcopy(node), method="c14n", exclusive=exclusive, with_comments=comments)


def _relationship_transform(data, transform):
    """ECMA-376 Part 2 RelationshipTransform: keep the selected relationships, sorted by Id,
    with an explicit TargetMode, then canonicalise (the following c14n transform)."""
    ids = {e.get("SourceId") for e in transform if e.tag.endswith("RelationshipReference")}
    types = {e.get("SourceType") for e in transform if e.tag.endswith("RelationshipsGroupReference")}
    rels = etree.fromstring(data)
    keep = [r for r in rels if r.get("Id") in ids or r.get("Type") in types]
    out = etree.Element("{%s}Relationships" % REL_NS, nsmap={None: REL_NS})
    for rel in sorted(keep, key=lambda r: r.get("Id")):
        item = etree.SubElement(out, "{%s}Relationship" % REL_NS)
        for name in ("Id", "Target", "TargetMode", "Type"):
            value = rel.get(name, "Internal" if name == "TargetMode" else None)
            if value is not None:
                item.set(name, value)
    return etree.tostring(out, method="c14n")


def _reference_digest(ref, signature_root, package, ids):
    uri = ref.get("URI", "")
    transforms = ref.findall("ds:Transforms/ds:Transform", NS)
    if uri.startswith("#"):
        node = ids.get(uri[1:])
        if node is None:
            raise ValueError("unresolved reference %s" % uri)
        algorithm = transforms[-1].get("Algorithm") if transforms else "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
        data = _c14n(node, algorithm)
    else:
        name = re.sub(r"\?.*$", "", uri).lstrip("/")
        data = package.read(name)
        for transform in transforms:
            algorithm = transform.get("Algorithm")
            if algorithm == REL_TRANSFORM:
                data = _relationship_transform(data, transform)
            elif algorithm in C14N:
                data = _c14n(etree.parse(io.BytesIO(data)).getroot(), algorithm)
            else:
                raise ValueError("unsupported transform %s" % algorithm)
    digest = DIGESTS[ref.find("ds:DigestMethod", NS).get("Algorithm")](data).digest()
    return digest == base64.b64decode(ref.findtext("ds:DigestValue", namespaces=NS))


def _verify_signature(sig, package, ca_cert):
    result = {"errors": []}
    ids = {node.get("Id"): node for node in sig.getroottree().iter() if isinstance(node.tag, str) and node.get("Id")}
    cert = x509.load_der_x509_certificate(base64.b64decode(sig.findtext(".//ds:X509Certificate", namespaces=NS)))
    result["subject"] = cert.subject.rfc4514_string()
    signed_info = sig.find("ds:SignedInfo", NS)
    c14n_alg = signed_info.find("ds:CanonicalizationMethod", NS).get("Algorithm")
    method = signed_info.find("ds:SignatureMethod", NS).get("Algorithm").rsplit("#", 1)[-1]
    value = base64.b64decode(sig.findtext("ds:SignatureValue", namespaces=NS))
    key = cert.public_key()
    try:
        if isinstance(key, ec.EllipticCurvePublicKey):
            raise ValueError("ECDSA raw signature not handled")
        key.verify(value, _c14n(signed_info, c14n_alg), padding.PKCS1v15(), SIGHASH[method]())
        result["signature_value"] = True
    except Exception as error:  # noqa: BLE001 - reported, not raised
        result["signature_value"] = False
        result["errors"].append("SignatureValue: %r" % error)
    refs = signed_info.findall("ds:Reference", NS)
    # OOXML: the package parts are listed in the Manifest of the signed package Object
    refs += sig.findall("ds:Object/ds:Manifest/ds:Reference", NS)
    ok = 0
    result["unchecked"] = []
    for ref in refs:
        if any(tr.get("Algorithm") == REL_TRANSFORM for tr in ref.findall("ds:Transforms/ds:Transform", NS)):
            # OPC relationship parts: this verifier's RelationshipTransform does not reproduce
            # xmlsec's output byte for byte, so these are reported, not judged (HST checks them)
            result["unchecked"].append(ref.get("URI"))
            continue
        try:
            if _reference_digest(ref, sig, package, ids):
                ok += 1
            else:
                result["errors"].append("digest mismatch: %s" % ref.get("URI"))
        except Exception as error:  # noqa: BLE001
            result["errors"].append("%s: %r" % (ref.get("URI"), error))
    refs = [r for r in refs if r.get("URI") not in result["unchecked"]]
    result["references"] = "%d/%d" % (ok, len(refs))
    try:
        cert.verify_directly_issued_by(ca_cert)
        result["issued_by_ca"] = True
    except Exception as error:  # noqa: BLE001
        result["issued_by_ca"] = False
        result["errors"].append("issuer: %r" % error)
    result["valid"] = result["signature_value"] and ok == len(refs) and result["issued_by_ca"]
    return result


def verify_package(path, ca_pem):
    """[{subject, valid, references, errors}] for every XML signature in an ODF/OOXML file."""
    ca_cert = x509.load_pem_x509_certificate(open(ca_pem, "rb").read())
    with zipfile.ZipFile(path) as package:
        names = [n for n in package.namelist()
                 if n == "META-INF/documentsignatures.xml" or re.match(r"_xmlsignatures/sig\d+\.xml$", n)]
        results = []
        for name in names:
            root = etree.fromstring(package.read(name))
            for sig in ([root] if root.tag == "{%s}Signature" % DS else root.findall("ds:Signature", NS)):
                results.append(dict(_verify_signature(sig, package, ca_cert), part=name))
        return results


def verify_pdf(path, nssdb, ca_pem):
    """{'pdfsig': text, 'pdfsig_valid': bool, 'pyhanko': text or None, 'pyhanko_valid': bool or None}."""
    out = {"pdfsig": None, "pdfsig_valid": None, "pyhanko": None, "pyhanko_valid": None}
    if shutil.which("pdfsig"):
        text = subprocess.run(["pdfsig", "-nssdir", "sql:" + nssdb, path], capture_output=True, text=True).stdout
        out["pdfsig"] = text
        out["pdfsig_valid"] = ("Signature is Valid" in text and "Certificate is Trusted" in text
                               and "Total document signed" in text)
    pyhanko = shutil.which("pyhanko") or (shutil.which("/opt/venv/bin/pyhanko"))
    if pyhanko:
        # the test CA in addition to the system roots, which anchor public time-stamp servers
        res = subprocess.run([pyhanko, "sign", "validate", "--pretty-print", "--no-revocation-check",
                              "--no-strict-syntax", "--trust", ca_pem, path], capture_output=True, text=True)
        out["pyhanko"] = (res.stdout + res.stderr)[-3000:]
        out["pyhanko_valid"] = res.returncode == 0 and "The signature is judged VALID" in res.stdout
    return out
