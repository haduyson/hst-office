# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Profile seeding for scripts/perf/large-file-open.py: no first-start dialogs, AutoRecovery and update checks off.

Seeds: default (automatic spell checking off, as in HST), spell (automatic spell checking on, as in a profile where the
user turned it on), toolbar / tabbed (standard toolbars / the tabbed bar in Writer, Calc and Impress), nothreads
(threaded formula-group calculation off), norowheight (optimal row heights not recalculated on load), autosave
(AutoRecovery on, every minute, for large documents too: the AutoRecovery freeze)."""
import os
import re

SEEDS = ("default", "spell", "toolbar", "tabbed", "nothreads", "norowheight", "autosave")
APPS = ("Writer", "Calc", "Impress")


def seed_items(seed):
    items = [("/org.openoffice.Office.Common/Misc", "FirstRun", "false"),
             ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false"),
             ("/org.openoffice.Office.Linguistic/General", "IsSpellAuto", "true" if seed == "spell" else "false"),
             ("/org.openoffice.Office.Recovery/AutoSave", "Enabled", "true" if seed == "autosave" else "false"),
             ("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
             ("/org.hasontech.hstoffice.ErrorReport", "AskAfterCrash", "false"),
             ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
             ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false"),
             ("/org.openoffice.Office.Jobs/Jobs/org.openoffice.Office.Jobs:Job['UpdateCheck']/Arguments",
              "AutoCheckEnabled", "false")]
    if seed == "autosave":  # HstLargeDocumentTimeIntervall: 1.0.2's longer interval for large documents
        items += [("/org.openoffice.Office.Recovery/AutoSave", name, "1")
                  for name in ("TimeIntervall", "HstLargeDocumentTimeIntervall")]
        items.append(("/org.openoffice.Office.Recovery/AutoSave", "UserAutoSaveEnabled", "false"))
    if seed == "nothreads":
        items.append(("/org.openoffice.Office.Calc/Formula/Calculation", "UseThreadedCalculationForFormulaGroups",
                      "false"))
    if seed == "norowheight":  # Tools - Options - Calc - Formula: recalculation on load of optimal row heights: never
        items.append(("/org.openoffice.Office.Calc/Formula/Load", "RecalcOptimalRowHeightMode", "1"))
    mode = {"toolbar": "Default", "tabbed": "notebookbar.ui"}.get(seed)
    if mode:
        for app in APPS:
            items.append(("/org.openoffice.Office.UI.ToolbarMode/Applications/"
                          "org.openoffice.Office.UI.ToolbarMode:Application['%s']" % app, "Active", mode))
    body = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n'
                   % (path, name, value) for path, name, value in items)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
            'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
            + body + "</oor:items>\n")


def create(profile, seed):
    os.makedirs(os.path.join(profile, "user"), exist_ok=True)
    with open(os.path.join(profile, "user", "registrymodifications.xcu"), "w", encoding="utf-8") as f:
        f.write(seed_items(seed))


def reseed(profile, seed):
    """Put the seed items back before every start: a first start rewrites registrymodifications.xcu and drops items
    of schemas it did not know yet (the HST extension's are registered during that start), so without this HST asks
    its default-apps question in every measured window and the stock office keeps automatic spell checking on."""
    xcu = os.path.join(profile, "user", "registrymodifications.xcu")
    if not os.path.exists(xcu):
        return
    with open(xcu, encoding="utf-8") as f:
        text = f.read()
    body = seed_items(seed).split("\n", 2)[2].rsplit("</oor:items>", 1)[0]
    if seed == "autosave":  # started without --norestore: no recovery of an earlier (killed) open
        text = re.sub(r'<item oor:path="/org.openoffice.Office.Recovery/RecoveryList[^\n]*\n', "", text)
        backup = os.path.join(profile, "user", "backup")
        for name in os.listdir(backup) if os.path.isdir(backup) else []:
            os.remove(os.path.join(backup, name))
    with open(xcu, "w", encoding="utf-8") as f:
        f.write(text.replace("</oor:items>", body + "</oor:items>", 1))


def clear_leftovers(profile, path):
    """A killed office leaves the document's lock file ("document in use") and HST's session marker (crash
    question): neither belongs to the next open."""
    lock = os.path.join(os.path.dirname(path), ".~lock.%s#" % os.path.basename(path))
    marker = os.path.join(profile, "user", "hst-office", "session.json")
    for leftover in (lock, marker):
        if os.path.exists(leftover):
            os.remove(leftover)
