# SPDX-License-Identifier: AGPL-3.0-only
"""The documents W16 opens: one small file per format, ODF written here and OOXML converted from it."""
from pathlib import Path
import subprocess
import zipfile

NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
      'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"')
BODY = {"odt": ("application/vnd.oasis.opendocument.text", "<office:text><text:p>HST</text:p></office:text>"),
        "ods": ("application/vnd.oasis.opendocument.spreadsheet",
                '<office:spreadsheet><table:table table:name="Sheet1"><table:table-row><table:table-cell '
                'office:value-type="string"><text:p>HST</text:p></table:table-cell></table:table-row></table:table>'
                '</office:spreadsheet>'),
        "odp": ("application/vnd.oasis.opendocument.presentation",
                '<office:presentation><draw:page draw:name="p1"><draw:frame svg:x="2cm" svg:y="2cm" svg:width="12cm" '
                'svg:height="3cm"><draw:text-box><text:p>HST</text:p></draw:text-box></draw:frame></draw:page>'
                '</office:presentation>')}


def fixtures(install, work):
    """One small document per format: ODF written here, OOXML converted by the installed office on its own
    throw-away profile (the default profile stays new)."""
    out = Path(work) / "fixtures"
    out.mkdir(parents=True, exist_ok=True)
    soffice = Path(install) / "program" / "soffice.exe"
    for ext, (mime, body) in BODY.items():
        path = out / ("mau." + ext)
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), mime)
            z.writestr("META-INF/manifest.xml", '<?xml version="1.0" encoding="UTF-8"?><manifest:manifest '
                       'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">'
                       '<manifest:file-entry manifest:full-path="/" manifest:media-type="%s" manifest:version="1.3"/>'
                       '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                       '</manifest:manifest>' % mime, zipfile.ZIP_DEFLATED)
            z.writestr("content.xml", '<?xml version="1.0" encoding="UTF-8"?><office:document-content %s '
                       'office:version="1.3"><office:body>%s</office:body></office:document-content>' % (NS, body),
                       zipfile.ZIP_DEFLATED)
    profile = (Path(work) / "convert-profile").resolve().as_uri()
    for odf, ooxml in (("odt", "docx"), ("ods", "xlsx"), ("odp", "pptx")):
        subprocess.run([str(soffice), "--headless", "--norestore", "-env:UserInstallation=" + profile,
                        "--convert-to", ooxml, "--outdir", str(out), str(out / ("mau." + odf))],
                       check=True, capture_output=True, timeout=300, stdin=subprocess.DEVNULL)
        if not (out / ("mau." + ooxml)).is_file():
            raise RuntimeError("Không tạo được tệp mẫu ." + ooxml)
    return out
