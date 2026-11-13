# SPDX-License-Identifier: AGPL-3.0-only
""""Kiểu trích dẫn": the document's style, a university preset of it, the options users change most, and a live
preview with the document's own sources (sample sources when it has none). Only options that differ from the
style (and preset) are stored, so the document property stays short. Returns new settings or None."""
from .citation_settings import stored_options
from .dialogs import Dialog

W, H = 380, 268
BRACKETS = ("[]", "()", "sup")
CHECKS = (("groupByLanguage", "groupByLanguage"), ("groupHeadings", "groupHeadings"), ("compress", "compress"),
          ("separate", "multiCite"), ("locatorLabel", "locatorLabel"))
SAMPLES = (
    {"id": "s1", "type": "book", "title": "Giáo trình kinh tế vĩ mô", "language": "vi", "publisher": "Giáo dục",
     "publisher-place": "Hà Nội", "author": [{"family": "Nguyễn", "given": "Văn An", "hst-vi": True}],
     "issued": {"date-parts": [[2010]]}},
    {"id": "s2", "type": "article-journal", "title": "Monetary policy and growth", "language": "en",
     "container-title": "Journal of Economics", "volume": "12", "issue": "3", "page": "45-67",
     "author": [{"family": "Smith", "given": "John"}, {"family": "Lee", "given": "Anna"}],
     "issued": {"date-parts": [[2020]]}},
    {"id": "s3", "type": "article-journal", "title": "Tăng trưởng tín dụng ở Việt Nam", "language": "vi",
     "container-title": "Tạp chí Kinh tế và Phát triển", "issue": "250", "page": "10-18",
     "author": [{"family": "Trần", "given": "Thị Bình", "hst-vi": True}], "issued": {"date-parts": [[2019]]}},
)


def run(ctx, peer, texts, current, doc_items, document_language=None):
    from . import citation_engine, citation_refresh, citation_style
    t = texts["style"]
    user_dir = citation_refresh.user_dir(ctx)
    styles = citation_style.list_styles(user_dir)
    ids = [s["id"] for s in styles]
    language = (current.get("opts") or {}).get("language")
    result, state = {}, {"presets": []}
    dialog = Dialog(ctx, t["title"], W, H)
    dialog.label("lStyle", t["style"], 8, 10, 90)
    dialog.listbox("style", 100, 8, W - 108, [s["name"] for s in styles],
                   ids.index(current["style"]) if current["style"] in ids else 0, help_text=t["style"])
    dialog.label("lPreset", t["preset"], 8, 28, 90)
    dialog.listbox("preset", 100, 26, W - 108, [t["presetNone"]], 0, help_text=t["preset"])
    dialog.label("lBrackets", t["brackets"], 8, 46, 90)
    dialog.listbox("brackets", 100, 44, 100, t["bracketChoices"], 0, help_text=t["brackets"])
    for index, (key, _option) in enumerate(CHECKS):
        dialog.check(key, t[key], 8 + (index % 2) * 186, 62 + (index // 2) * 12, 182, state=False)
    dialog.label("lPreview", t["preview"], 8, 102, 100)
    dialog.edit("preview", 8, 112, W - 16, h=H - 140, multiline=True, readonly=True, help_text=t["preview"])
    dialog.button("ok", t["apply"], W - 156, H - 20, 72, default=True, callback=lambda: finish())
    dialog.button("cancel", texts["common"]["cancel"], W - 80, H - 20, 72, kind=2)

    def style_id():
        return ids[max(0, dialog.get("style"))]

    def preset_id():
        index = dialog.get("preset")
        return state["presets"][index - 1] if index > 0 else None

    def base():
        return citation_style.load_style(style_id(), {}, preset_id(), user_dir=user_dir).options

    def chosen():
        options = {"brackets": BRACKETS[max(0, dialog.get("brackets"))]}
        for key, option in CHECKS:
            value = bool(dialog.get(key))
            options[option] = ("separate" if value else "combined") if option == "multiCite" else value
        return options

    def show(options):
        bracket = options.get("brackets", "[]")
        dialog.select("brackets", BRACKETS.index(bracket) if bracket in BRACKETS else 0)
        for key, option in CHECKS:
            value = options.get(option)
            dialog.model.getByName(key).State = int(value == "separate" if option == "multiCite" else bool(value))

    def on_style(keep=None):
        entry = styles[ids.index(style_id())]
        state["presets"] = [p["id"] for p in entry["presets"]]
        from .citation_lists import set_rows
        index = state["presets"].index(keep) + 1 if keep in state["presets"] else 0
        set_rows(dialog, "preset", [t["presetNone"]] + [p["name"] for p in entry["presets"]], (index,))
        on_preset()

    def on_preset(options=None):
        merged = dict(base())
        merged.update(options or {})
        show(merged)
        preview()

    def preview():
        items = list(doc_items.values())[:3] or list(SAMPLES)
        try:
            options = dict(base(), **chosen(), **({"language": language} if language else {}))
            style = citation_style.load_style(style_id(), options, preset_id(), user_dir=user_dir)
            clusters = [{"citationID": "p%d" % n, "items": [{"id": i["id"]}], "mode": "normal"}
                        for n, i in enumerate(items)]
            done = citation_engine.process(style, {i["id"]: i for i in items}, clusters, document_language=document_language)
            lines = [c["text"] for c in done["citations"]] + [""]
            lines += [(e["label"] + " " if e["label"] else "") + e["text"]
                      for g in done["bibliography"]["groups"] for e in g["entries"]]
            dialog.set_text("preview", "\n".join(lines))
        except Exception as exc:  # noqa: BLE001 - a preview never stops the dialog
            dialog.set_text("preview", str(exc))

    def finish():
        result["settings"] = {"style": style_id(), "preset": preset_id(),
                              "opts": stored_options(chosen(), base(), language)}
        dialog.end(1)

    dialog.on_change(["style"], lambda: on_style())
    dialog.on_change(["preset"], lambda: on_preset())
    dialog.on_change(["brackets"] + [k for k, _o in CHECKS], preview)
    dialog.on_ready = lambda: (on_style(current.get("preset")), on_preset(current.get("opts")))
    if dialog.execute(peer) != 1:
        return None
    return result["settings"]
