# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Quick access toolbar of the HST ribbon over UNO, shared by the Linux and Windows checks: the default and test
command lists, the commands a module shows, and replacing them (from the caller's thread, as a UNO client does)."""

WRITER, CALC = "com.sun.star.text.TextDocument", "com.sun.star.sheet.SpreadsheetDocument"
IMPRESS, DRAW = "com.sun.star.presentation.PresentationDocument", "com.sun.star.drawing.DrawingDocument"
# the 1.0.2 quick access toolbar: six buttons, Mới (.uno:AddDirect: .uno:New does not exist), Mở, Lưu, Hoàn tác, Làm lại, In (owner decision D3); the
# open command of Writer and Sheets is their own (OpenFromWriter, OpenFromCalc)
OPEN_COMMAND = {WRITER: ".uno:OpenFromWriter", CALC: ".uno:OpenFromCalc"}
# KeyTips are positional: 1 Mới, 2 Mở, 3 Lưu, 4 Hoàn tác, 5 Làm lại, 6 In
UNDO_KEY, REDO_KEY = "4", "5"


def defaults(module):
    """The six default buttons of the quick access toolbar of `module` (a document service name), in order."""
    return [".uno:AddDirect", OPEN_COMMAND.get(module, ".uno:Open"), ".uno:Save", ".uno:Undo", ".uno:Redo", ".uno:Print"]


DEFAULTS = defaults(WRITER)
MANY = [".uno:Paste", ".uno:Cut", ".uno:Copy", ".uno:Bold", ".uno:Italic", ".uno:Underline", ".uno:CenterPara",
        ".uno:DefaultBullet", ".uno:InsertTable", ".uno:InsertGraphic", ".uno:SearchDialog", ".uno:Print",
        ".uno:PrintPreview"]


def _manager(office):
    """The module UI configuration manager supplier (hst_gui.Office has smgr, windows_gui.WinOffice only ctx)."""
    smgr = getattr(office, "smgr", None) or office.ctx.ServiceManager
    return smgr.createInstanceWithContext("com.sun.star.ui.ModuleUIConfigurationManagerSupplier", office.ctx)


def shown(office, module):
    """Commands shown in the module's quick access toolbar (its notebookbarshortcuts settings). The toolbox sits in
    the ribbon's tab control, whose accessible children are only the tabs, so the list is read over UNO."""
    supplier = _manager(office)
    items = supplier.getUIConfigurationManager(module).getSettings(
        "private:resource/toolbar/notebookbarshortcuts", False)
    result = []
    for index in range(items.getCount()):
        props = {p.Name: p.Value for p in items.getByIndex(index)}
        if props.get("IsVisible", True):
            result.append(props.get("CommandURL"))
    return result


def set_commands(office, module, commands):
    """Shows `commands` (and keeps the defaults) in the module's quick access toolbar through the UI configuration."""
    import uno
    supplier = _manager(office)
    config = supplier.getUIConfigurationManager(module)
    items = config.getSettings("private:resource/toolbar/notebookbarshortcuts", True)
    for command in commands:
        props = []
        for name, value in (("CommandURL", command), ("Label", ""), ("Type", 0), ("Style", 0), ("IsVisible", True)):
            prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            prop.Name, prop.Value = name, value
            props.append(prop)
        uno.invoke(items, "insertByIndex", (items.getCount(), uno.Any("[]com.sun.star.beans.PropertyValue",
                                                                          tuple(props))))
    config.replaceSettings("private:resource/toolbar/notebookbarshortcuts", items)
    config.store()
