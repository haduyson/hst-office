# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ Khối địa chỉ / Dòng chào: which column holds the title, gender, name, position, unit and address
(found from the headers, changeable), the Vietnamese options and a live example of the recipient shown. Returns the
settings to store in the document (mail_merge_store meta "block" or "greeting")."""
import uno

from . import mail_merge_address as address
from .dialogs import Dialog

BLOCK_ROLES = address.ROLES
GREETING_ROLES = ("title", "gender", "name")


class AddressDialog:
    def __init__(self, ctx, texts, table, row, stored, greeting=False):
        self.t, self.table, self.row, self.greeting = texts, table, row, greeting
        default = address.GREETING_DEFAULT if greeting else address.BLOCK_DEFAULT
        self.conf = address.settings(stored, table.headers, default)
        self.roles = GREETING_ROLES if greeting else BLOCK_ROLES
        self.columns = [""] + list(table.headers)
        self.result = None
        top = 112 if greeting else 146  # the example under the options
        d = self.d = Dialog(ctx, texts["greet.title" if greeting else "block.title"], 320, top + 68)
        y = 6
        for role in self.roles:
            d.label("l_" + role, texts["role." + role], 8, y + 2, 90)
            choices = [texts["role.none"]] + list(table.headers)
            current = self.conf.get(role, "")
            d.listbox("r_" + role, 100, y, 120, choices, self.columns.index(current) if current in self.columns else 0,
                      help_text=texts["role." + role])
            y += 15
        styles = [texts["style.formal"], texts["style.friendly"]]
        d.label("styleLabel", texts["style.label"], 8, y + 2, 90)
        d.listbox("style", 100, y, 120, styles, 0 if self.conf["style"] == "formal" else 1, help_text=texts["style.label"])
        y += 15
        if greeting:
            d.label("openLabel", texts["greet.opening"], 8, y + 2, 90)
            d.listbox("opening", 100, y, 120, list(address.OPENINGS), _index(address.OPENINGS, self.conf["opening"]))
            d.label("endLabel", texts["greet.ending"], 226, y + 2, 40)
            endings = [e or texts["greet.no-ending"] for e in address.ENDINGS]
            d.listbox("ending", 266, y, 46, endings, _index(address.ENDINGS, self.conf["ending"]))
            d.check("given", texts["greet.given"], 8, y + 16, 304, self.conf["given"])
            d.check("capital", texts["greet.capital"], 8, y + 28, 304, self.conf["capital"])
            watched = ["opening", "ending", "given", "capital"]
        else:
            d.label("leadLabel", texts["block.lead"], 8, y + 2, 90)
            d.edit("lead", 100, y, 120, text=self.conf["lead"], help_text=texts["block.lead"])
            d.check("oneLine", texts["block.one-line"], 8, y + 16, 304, self.conf["one_line"])
            watched = ["lead", "oneLine"]
        d.label("exampleLabel", texts["ins.preview"], 8, top + 4, 304)
        d.edit("example", 8, top + 14, 304, h=34, multiline=True, readonly=True, help_text=texts["ins.preview"])
        d.button("ok", texts["ins.insert"], 196, top + 50, 56, default=True, callback=self._accept)
        d.button("cancel", texts["cancel"], 256, top + 50, 56, callback=lambda: d.end(0))
        d.on_change(["r_" + r for r in self.roles] + ["style"] + watched, self._update)
        d.on_ready = self._update

    def _read(self):
        conf = dict(self.conf)
        for role in self.roles:
            conf[role] = self.columns[max(0, self.d.get("r_" + role))]
        conf["style"] = "formal" if self.d.get("style") <= 0 else "friendly"
        if self.greeting:
            conf["opening"] = address.OPENINGS[max(0, self.d.get("opening"))]
            conf["ending"] = address.ENDINGS[max(0, self.d.get("ending"))]
            conf["given"], conf["capital"] = self.d.get("given"), self.d.get("capital")
        else:
            conf["lead"], conf["one_line"] = self.d.get("lead").strip(), self.d.get("oneLine")
        return conf

    def _update(self):
        conf = self._read()
        if self.row is None:
            text = ""
        elif self.greeting:
            text = address.greeting(self.table, self.row, conf)
        else:
            text = address.address_block(self.table, self.row, conf)
        model = self.d.model.getByName("example")
        uno.invoke(model, "setPropertyValue", ("Text", text.replace("\n", "\r\n")))

    def _accept(self):
        self.result = self._read()
        self.d.end(1)

    def run(self, parent_peer):
        self.d.execute(parent_peer)
        return self.result


def _index(items, value):
    return items.index(value) if value in items else 0
