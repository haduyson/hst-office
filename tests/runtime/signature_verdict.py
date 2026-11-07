# SPDX-License-Identifier: AGPL-3.0-only
"""Verdict of check-digital-signature.py: independent verification of each signed file and the pass/fail rules."""
import os

import signature_verify
from signature_documents import FORMATS


def external_checks(pki, results):
    for tag, row in results.items():
        if not isinstance(row, dict) or not row.get("file") or not os.path.exists(row["file"]):
            continue
        if row["file"].endswith(".pdf"):
            row["external"] = signature_verify.verify_pdf(row["file"], pki.nssdb, pki.ca_pem)
            row["external_valid"] = bool(row["external"]["pdfsig_valid"]) and row["external"]["pyhanko_valid"] is not False
        else:
            row["external"] = signature_verify.verify_package(row["file"], pki.ca_pem)
            row["external_valid"] = bool(row["external"]) and all(s["valid"] for s in row["external"])


def verdict(results):
    failures = []
    for tag in [f[0] for f in FORMATS] + ["pdf", "pdf-export"] + (["pdf-export-tsa"] if "pdf-export-tsa" in results else []):
        row = results.get(tag, {})
        api_ok = bool(row.get("hst")) and all(s["valid"] and s["certificate_status"] == 0 for s in row["hst"])
        # OOXML: docProps/core.xml, docProps/app.xml and [Content_Types].xml stay unsigned by
        # convention, so HST reports the signature as valid but partial (PARTIAL_OK)
        accepted = ("OK", "PARTIAL_OK") if tag in ("docx", "xlsx", "pptx") else ("OK",)
        hst_ok = row.get("status_bar") in accepted if "status_bar" in row else api_ok
        row["verdict"] = "PASS" if hst_ok and row.get("external_valid") else "FAIL"
        if row["verdict"] != "PASS":
            failures.append(tag)
    tampered = results.get("tampered-odt", {})
    if tampered.get("external_valid") or any(s["valid"] for s in tampered.get("hst", [])) or tampered.get("status_bar") == "OK":
        failures.append("tampered-odt (accepted)")
    prompts = results.get("pin_prompts_signing_run", [])
    if len(prompts) < 2:
        failures.append("wrong PIN was not re-prompted")
    cancel = results.get("cancel-pin", {})
    if cancel.get("file_has_signature") or not cancel.get("office_alive") or not cancel.get("prompts"):
        failures.append("cancel-pin")
    return failures
