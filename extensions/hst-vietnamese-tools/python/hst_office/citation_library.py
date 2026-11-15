# SPDX-License-Identifier: AGPL-3.0-only
"""The user's own reference library: <user profile>/hst-citations/library.json, never sent anywhere.

File: {"schemaVersion": 1, "items": [CSL-JSON items]}. Writes are atomic (temporary file + os.replace). Limits:
20 000 items and 20 MB. A damaged file is copied to library.json.bad (or .bad-2, .bad-3… — an existing copy is
never overwritten) and LibraryDamaged is raised, so the caller can tell the user before starting a new library.
A library written by a newer HST (schemaVersion > 1) opens read-only. Pure Python (no uno).
"""
import json
import os
import shutil

from . import citation_dedupe as dedupe
from . import citation_model as model
from . import citation_names as names
from .citation_store import atomic_write
from .vietnamese_text import remove_diacritics

SCHEMA_VERSION = 1
MAX_ITEMS = 20_000
MAX_BYTES = 20 * 1024 * 1024
SEARCH_FIELDS = ("title", "container-title", "publisher", "DOI", "ISBN", "genre", "note")


class LibraryError(Exception):
    pass


class LibraryDamaged(LibraryError):
    def __init__(self, message, bad_path):
        super().__init__(message)
        self.bad_path = bad_path


def library_path(user_dir):
    """<user profile>/hst-citations/library.json (``user_dir`` is the expanded $(user) folder)."""
    return os.path.join(user_dir, "hst-citations", "library.json")


def _keep_bad_copy(path):
    target, number = path + ".bad", 1
    while os.path.exists(target):
        number += 1
        target = "%s.bad-%d" % (path, number)
    shutil.copy2(path, target)
    return target


def _haystack(item):
    parts = [item.get(field, "") for field in SEARCH_FIELDS]
    for var in ("author", "editor", "translator"):
        parts += [names.full_name(n) for n in item.get(var, [])]
    parts.append(str(model.year(item) or ""))
    return remove_diacritics(" ".join(parts)).lower()


class Library:
    def __init__(self, path, items=(), read_only=False):
        self.path, self.read_only, self.warnings = path, read_only, []
        self._items = {}
        for item in items:
            self._items[item["id"]] = item

    @classmethod
    def load(cls, path):
        """The library at ``path`` (empty when the file does not exist yet)."""
        if not os.path.exists(path):
            return cls(path)
        try:
            if os.path.getsize(path) > MAX_BYTES:
                raise ValueError("lớn hơn 20 MB")
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                raise ValueError("thiếu danh sách items")
            version = data.get("schemaVersion")
            if not isinstance(version, int) or version < 1:
                raise ValueError("schemaVersion không hợp lệ")
        except (OSError, ValueError) as exc:
            bad = _keep_bad_copy(path)
            raise LibraryDamaged("Thư viện tài liệu tham khảo bị hỏng (%s); bản cũ được giữ tại %s" % (exc, bad),
                                 bad) from exc
        library = cls(path, read_only=version > SCHEMA_VERSION)
        for raw in data["items"][:MAX_ITEMS]:
            try:
                item, warnings = model.normalize_item(raw)
            except ValueError as exc:
                library.warnings.append(str(exc))
                continue
            if item["id"] in library._items:
                item["id"] = model.new_id()
            library._items[item["id"]] = item
            library.warnings += warnings
        return library

    @property
    def items(self):
        return list(self._items.values())

    def __len__(self):
        return len(self._items)

    def get(self, item_id):
        return self._items.get(item_id)

    def save(self):
        if self.read_only:
            raise LibraryError("Thư viện do phiên bản HST Office mới hơn tạo; bản này chỉ đọc được.")
        if len(self._items) > MAX_ITEMS:
            raise LibraryError("Thư viện vượt quá %d mục." % MAX_ITEMS)
        data = json.dumps({"schemaVersion": SCHEMA_VERSION, "items": self.items}, ensure_ascii=False,
                          indent=1).encode("utf-8")
        if len(data) > MAX_BYTES:
            raise LibraryError("Thư viện vượt quá 20 MB.")
        atomic_write(self.path, data)

    def add(self, items):
        """(added ids, [(item, existing id)]): new items are stored (normalised, stamped); duplicates are returned
        untouched for the user to choose "Gộp" (merge) or "Giữ cả hai" (keep_both)."""
        index = dedupe.Index(self._items.values())
        added, duplicates = [], []
        for raw in items:
            item = model.normalize_item(raw)[0]
            existing = index.find(item)
            if existing:
                duplicates.append((item, existing))
                continue
            self._store(item)
            index.add(item)
            added.append(item["id"])
        return added, duplicates

    def _store(self, item):
        if len(self._items) >= MAX_ITEMS:
            raise LibraryError("Thư viện vượt quá %d mục." % MAX_ITEMS)
        if item["id"] in self._items:
            item["id"] = model.new_id()
        self._items[item["id"]] = model.touch(item)

    def keep_both(self, item):
        copy = dict(model.normalize_item(item)[0], id=model.new_id())
        self._store(copy)
        return copy["id"]

    def merge(self, existing_id, item):
        """Fill the fields the stored item lacks from ``item``; stored values win."""
        current = self._items[existing_id]
        incoming = model.normalize_item(item)[0]
        for key, value in incoming.items():
            if key not in current and key != "id":
                current[key] = value
        model.touch(current)
        return existing_id

    def update(self, item):
        """Replace a stored item (after the user edited it)."""
        clean = model.normalize_item(item)[0]
        if clean["id"] not in self._items:
            raise KeyError(clean["id"])
        self._items[clean["id"]] = model.touch(clean)
        return clean

    def remove(self, ids):
        return [self._items.pop(i) for i in ids if i in self._items]

    def search(self, text, limit=200):
        """Items whose title, names, year, container, publisher, DOI or ISBN contain every word of ``text``
        (accents and case ignored), sorted by title."""
        words = remove_diacritics(text or "").lower().split()
        found = [item for item in self._items.values() if all(w in _haystack(item) for w in words)]
        found.sort(key=lambda item: names.collation_key(item.get("title", "")))
        return found[:limit]
