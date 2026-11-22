# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""`python -m hst_ocr`: the OCR core as a process.

One-shot:   python -m hst_ocr < request.json > response.json
Serve:      python -m hst_ocr --serve   one JSON request per stdin line, one JSON response per stdout line, models
            stay loaded between requests (the extension keeps one engine process per office session).
Exit code 0 when a response was written (even an error response), 2 on unusable input.
"""
import json
import sys

from . import pipeline, protocol


def _answer(line):
    try:
        data = json.loads(line)
    except ValueError as exc:
        return protocol.error_response("bad-json", "request is not JSON: %s" % exc)
    try:
        return pipeline.run(data)
    except Exception as exc:  # noqa: BLE001 - a bug must still produce a JSON answer, never a hung caller
        return protocol.error_response("internal", "%s: %s" % (type(exc).__name__, exc))


def main(argv):
    out = sys.stdout
    if "--serve" in argv:
        for line in sys.stdin:
            if line.strip():
                out.write(json.dumps(_answer(line), ensure_ascii=False) + "\n")
                out.flush()
        return 0
    raw = sys.stdin.read()
    if not raw.strip():
        sys.stderr.write(__doc__)
        return 2
    out.write(json.dumps(_answer(raw), ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
