# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư: the Vietnamese address block and greeting line. Pure Python (no UNO).

The columns are found by their headers (roles: title "Danh xưng", gender "Giới tính", name "Họ và tên", position
"Chức vụ", unit "Đơn vị", address "Địa chỉ") and can be changed in the dialog. No postcode or country is needed.
  Khối địa chỉ:  Kính gửi: Ông Nguyễn Văn An      (empty lines are left out)
                 Trưởng phòng
                 Phòng Kế toán
                 12 Lê Lợi, Huế
  Dòng chào:     Kính gửi ông An,  /  Thân gửi chị Ngọc,  /  Kính gửi Ông/Bà Nguyễn Văn An,
The honorific comes from the title column, else from the gender column (Ông/Bà or Anh/Chị), else the neutral pair.
Settings live in the document (mail_merge_store meta "block" and "greeting")."""
from .vietnamese_text import given_name, remove_diacritics

ROLES = ("title", "gender", "name", "position", "unit", "address")
HINTS = {"title": ("danh xung", "xung ho", "quy danh"),
         "gender": ("gioi tinh", "phai", "gender", "sex"),
         "name": ("ho va ten", "ho ten", "nguoi nhan", "ten day du", "full name", "name", "ten"),
         "position": ("chuc vu", "chuc danh", "position", "job title"),
         "unit": ("don vi", "co quan", "phong ban", "cong ty", "to chuc", "company", "organization"),
         "address": ("dia chi", "address")}
STYLES = {"formal": ("Ông", "Bà", "Ông/Bà"), "friendly": ("Anh", "Chị", "Anh/Chị")}
OPENINGS = ("Kính gửi", "Kính thưa", "Thân gửi", "Thưa", "Xin chào")
ENDINGS = (",", ":", "")
BLOCK_DEFAULT = {"lead": "Kính gửi:", "style": "formal", "one_line": False}
GREETING_DEFAULT = {"opening": "Kính gửi", "style": "formal", "given": True, "capital": False, "ending": ","}
_MALE = {"nam", "male", "m", "trai", "ong", "anh"}
_FEMALE = {"nu", "female", "f", "gai", "ba", "chi"}
_LOWER = {"ong", "ba", "anh", "chi", "em", "co", "chu", "bac", "ong/ba", "anh/chi", "quy ong/ba"}


def _plain(text):
    return " ".join(remove_diacritics(str(text or "")).lower().split())


def guess_roles(headers):
    """{role: header or ""} from the header names; each header is used for one role at most."""
    roles, used = {}, set()
    for role in ROLES:
        found = ""
        for hint in HINTS[role]:
            found = next((h for h in headers if h not in used and _plain(h) == hint), "")
            if found:
                break
        roles[role] = found
        if found:
            used.add(found)
    return roles


def settings(stored, headers, default):
    """Stored settings completed with the defaults and the guessed roles; unknown columns are dropped."""
    result = dict(default)
    result.update(guess_roles(headers))
    for key, value in (stored or {}).items():
        if key in ROLES:
            result[key] = value if value in headers else ""
        elif key in default and isinstance(value, type(default[key])):
            result[key] = value
    return result


def _value(table, row, header):
    return table.text(row, header).strip() if header and header in table.headers else ""


def gender(text):
    word = _plain(text)
    return "male" if word in _MALE else "female" if word in _FEMALE else ""


def honorific(table, row, conf):
    """"Ông"/"Bà" (or Anh/Chị) for the recipient; the title column wins; unknown gender: "Ông/Bà"."""
    title = _value(table, row, conf.get("title"))
    if title:
        return title
    male, female, neutral = STYLES.get(conf.get("style"), STYLES["formal"])
    kind = gender(_value(table, row, conf.get("gender")))
    return male if kind == "male" else female if kind == "female" else neutral


def address_block(table, row, conf):
    """The block's lines joined with line breaks (a field shows them as separate lines)."""
    name = _value(table, row, conf.get("name"))
    first = " ".join(part for part in (conf.get("lead", ""), honorific(table, row, conf) if name else "", name) if part)
    details = [_value(table, row, conf.get(role)) for role in ("position", "unit")]
    details = [d for d in details if d]
    lines = [first] + ([", ".join(details)] if conf.get("one_line") and details else details)
    lines.append(_value(table, row, conf.get("address")))
    return "\n".join(line for line in lines if line.strip())


def greeting(table, row, conf):
    """"Kính gửi ông An," style greeting; with no name: "Kính gửi Quý ông/bà,"-like neutral text."""
    name = _value(table, row, conf.get("name"))
    if name and conf.get("given", True):
        name = given_name(name) or name
    title = honorific(table, row, conf)
    if not conf.get("capital") and _plain(title) in _LOWER:
        title = title.lower()  # "ông An", "ông/bà"; a title such as "PGS.TS." stays as typed
    parts = [conf.get("opening", "Kính gửi"), title if name else "Quý " + title.lower(), name]
    return " ".join(p for p in parts if p) + conf.get("ending", ",")
