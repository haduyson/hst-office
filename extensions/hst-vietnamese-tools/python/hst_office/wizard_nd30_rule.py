# SPDX-License-Identifier: AGPL-3.0-only
"""The "Đường kẻ dưới tên cơ quan" row of the ND30 wizard: a list of lengths (nd30_rule_length.CHOICES) and an edit
for a length in mm, enabled only for "Tự nhập (mm)". Off for profiles without an agency rule (the Party forms)."""
from . import nd30_rule_length as rules

NAMES = ("agencyRule", "agencyRuleMm")


class AgencyRuleRow:
    def __init__(self, d, strings, value, x_label, w_label, x_field, w_field, y):
        self.d, self.s = d, strings
        choice, mm = rules.parse(value)
        d.label("l_agencyRule", strings["agencyRule"], x_label, y + 2, w_label, 10)
        d.listbox("agencyRule", x_field, y, w_field - 74, strings["agencyRuleChoices"], rules.CHOICES.index(choice),
                  help_text=strings["agencyRuleHelp"])
        d.edit("agencyRuleMm", x_field + w_field - 70, y, 50, text="" if mm is None else "%g" % mm,
               help_text=strings["agencyRuleMm"])
        d.label("l_agencyRuleMm", "mm", x_field + w_field - 17, y + 2, 17, 10)
        self.sync(True)

    def choice(self):
        index = self.d.get("agencyRule")
        return rules.CHOICES[index] if 0 <= index < len(rules.CHOICES) else rules.DEFAULT

    def value(self):
        """The field/remembered form ("2/5", "parent", "mm:30" ...), or None while the typed length is not valid."""
        choice = self.choice()
        return rules.encode(choice, rules.parse_mm(self.d.get("agencyRuleMm")) if choice == "mm" else None)

    def error(self):
        """What to fix in the row; nothing while it is off (a Party form has no agency rule)."""
        enabled = self.d.model.getByName("agencyRule").Enabled
        return self.s["agencyRuleMmError"] if enabled and self.value() is None else None

    def sync(self, has_rule):
        """Enable the row for profiles with an agency rule; the mm edit only for a typed length."""
        model = self.d.model
        for name in ("l_agencyRule", "agencyRule", "l_agencyRuleMm"):
            model.getByName(name).Enabled = has_rule
        model.getByName("agencyRuleMm").Enabled = has_rule and self.choice() == "mm"
