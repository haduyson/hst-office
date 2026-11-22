# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Tùy chọn ▸ HST Office ▸ Trợ lý AI (OptionsDialog.xcu, dialogs/AI.xdl).

Settings (on/off, provider, model) are saved on OK; Cancel keeps the old ones. The key box never shows a stored key:
a key typed there is stored on OK (ai_keystore: the OS credential store) for the selected provider; "Xóa khóa"
removes it at once. "Tải danh sách" and "Kiểm tra khóa" send a request to the provider with the key (and, for the
check, a one-word question), only when pressed; they run on a worker thread and report in the status line.
"""
import unohelper
from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo

from . import ai_config, ai_options_requests, diag_log, privacy_link
from .ai_providers import ORDER, PROVIDERS
from .dialogs import _Action, _Changed, palette

HANDLER_NAME = "org.hst.office.vi.OptionsAI"
NONE_LABEL = "(Chưa chọn)"
TEXT = {
    "stored": "Đã có khóa, lưu trong %s.",
    "missing": "Chưa có khóa cho nhà cung cấp này.",
    "choose": "Chọn nhà cung cấp để nhập khóa API.",
    "deleted": "Đã xóa khóa đã lưu.",
    "saved": "Đã lưu khóa trong %s.",
}


def provider_items():
    return [NONE_LABEL] + [PROVIDERS[p]["label"] for p in ORDER]


def provider_at(index):
    """Pure: provider id of a list position (0 = none)."""
    return ORDER[index - 1] if 1 <= index <= len(ORDER) else ""


def changes_from_page(enabled, index, model):
    """Pure: the settings to save from the page state (the model is remembered per provider)."""
    provider = provider_at(index)
    changes = {"Enabled": bool(enabled), "Provider": provider}
    if provider:
        model = (model or "").strip()
        changes[ai_config.MODEL_KEYS[provider]] = "" if model == PROVIDERS[provider]["models"][0] else model
    return changes


class AiOptionsHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):
    def __init__(self, ctx):
        self.ctx, self.window, self._wired, self._listeners = ctx, None, None, []
        self.values = dict(ai_config.DEFAULTS)
        self._keystore = None

    def getImplementationName(self):
        return HANDLER_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return (HANDLER_NAME,)

    def getSupportedMethodNames(self):
        return ("external_event", "loadModels", "deleteKey", "testKey")

    def callHandlerMethod(self, window, event, method):
        try:
            self.window = window
            if method == "external_event":
                if event in ("initialize", "back"):
                    self._load()
                elif event == "ok":
                    self._save()
                return True
            if method in ("loadModels", "deleteKey", "testKey"):
                getattr(self, "_" + method)()
                return True
        except Exception:  # noqa: BLE001 - never raise into the options dialog
            diag_log.exception("ai_options")
        return False

    def keystore(self):
        if self._keystore is None:
            from .ai_keystore import Keystore
            self._keystore = Keystore(self.ctx)
        return self._keystore

    def _control(self, name):
        return self.window.getControl(name)

    def _status(self, text, error=False):
        model = self._control("status").getModel()
        model.Label, model.TextColor = text, palette(self.ctx)["error" if error else "muted"]

    def _provider(self):
        selected = self._control("provider").getSelectedItemPos()
        return provider_at(selected)

    def _load(self):
        self.values, locked = ai_config.load(self.ctx)
        self._control("enabled").setState(1 if self.values["Enabled"] else 0)
        self._control("enabled").setEnable("Enabled" not in locked)
        box = self._control("provider")
        box.removeItems(0, box.getItemCount())
        box.addItems(tuple(provider_items()), 0)
        provider = self.values["Provider"]
        box.selectItemPos(ORDER.index(provider) + 1 if provider in ORDER else 0, True)
        box.setEnable("Provider" not in locked)
        self._control("key").getModel().EchoChar = ord("•")
        self._control("locked").setVisible(bool(locked & {"Enabled", "Provider"}))
        self._wire()
        self._provider_changed()
        self._status("")

    def _wire(self):
        if self._wired is self.window:
            return
        privacy = self._control("privacy")
        model = privacy.getModel()
        model.Label = model.HelpText = privacy_link.ui_label(self.ctx)
        model.TextColor = palette(self.ctx)["link"]
        self._control("keysPage").getModel().TextColor = palette(self.ctx)["link"]
        self._listeners = [_Action(lambda: privacy_link.open_policy(self.ctx, "options")),
                           _Action(self._open_keys_page), _Changed(self._provider_changed)]
        privacy.addActionListener(self._listeners[0])
        self._control("keysPage").addActionListener(self._listeners[1])
        self._control("provider").addItemListener(self._listeners[2])
        self._wired = self.window

    def _provider_changed(self):
        provider = self._provider()
        combo = self._control("model")
        combo.removeItems(0, combo.getItemCount())
        has = bool(provider)
        for name in ("model", "loadModels", "key", "deleteKey", "test", "keysPage"):
            self._control(name).setEnable(has)
        self._control("key").setText("")
        if not has:
            combo.setText("")
            self._control("keyStatus").getModel().Label = TEXT["choose"]
            return
        combo.addItems(PROVIDERS[provider]["models"], 0)
        combo.setText(ai_config.model_for(self.values, provider))
        stored = self.keystore().get(provider)
        self._control("keyStatus").getModel().Label = (TEXT["stored"] % self.keystore().label) if stored \
            else TEXT["missing"]

    def _open_keys_page(self):
        provider = self._provider()
        if provider:
            shell = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.system.SystemShellExecute", self.ctx)
            shell.execute(PROVIDERS[provider]["keys_page"], "", 1)  # 1 = URIS_ONLY

    def _save(self):
        changes = changes_from_page(self._control("enabled").getState() == 1,
                                    self._control("provider").getSelectedItemPos(),
                                    self._control("model").getText())
        ai_config.save(self.ctx, changes)
        key, provider = self._control("key").getText().strip(), changes["Provider"]
        if key and provider:
            self.keystore().set(provider, key)
        from .ai_handler import broadcast_all
        broadcast_all()

    def _deleteKey(self):
        provider = self._provider()
        if provider and self.keystore().delete(provider):
            self._status(TEXT["deleted"])
        self._provider_changed()

    def _loadModels(self):
        ai_options_requests.load_models(self)

    def _testKey(self):
        ai_options_requests.test_key(self)
