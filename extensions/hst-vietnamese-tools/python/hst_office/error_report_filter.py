# SPDX-License-Identifier: AGPL-3.0-only
"""Privacy filter for diagnostic text sent with an error report (Trợ giúp ▸ Báo lỗi cho HASON TECH…).

The report must never carry document content, document names or paths, user names or profile paths. HST's own log
lines are mostly tracebacks, so the filter keeps the shape a developer needs (module file name, line number, exception
type) and replaces everything that could identify a person or a document:

  * the known personal strings (home directory, user name, office profile, temp directory) in every spelling;
  * every URL (file:, vnd.sun.star.*, private:, http(s): ...) -> <URL>;
  * every absolute path (POSIX, Windows drive or UNC) -> <PATH>, keeping only the base name of a Python module
    (".../hst_office/dispatch.py" -> "<PATH>/dispatch.py");
  * every name with a document extension (Báo cáo.docx, "so lieu.xlsx") -> <FILE>;
  * e-mail addresses -> <EMAIL>;
  * every UUID -> <ID>, so the anonymous install ID of the update check (update_install_id) can never reach the local
    log or a report, whatever message carried it.
"""
import os
import re

DOC_EXT = ("doc", "docx", "docm", "dot", "dotx", "dotm", "odt", "ott", "fodt", "rtf", "txt", "xls", "xlsx", "xlsm",
           "xlsb", "xlt", "xltx", "ods", "ots", "fods", "csv", "tsv", "ppt", "pptx", "pptm", "pps", "ppsx", "pot",
           "potx", "odp", "otp", "fodp", "odg", "otg", "odf", "odb", "pdf", "xml", "html", "htm", "hwp", "wps", "epub",
           "png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff", "svg", "zip", "oxt", "p12", "pfx", "pem", "cer")
_URL = re.compile(r"\b(?:file|vnd\.sun\.star\.[\w.-]+|private|https?|ftp|smb|webdav|davs?|mailto|data):[^\s\"'<>]*",
                  re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_UUID = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}-(?:[0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}(?![0-9A-Fa-f])")
# A path segment may contain spaces (C:\Users\Nguyen Van A\...); it stops at quotes, commas, colons and line ends.
_SEG = r"[^\s\\/\"'<>|:,;()\[\]]+(?: [^\s\\/\"'<>|:,;()\[\]]+)*"
_PATH = re.compile(r"(?:\b[A-Za-z]:|\\\\" + _SEG + r")(?:[\\/]" + _SEG + r")+[\\/]?|\b[A-Za-z]:[\\/]"
                   r"|(?<![\w.])(?:~|\.{1,2})?(?:/" + _SEG + r")+/?"
                   r"|(?:\\" + _SEG + r"){2,}\\?")  # what is left of a Windows path after a greedy POSIX match
_DOC_NAME = re.compile(r"(?:[\"'][^\"'\n]{1,200}\.(?:%s)[\"']|[^\s\"'<>|/\\:]+\.(?:%s))(?![\w.])"
                       % ("|".join(DOC_EXT), "|".join(DOC_EXT)), re.I)
_PY_TAIL = re.compile(r"[\\/]([\w-]+\.py)[\"']?$")
MIN_SECRET = 3  # shorter personal strings ("an") would erase ordinary words; paths and URLs catch them anyway


def personal_strings(environ=None, extra=()):
    """Home, user name, profile and temp locations of this process, in native, URL and backslash spellings."""
    environ = os.environ if environ is None else environ
    found = set()
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TMPDIR", "TEMP", "TMP", "XDG_CONFIG_HOME",
                "USER", "USERNAME", "LOGNAME"):
        value = environ.get(key, "")
        if value:
            found.add(value)
            found.add(os.path.basename(value.rstrip("/\\")))
    try:
        import getpass
        found.add(getpass.getuser())
    except Exception:  # noqa: BLE001 - no user database entry (containers): nothing to add
        pass
    try:
        found.add(os.path.basename(os.path.expanduser("~").rstrip("/\\")))
        found.add(os.path.expanduser("~"))
    except Exception:  # noqa: BLE001
        pass
    for value in list(extra):
        if value:
            found.add(value)
    spellings = set()
    for value in found:
        if isinstance(value, str) and len(value.strip()) >= MIN_SECRET and value.strip("/\\") not in ("tmp", "temp"):
            spellings.update({value, value.replace("\\", "/"), value.replace("/", "\\"),
                              value.replace(" ", "%20")})
    return sorted(spellings, key=len, reverse=True)  # longest first: a home path before its user name


def _path(match):
    text = match.group(0)
    tail = _PY_TAIL.search(text)
    return "<PATH>/" + tail.group(1) if tail else "<PATH>"


def scrub(text, secrets=None):
    """`text` with personal strings, URLs, UUIDs, paths, document names and e-mail addresses replaced."""
    if not text:
        return ""
    secrets = personal_strings() if secrets is None else secrets
    text = _URL.sub("<URL>", text)
    text = _UUID.sub("<ID>", text)
    text = _EMAIL.sub("<EMAIL>", text)
    text = _PATH.sub(_path, text)
    for secret in secrets:  # what is left outside paths: a user name inside a message, a profile in another form
        if secret:
            text = re.sub(r"(?<!\w)%s(?!\w)" % re.escape(secret), "<USER>", text, flags=re.I)  # whole words only
    text = _DOC_NAME.sub("<FILE>", text)
    return text


def tail_lines(text, max_lines, max_bytes):
    """The last whole lines of `text` that fit both limits (UTF-8 bytes)."""
    lines = text.splitlines()[-max_lines:]
    kept, size = [], 0
    for line in reversed(lines):
        size += len(line.encode("utf-8")) + 1
        if size > max_bytes:
            break
        kept.append(line)
    return "\n".join(reversed(kept))
