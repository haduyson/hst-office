# SPDX-License-Identifier: AGPL-3.0-only
"""Rich text runs of formatted citations and bibliography entries. Pure Python (no uno).

A run is ``(text, flags)`` while formatting; ``flags`` is a string of the letters ``i`` (italic), ``b`` (bold) and
``s`` (superscript). The public form handed to the document layer (``to_public``) is a list of dicts
``{"text": "...", "italic": true, "bold": true, "superscript": true}`` where only the flags that are set appear.

``Out`` collects text the way citation styles expect: empty pieces vanish, a period never follows ``.``, ``?`` or
``!`` (``"Title?" + "."`` -> ``"Title?"``), repeated separators and double spaces collapse, and, when asked, a
comma or period that follows a closing quote moves inside it (American style: ``“Title,”``).
"""
import html

_FLAG_NAMES = (("i", "italic"), ("b", "bold"), ("s", "superscript"))
_END = ".?!"
_CLOSE_QUOTES = "”’\""

_FLAG_CACHE = {}


def _norm_flags(flags):
    if flags not in _FLAG_CACHE:
        _FLAG_CACHE[flags] = "".join(sorted(set(flags or "")))
    return _FLAG_CACHE[flags]


class Out:
    """Append-only run collector with punctuation collapsing."""

    def __init__(self):
        self.runs = []

    def last_char(self):
        for text, _ in reversed(self.runs):
            if text:
                return text[-1]
        return ""

    def visible_last(self):
        """Last character that is not a space ("" when nothing is visible yet)."""
        for text, _ in reversed(self.runs):
            stripped = text.rstrip(" ")
            if stripped:
                return stripped[-1]
        return ""

    def _trim_tail(self):
        """Drop a trailing separator (", ", "; ", ": ") before new punctuation takes its place."""
        while self.runs:
            text, flags = self.runs[-1]
            trimmed = text.rstrip(" ")
            if trimmed and trimmed[-1] in ",;:":
                trimmed = trimmed[:-1].rstrip(" ")
                if trimmed:
                    self.runs[-1] = (trimmed, flags)
                else:
                    self.runs.pop()
                    continue
            elif not trimmed:
                self.runs.pop()
                continue
            elif trimmed != text:
                self.runs[-1] = (trimmed, flags)
            return

    def add(self, text, flags=""):
        if not text:
            return
        last = self.runs[-1][0] if self.runs else ""  # runs are never empty strings
        tail = last.rstrip(" ")
        visible = tail[-1] if tail else self.visible_last()
        first = text.lstrip(" ")[:1]
        if visible and first and first in ".,;:" and visible in ",;:":
            self._trim_tail()  # "Nxb Giáo dục, " + "." -> "Nxb Giáo dục."
            visible = self.visible_last()
            text = text.lstrip(" ")
        if visible and first == "." and visible in _END:
            text = text.lstrip(" ")[1:]  # "J. A." + ". " -> "J. A. "; "Title?" + "." -> "Title?"
        prev = self.last_char() if not self.runs or self.runs[-1][0] is not last else last[-1:]
        if prev == " " and text.startswith(" "):
            text = text.lstrip(" ")
        if text:
            self.runs.append((text, _norm_flags(flags)))

    def extend(self, runs, extra_flags="", collapsed=False):
        """``collapsed``: runs of another Out; once one is kept unchanged and shows more than ", ; :", the rest were
        tidied against the same predecessors and are appended as they are (saves re-adding per nesting level)."""
        for index, (text, flags) in enumerate(runs):
            flags = flags + extra_flags if extra_flags else flags
            before = len(self.runs)
            self.add(text, flags)
            if collapsed and len(self.runs) == before + 1 and self.runs[-1][0] is text and text.strip(" ,;:"):
                self.runs.extend((t, _norm_flags(f + extra_flags if extra_flags else f)) for t, f in runs[index + 1:])
                return

    def mark(self):
        return len(self.runs)

    def since(self, mark):
        return self.runs[mark:]

    def truncate(self, mark):
        del self.runs[mark:]


def merge(runs):
    """Adjacent runs with the same flags joined; empty runs dropped; outer spaces trimmed."""
    merged = []
    for text, flags in runs:
        if not text:
            continue
        if merged and merged[-1][1] == flags:
            merged[-1] = (merged[-1][0] + text, flags)
        else:
            merged.append((text, flags))
    while merged and not merged[0][0].strip():
        merged.pop(0)
    while merged and not merged[-1][0].strip():
        merged.pop()
    if merged:
        merged[0] = (merged[0][0].lstrip(), merged[0][1])
        merged[-1] = (merged[-1][0].rstrip(), merged[-1][1])
    return merged


def quote_punctuation(runs):
    """Move a comma or period that directly follows a closing double quote inside it: ``“Title”,`` -> ``“Title,”``."""
    result = [list(run) for run in runs]
    for index, run in enumerate(result):
        if not run[0] or run[0][-1] not in "”\"":
            continue
        nxt = result[index + 1] if index + 1 < len(result) else None
        if nxt and nxt[0][:1] in (",", "."):
            run[0], nxt[0] = run[0][:-1] + nxt[0][0] + run[0][-1], nxt[0][1:]
    text_fixed = []
    for text, flags in result:
        for mark in ("”,", "”.", "\",", "\"."):
            text = text.replace(mark, mark[1] + mark[0])
        text_fixed.append((text, flags))
    return merge(text_fixed)


def apply_flags(runs, flags):
    return [(text, _norm_flags(own + flags)) for text, own in runs]


def plain(runs):
    return "".join(text for text, _ in runs)


def to_public(runs):
    """[{"text": ..., "italic": True, ...}] for the document layer (JSON-safe)."""
    result = []
    for text, flags in merge(runs):
        entry = {"text": text}
        for letter, name in _FLAG_NAMES:
            if letter in flags:
                entry[name] = True
        result.append(entry)
    return result


def from_public(entries):
    """Inverse of to_public; unknown keys are ignored, non-string text is refused."""
    runs = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            raise ValueError("a run needs a text string")
        runs.append((entry["text"], _norm_flags("".join(letter for letter, name in _FLAG_NAMES if entry.get(name)))))
    return runs


def to_html(runs):
    """Escaped HTML using <i>, <b> and <sup> only (for .uno:TextFormField results)."""
    parts = []
    for text, flags in merge(runs):
        piece = html.escape(text, quote=False)
        for letter, tag in (("s", "sup"), ("b", "b"), ("i", "i")):
            if letter in flags:
                piece = "<%s>%s</%s>" % (tag, piece, tag)
        parts.append(piece)
    return "".join(parts)


def to_markup(runs):
    """Compact test/debug notation: *italic*, **bold**, ^superscript^."""
    parts = []
    for text, flags in merge(runs):
        piece = text
        if "s" in flags:
            piece = "^%s^" % piece
        if "b" in flags:
            piece = "**%s**" % piece
        if "i" in flags:
            piece = "*%s*" % piece
        parts.append(piece)
    return "".join(parts)
