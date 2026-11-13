# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: what the user never has to see. The document remembers its recipient list in the user-defined
property HSTMailMerge (JSON: source file, sheet, unchecked recipients, order, file-name pattern, folder, the last
format chosen per column, id); the merge
engine reads a typed copy of the checked recipients (staging .ods: text stays text, dates are dates) through the data
source "HST Trộn thư <id>", registered automatically under <user profile>/user/hst/mail-merge/<id>/.

Every staging write uses a new file name and points the data source to it, so a connection the engine opened
earlier can never serve old rows; older copies are removed."""
import glob
import json
import os
import time
import uuid

from . import mail_merge_format as fmt

PROPERTY = "HSTMailMerge"
TABLE = "DanhSach"  # sheet of the staging copy = table name the fields use
SOURCE_PREFIX = "HST_TronThu_"  # no space: a DOCX round trip keeps the whole name
VERSION = 1
DEFAULT_META = {"v": VERSION, "id": "", "source": "", "sheet": None, "excluded": [], "sort": "", "descending": False,
                "pattern": "", "folder": "", "kinds": {}}


def parse_meta(text):
    """The stored settings, completed with defaults; damaged or foreign values are ignored."""
    meta = dict(DEFAULT_META)
    try:
        stored = json.loads(text) if text else {}
    except ValueError:
        stored = {}
    if isinstance(stored, dict):
        for key, default in DEFAULT_META.items():
            value = stored.get(key, default)
            if key == "sheet" and (value is None or isinstance(value, str)):
                meta[key] = value
            elif key != "sheet" and isinstance(value, type(default)):
                meta[key] = value
    meta["excluded"] = [k for k in meta["excluded"] if isinstance(k, str)]
    meta["kinds"] = {k: v for k, v in meta["kinds"].items() if isinstance(k, str) and isinstance(v, str)}
    return meta


def read_meta(doc):
    props = doc.DocumentProperties.UserDefinedProperties
    try:
        return parse_meta(props.getPropertyValue(PROPERTY))
    except Exception:  # noqa: BLE001 - property missing: no recipient list yet
        return parse_meta("")


def write_meta(doc, meta):
    props = doc.DocumentProperties.UserDefinedProperties
    text = json.dumps(meta, ensure_ascii=False, sort_keys=True)
    if props.getPropertySetInfo().hasPropertyByName(PROPERTY):
        props.setPropertyValue(PROPERTY, text)
    else:
        props.addProperty(PROPERTY, 128, text)  # PropertyAttribute.REMOVABLE


def new_id():
    return uuid.uuid4().hex[:8]


def source_name(meta):
    return SOURCE_PREFIX + meta["id"]


def work_dir(ctx, meta):
    import uno
    paths = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
    user = uno.fileUrlToSystemPath(paths.substituteVariables("$(user)", True))
    path = os.path.join(user, "hst", "mail-merge", meta["id"])
    os.makedirs(path, exist_ok=True)
    return path


def _prop(name, value):
    from com.sun.star.beans import PropertyValue
    return PropertyValue(Name=name, Value=value)


def write_staging(ctx, folder, headers, kinds, rows):
    """Write the staging .ods (a new file each time) and return its path."""
    import uno
    from com.sun.star.lang import Locale
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, (_prop("Hidden", True),))
    try:
        sheet = doc.Sheets.getByIndex(0)
        sheet.Name = TABLE
        data = [tuple(headers)] + [tuple("" if v is None else v for v in row) for row in rows]
        sheet.getCellRangeByPosition(0, 0, len(headers) - 1, len(data) - 1).setDataArray(tuple(data))
        if rows:
            locale = Locale("vi", "VN", "")
            key = doc.NumberFormats.queryKey("YYYY-MM-DD", locale, False)
            key = key if key >= 0 else doc.NumberFormats.addNew("YYYY-MM-DD", locale)
            for column, kind in enumerate(kinds):
                if kind == fmt.COL_DATE:
                    sheet.getCellRangeByPosition(column, 1, column, len(rows)).NumberFormat = key
        path = os.path.join(folder, "danh-sach-%d.ods" % int(time.time() * 1000))
        doc.storeToURL(uno.systemPathToFileUrl(path), (_prop("FilterName", "calc8"),))
    finally:
        doc.close(True)
    for old in glob.glob(os.path.join(folder, "danh-sach-*.ods")):
        if old != path:
            try:
                os.remove(old)
            except OSError:  # still open by an earlier engine connection (Windows): removed next time
                pass
    return path


def register(ctx, meta, folder, staging_path):
    """Create or re-point the data source of this document to the staging copy."""
    import uno
    context = ctx.ServiceManager.createInstanceWithContext("com.sun.star.sdb.DatabaseContext", ctx)
    name, url = source_name(meta), "sdbc:calc:" + uno.systemPathToFileUrl(staging_path)
    odb = os.path.join(folder, "nguon.odb")
    source = None
    if context.hasByName(name):
        try:
            source = context.getByName(name)
        except Exception:  # noqa: BLE001 - registered file gone: register again below
            context.revokeObject(name)
    if source is None:
        source = context.createInstance()
        source.URL = url
        source.DatabaseDocument.storeAsURL(uno.systemPathToFileUrl(odb), ())
        context.registerObject(name, source)
    else:
        source.URL = url
        source.DatabaseDocument.store()
    return name


def set_current_source(doc, name):
    """The document's own data source (the engine's dialogs and the wizard start from it)."""
    settings = doc.createInstance("com.sun.star.text.DocumentSettings")
    settings.CurrentDatabaseDataSource = name
    settings.CurrentDatabaseCommand = TABLE
    settings.CurrentDatabaseCommandType = 0
