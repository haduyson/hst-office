# SPDX-License-Identifier: AGPL-3.0-only
"""Quick access toolbar of the HST ribbon over UNO, shared by the Linux and Windows checks: the default and test
command lists, the commands a module shows, and replacing them (from the caller's thread, as a UNO client does)."""

DEFAULTS = [".uno:Save", ".uno:Undo", ".uno:Redo"]
WRITER, CALC = "com.sun.star.text.TextDocument", "com.sun.star.sheet.SpreadsheetDocument"
MANY = [".uno:Paste", ".uno:Cut", ".uno:Copy", ".uno:Bold", ".uno:Italic", ".uno:Underline", ".uno:CenterPara",
        ".uno:DefaultBullet", ".uno:InsertTable", ".uno:InsertGraphic", ".uno:SearchDialog", ".uno:Print",
        ".uno:PrintPreview"]


def shown(office, module):
    """Commands shown in the module's quick access toolbar (its notebookbarshortcuts settings). The toolbox sits in
    the ribbon's tab control, whose accessible children are only the tabs, so the list is read over UNO."""
    supplier = office.smgr.createInstanceWithContext(
        "com.sun.star.ui.ModuleUIConfigurationManagerSupplier", office.ctx)
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
    supplier = office.smgr.createInstanceWithContext(
        "com.sun.star.ui.ModuleUIConfigurationManagerSupplier", office.ctx)
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
