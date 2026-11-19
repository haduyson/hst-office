# SPDX-License-Identifier: AGPL-3.0-only
"""Where the Trợ lý AI keeps the user's API keys: never in plain text, never in the profile's settings.

Order: the operating system's credential store (Windows Credential Manager, macOS Keychain, the Linux Secret
Service); when that is unavailable, the office's password store, but only while it is protected by a master
password the user set (with the built-in default master password it is merely obfuscated, so it is not used);
otherwise the key is kept in memory until HST Office closes, and the options page says so.
"""
import sys

from . import diag_log

URL = "vnd.hasontech.hstoffice.ai://%s"  # password container record of one provider
USER = "api-key"
SESSION_LABEL = "bộ nhớ tạm (chỉ đến khi đóng HST Office)"
CONTAINER_LABEL = "kho mật khẩu của HST Office (có mật khẩu chính)"
_SESSION = {}


def os_store(platform=sys.platform):
    """The OS credential store of this platform, or None when it cannot be loaded."""
    try:
        if platform == "win32":
            from .ai_keystore_windows import Store
        elif platform == "darwin":
            from .ai_keystore_macos import Store
        else:
            from .ai_keystore_linux import Store
        return Store()
    except (OSError, AttributeError, ImportError):
        diag_log.exception("ai_keystore")
        return None


class SessionStore:
    label = SESSION_LABEL

    def get(self, provider):
        return _SESSION.get(provider)

    def set(self, provider, key):
        _SESSION[provider] = key

    def delete(self, provider):
        _SESSION.pop(provider, None)


class ContainerStore:
    """The office's password container, used only when a user master password protects it."""
    label = CONTAINER_LABEL

    def __init__(self, ctx):
        smgr = ctx.ServiceManager
        self.container = smgr.createInstanceWithContext("com.sun.star.task.PasswordContainer", ctx)
        self.handler = smgr.createInstanceWithContext("com.sun.star.task.InteractionHandler", ctx)
        if not (self.container.isPersistentStoringAllowed() and self.container.hasMasterPassword()
                and not self.container.isDefaultMasterPasswordUsed()):
            raise OSError("no user master password")

    def get(self, provider):
        record = self.container.find(URL % provider, self.handler)
        for user in getattr(record, "UserList", ()) or ():
            if user.UserName == USER and user.Passwords:
                return user.Passwords[0]
        return None

    def set(self, provider, key):
        self.container.addPersistent(URL % provider, USER, (key,), self.handler)

    def delete(self, provider):
        self.container.removePersistent(URL % provider, USER)


class Keystore:
    """Facade used by the options page and the assistant: get/set/delete one provider's key."""

    def __init__(self, ctx, store=None):
        self.ctx, self.store = ctx, store

    def _store(self):
        if self.store is None:
            self.store = os_store()
            if self.store is not None and not self._works(self.store):
                self.store = None
        if self.store is None:
            try:
                self.store = ContainerStore(self.ctx)
            except Exception:  # noqa: BLE001 - no master password or no container: session only
                self.store = SessionStore()
        return self.store

    @staticmethod
    def _works(store):
        """A store that loads but has no service behind it (Linux without a keyring daemon) fails a lookup."""
        try:
            store.get("probe")
            return True
        except Exception:  # noqa: BLE001
            diag_log.exception("ai_keystore")
            return False

    @property
    def label(self):
        return self._store().label

    @property
    def persistent(self):
        return not isinstance(self._store(), SessionStore)

    def get(self, provider):
        try:
            return self._store().get(provider) or _SESSION.get(provider)
        except Exception:  # noqa: BLE001 - a locked keychain or a cancelled master password: no key
            diag_log.exception("ai_keystore")
            return _SESSION.get(provider)

    def set(self, provider, key):
        """Store `key`; returns the label of the place it went (falls back to the session on failure)."""
        try:
            self._store().set(provider, key)
            return self._store().label
        except Exception:  # noqa: BLE001
            diag_log.exception("ai_keystore")
            _SESSION[provider] = key
            return SESSION_LABEL

    def delete(self, provider):
        _SESSION.pop(provider, None)
        try:
            self._store().delete(provider)
            return True
        except Exception:  # noqa: BLE001
            diag_log.exception("ai_keystore")
            return False
