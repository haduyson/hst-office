# SPDX-License-Identifier: AGPL-3.0-only
"""What the frame screenshots (hst_frame_shots.py) shoot: the applications, the frame parts and how to find them
in the accessibility tree, and the looks. Shared by the Linux and Windows runs."""

# app: (document factory, text typed into the document so the context menu has a word under the cursor)
APPS = {
    "writer": ("swriter", "Thử nghiệm khung HST: thanh công cụ, thanh bên và thanh trạng thái."),
    "sheets": ("scalc", None),
    "slides": ("simpress", None),
}

# The sidebar opens on its Properties deck; the File tab (backstage) opens and closes with its own command.
SIDEBAR_COMMAND = ".uno:SidebarDeck.PropertyDeck"
BACKSTAGE_COMMAND = ".uno:HSTBackstage"

# Frame parts found in a document window's accessibility tree: (AccessibleRole names, accessible names in Vietnamese
# or English, matched case-insensitively as substrings; empty: any name). The first showing match wins; a part that
# is not found is listed in failures.txt. The File tab (backstage) covers the document area, so its shot is the whole
# window and is not cropped.
REGIONS = {
    "ribbon": (("PAGE_TAB_LIST",), ()),  # the notebookbar's tabs and the selected tab's commands
    "sidebar": (("SPLIT_PANE",), ()),  # the deck and its tab bar, beside the document
    "statusbar": (("STATUS_BAR",), ()),
    "doctabs": (("PANEL",), ("thẻ tài liệu", "document tabs")),
}

# The parts cropped from each state's window shot; "context-menu" is shot as the menu's own window.
STATES = {
    "window": ("ribbon", "sidebar", "statusbar", "doctabs"),
    "backstage": (),
    "context-menu": (),
}

# "before" is the frame without the coat (HST_UI_COAT=0), "after" with it.
LOOKS = [(coat, theme, scale) for coat in ("before", "after") for theme in ("light", "dark") for scale in ("100", "125")]

# no update check: its modal dialog would interrupt the shots
NO_PROMPTS = [("/org.openoffice.Office.HSTUpdate", "AutoCheck", "false"),
              ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")]


def shot_name(app, state, look):
    """File name (without .png) of one window or menu shot."""
    return f"{app}-{state}-{'-'.join(look)}"


def crop_name(app, part, look):
    """File name (without .png) of one frame part cropped from a window shot."""
    return f"{app}-{part}-{'-'.join(look)}"


def matches(part, role_name, name):
    """Whether an accessible of AccessibleRole `role_name` named `name` is frame part `part`."""
    roles, names = REGIONS[part]
    if role_name not in roles:
        return False
    lowered = (name or "").lower()
    return not names or any(wanted in lowered for wanted in names)
