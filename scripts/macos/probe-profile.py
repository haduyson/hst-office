# SPDX-License-Identifier: AGPL-3.0-only
"""Edit a user profile's registrymodifications.xcu for the macOS probes (stdlib only).

probe-profile.py <profile> [--shown true|false|unset] [--transparency N] [--no-tip]
  --shown          set or remove (unset) /org.hasontech.hstoffice.Welcome Shown
  --transparency   Office.Common/Misc NotebookbarColorTransparency
  --no-tip         ShowTipOfTheDay=false
The profile must already exist (run soffice --headless --terminate_after_init first), otherwise the first start
rewrites the file."""
import argparse
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("profile")
parser.add_argument("--shown", choices=("true", "false", "unset"))
parser.add_argument("--transparency", type=int)
parser.add_argument("--no-tip", action="store_true")
args = parser.parse_args()
path = Path(args.profile) / "user" / "registrymodifications.xcu"
text = path.read_text(encoding="utf-8")


def drop(text, node, name):
    return re.sub(r'<item oor:path="%s"><prop oor:name="%s"[^\n]*</item>\n?' % (re.escape(node), name), "", text)


def item(node, name, value):
    return f'<item oor:path="{node}"><prop oor:name="{name}" oor:op="fuse"><value>{value}</value></prop></item>\n'


add = ""
if args.shown:
    text = drop(text, "/org.hasontech.hstoffice.Welcome", "Shown")
    if args.shown != "unset":
        add += item("/org.hasontech.hstoffice.Welcome", "Shown", args.shown)
if args.transparency is not None:
    text = drop(text, "/org.openoffice.Office.Common/Misc", "NotebookbarColorTransparency")
    add += item("/org.openoffice.Office.Common/Misc", "NotebookbarColorTransparency", args.transparency)
if args.no_tip:
    text = drop(text, "/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay")
    add += item("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")
path.write_text(text.replace("</oor:items>", add + "</oor:items>"), encoding="utf-8")
