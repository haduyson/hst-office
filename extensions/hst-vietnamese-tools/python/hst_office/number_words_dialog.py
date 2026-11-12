# SPDX-License-Identifier: AGPL-3.0-only
"""Dialog "Đọc số thành chữ" (Sheets: source and target cell, text or formula) and Writer (same name: the
selected number). Number or money, unit, nghìn/ngàn, lẻ/linh, bốn/tư, Vietnamese/English, with a live preview."""
from . import number_words
from . import utilities_texts as T
from .dialogs import Dialog
from .number_words_choice import error_text, words

D = T.DIALOG


class NumberWordsDialog:
    def __init__(self, ctx, calc, source="", target="", sample=None):
        """`calc`: show the cell fields and the output choice; `sample`: the number read in the preview (Writer)."""
        self.calc, self.sample, self.accepted = calc, sample, None
        height = 214 if calc else 198
        d = self.d = Dialog(ctx, D["title"] if calc else D["writerTitle"], 270, height)
        y = 8
        if calc:
            d.label("l_source", D["source"], 8, y + 2, 78)
            d.edit("source", 90, y, 60, text=source, help_text=D["source"])
            d.label("l_target", D["target"], 158, y + 2, 46)
            d.edit("target", 206, y, 56, text=target, help_text=D["target"])
        else:
            d.label("l_source", D["number"], 8, y + 2, 78)
            d.edit("source", 90, y, 172, text=source, readonly=True, help_text=D["number"])
        y += 18
        rows = [("kind", D["kind"], D["kinds"] if calc else D["writerKinds"]), ("preset", D["unitPreset"], D["presets"])]
        for name, label, items in rows:
            d.label("l_" + name, label, 8, y + 2, 78)
            d.listbox(name, 90, y, 172, items, help_text=label)
            y += 16
        d.label("l_unit", D["unit"], 8, y + 2, 78)
        d.edit("unit", 90, y, 60, text=T.PRESETS[0][0], help_text=D["unit"])
        d.label("l_sub", D["subUnit"], 158, y + 2, 46)
        d.edit("sub", 206, y, 56, text=T.PRESETS[0][1], help_text=D["subUnit"])
        y += 18
        for name, label, items in (("thousand", D["thousand"], D["thousands"]), ("odd", D["odd"], D["odds"]),
                                   ("four", D["four"], D["fours"]), ("language", D["language"], D["languages"])) + \
                ((("output", D["output"], D["outputs"]),) if calc else ()):
            d.label("l_" + name, label, 8, y + 2, 78)
            d.listbox(name, 90, y, 172, items, help_text=label)
            y += 16
        d.label("l_preview", D["preview"], 8, y + 4, 78)
        d.label("preview", "", 90, y + 4, 172, 30, wrap=True)
        y = height - 22
        d.button("ok", D["insert"] if calc else D["replace"], 140, y, 60, callback=self._accept, default=True)
        d.button("cancel", T.SAVE_BUTTONS[2], 204, y, 58, kind=2)
        names = ["source", "kind", "unit", "sub", "thousand", "odd", "four", "language"]
        d.on_change(names, self._update)
        d.on_change(["preset"], self._preset)
        d.on_ready = self._update
        self.read_cell = None  # Sheets: callable(address) -> cell value, for the preview

    def _preset(self):
        index = self.d.get("preset")
        if 0 <= index < len(T.PRESETS):
            self.d.set_text("unit", T.PRESETS[index][0])
            self.d.set_text("sub", T.PRESETS[index][1])
        self._update()

    def choice(self):
        """{'money', 'unit', 'sub_unit', 'options' (number_words.Options), 'formula', 'source', 'target'}."""
        options = number_words.Options(thousand=("nghìn", "ngàn")[max(0, self.d.get("thousand"))],
                                       odd=("lẻ", "linh")[max(0, self.d.get("odd"))],
                                       four=("bốn", "tư")[max(0, self.d.get("four"))],
                                       language=("vi", "en")[max(0, self.d.get("language"))])
        return {"money": self.d.get("kind") == 1, "unit": self.d.get("unit").strip(), "sub_unit": self.d.get("sub").strip(),
                "options": options, "formula": self.calc and self.d.get("output") == 1,
                "source": self.d.get("source").strip(), "target": self.d.get("target").strip() if self.calc else ""}

    def _value(self, choice):
        if not self.calc:
            return self.sample
        return self.read_cell(choice["source"]) if self.read_cell else None

    def _update(self):
        choice = self.choice()
        try:
            text = words(self._value(choice), choice)
        except number_words.NumberWordsError as exc:
            text = error_text(exc)
        except ValueError as exc:
            text = str(exc)
        self.d.model.getByName("preview").Label = text

    def _accept(self):
        self.accepted = self.choice()
        self.d.end(1)

    def run(self, parent_peer=None):
        self.d.execute(parent_peer)
        return self.accepted
