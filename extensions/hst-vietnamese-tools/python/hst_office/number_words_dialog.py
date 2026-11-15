# SPDX-License-Identifier: AGPL-3.0-only
"""Dialog "Đọc số thành chữ" (Sheets: source cell or column and target cell, text or formula, the file's default)
and Writer (same name: the selected number). Number or money, unit, nghìn/ngàn, lẻ/linh, bốn/tư, Vietnamese/English,
with a live preview of the first cell. It opens with number_words_defaults.resolve(); numbers and money keep their
own reading options, so switching "Đọc thành" shows the options of that kind."""
from . import number_words
from . import utilities_texts as T
from .dialogs import Dialog, palette
from .number_words_choice import error_text, words
from .number_words_defaults import CHOICES, DEFAULTS, option_indexes, options_key
from .number_words_file_default import has_group, matches

D = T.DIALOG


def preset_index(unit, sub_unit):
    """The "Đơn vị tiền" entry of a unit pair: a preset, else "Tùy chỉnh"."""
    return T.PRESETS.index((unit, sub_unit)) if (unit, sub_unit) in T.PRESETS else len(T.PRESETS)


class NumberWordsDialog:
    def __init__(self, ctx, calc, source="", target="", sample=None, initial=None, file_layer=None):
        """`calc`: show the cell fields, the output choice and the file default; `sample`: the number read in the
        preview (Writer); `initial`: the values to open with; `file_layer`: the file's default (Sheets)."""
        values = initial or DEFAULTS
        self.calc, self.sample, self.accepted, self.file_layer = calc, sample, None, file_layer or {}
        self.money = values["money"]
        self.groups = {False: values["number_options"], True: values["money_options"]}  # reading options per kind
        self.confirmed = False  # the user saw the "already holds data" notice for the current fields
        colours = palette(ctx)
        height = 258 if calc else 198
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
        rows = [("kind", D["kind"], D["kinds"] if calc else D["writerKinds"], int(values["money"])),
                ("preset", D["unitPreset"], D["presets"], preset_index(values["unit"], values["sub_unit"]))]
        for name, label, items, selected in rows:
            d.label("l_" + name, label, 8, y + 2, 78)
            d.listbox(name, 90, y, 172, items, selected=selected, help_text=label)
            y += 16
        d.label("l_unit", D["unit"], 8, y + 2, 78)
        d.edit("unit", 90, y, 60, text=values["unit"], help_text=D["unit"])
        d.label("l_sub", D["subUnit"], 158, y + 2, 46)
        d.edit("sub", 206, y, 56, text=values["sub_unit"], help_text=D["subUnit"])
        y += 18
        indexes = option_indexes(self.groups[self.money])
        lists = [(key, D[key], D[key + "s"], indexes[key]) for key in CHOICES]
        if calc:
            lists.append(("output", D["output"], D["outputs"], int(values["formula"])))
        for name, label, items, selected in lists:
            d.label("l_" + name, label, 8, y + 2, 78)
            d.listbox(name, 90, y, 172, items, selected=selected, help_text=label)
            y += 16
        if calc:
            d.check("file_default", D["fileDefault"], 90, y + 2, 172, state=has_group(self.file_layer, self.money))
            d.label("hint", "", 90, y + 14, 172).TextColor = colours["muted"]
            y += 26
        d.label("l_preview", D["preview"], 8, y + 4, 78)
        d.label("preview", "", 90, y + 4, 172, 30, wrap=True)
        if calc:
            d.label("notice", "", 8, y + 36, 254, 18, wrap=True).TextColor = colours["error"]
        y = height - 22
        d.button("ok", D["insert"] if calc else D["replace"], 140, y, 60, callback=self._accept, default=True)
        d.button("cancel", T.SAVE_BUTTONS[2], 204, y, 58, kind=2)
        names = ["source", "unit", "sub", "thousand", "odd", "four", "language"] + (["target"] if calc else [])
        d.on_change(names, self._update)
        d.on_change(["kind"], self._kind)
        d.on_change(["preset"], self._preset)
        d.on_ready = self._update
        self.read_cell = None  # Sheets: callable(source text) -> value of its first cell, for the preview
        self.occupied = None  # Sheets: callable(choice) -> how many target cells to write already hold data

    def _preset(self):
        index = self.d.get("preset")
        if 0 <= index < len(T.PRESETS):
            self.d.set_text("unit", T.PRESETS[index][0])
            self.d.set_text("sub", T.PRESETS[index][1])
        self._update()

    def _kind(self):
        """Numbers and money keep their own reading options (and file default box): show those of the new kind."""
        money = self.d.get("kind") == 1
        if money != self.money:
            self.groups[self.money] = self.choice()["options"].text()
            for key, index in option_indexes(self.groups[money]).items():
                self.d.select(key, index)
            if self.calc:
                self.d.model.getByName("file_default").State = int(has_group(self.file_layer, money))
            self.money = money
        self._update()

    def choice(self):
        """{'money', 'unit', 'sub_unit', 'options' (number_words.Options), 'formula', 'source', 'target',
        'file_default' (Sheets: make this kind's reading the file's default)}."""
        picked = {key: allowed[max(0, self.d.get(key))] for key, allowed in CHOICES.items()}
        options = number_words.Options(**picked)
        return {"money": self.d.get("kind") == 1, "unit": self.d.get("unit").strip(), "sub_unit": self.d.get("sub").strip(),
                "options": options, "formula": self.calc and self.d.get("output") == 1,
                "source": self.d.get("source").strip(), "target": self.d.get("target").strip() if self.calc else "",
                "file_default": self.calc and self.d.get("file_default")}

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
        if self.calc:
            current = {"unit": choice["unit"], "sub_unit": choice["sub_unit"],
                       options_key(choice["money"]): choice["options"].text()}
            uses_file = matches(self.file_layer, choice["money"], current)
            self.d.model.getByName("hint").Label = D["fileDefaultHint"] if uses_file else ""
            self._confirm(False)

    def _confirm(self, shown, count=0):
        """Show (or clear) the notice that `count` target cells already hold data; the next "Ghi đè" writes."""
        self.confirmed = shown
        self.d.model.getByName("notice").Label = D["occupied"] % count if shown else ""
        self.d.model.getByName("ok").Label = D["overwrite"] if shown else D["insert"]

    def _accept(self):
        choice = self.choice()
        if self.calc and not self.confirmed and self.occupied:
            count = self.occupied(choice)
            if count:
                return self._confirm(True, count)
        self.accepted = choice
        self.d.end(1)

    def run(self, parent_peer=None):
        self.d.execute(parent_peer)
        return self.accepted
