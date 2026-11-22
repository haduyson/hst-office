# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""hst_ocr: HST Office offline recognition core (text, formulas, tables). No UNO here.

The core talks JSON (protocol.py): one request in, one response out, through the `python -m hst_ocr` process or
`hst_ocr.pipeline.run(request_dict)`. The Writer/Sheets extension and, later, the Rust suite (crate `hst-ocr`)
only depend on that JSON contract, never on these modules.
"""
__version__ = "0.1.0"
PROTOCOL_VERSION = 1
