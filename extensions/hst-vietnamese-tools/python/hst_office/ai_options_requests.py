# SPDX-License-Identifier: AGPL-3.0-only
"""The two buttons of Tùy chọn ▸ HST Office ▸ Trợ lý AI that talk to the provider, only when pressed: "Tải danh sách"
(the models the key may use) and "Kiểm tra khóa" (a one-word question). Each runs on a worker thread; the answer
is shown in the page's status line on the main thread."""
import threading

from . import diag_log
from .ai_providers import PROVIDERS, AiError

TEXT = {"loading": "Đang hỏi %s…", "models": "Đã tải %d mô hình.", "test_ok": "Khóa và mô hình dùng được."}


def settings_of(page):
    """ai_client.Settings of the page as it is now (a typed key wins over the stored one)."""
    from .ai_client import Settings
    from .office_proxy import proxy
    from .update_fetch import release_info
    provider = page._provider()
    key = page._control("key").getText().strip() or (page.keystore().get(provider) if provider else None)
    return Settings(provider, page._control("model").getText().strip(), key, release_info()["release"],
                    proxy(page.ctx))


def background(page, work, done):
    """Run work(settings) on a thread; done(result) on the main thread, or the error in the status line."""
    from .update_ui import on_main_thread
    settings = settings_of(page)
    page._status(TEXT["loading"] % PROVIDERS[settings.provider]["label"] if settings.provider else "")

    def run():
        try:
            result = work(settings)
        except AiError as error:
            result = error
        except Exception as error:  # noqa: BLE001
            diag_log.exception("ai_options")
            result = AiError("reply", type(error).__name__)
        on_main_thread(page.ctx, lambda: finish(page, done, result))
    threading.Thread(target=run, name="hst-ai-options", daemon=True).start()


def finish(page, done, result):
    try:
        if isinstance(result, AiError):
            from .ai_texts import error_text
            page._status(error_text(result), error=True)
        else:
            done(result)
    except Exception:  # noqa: BLE001 - the options dialog closed meanwhile
        pass


def load_models(page):
    from .ai_client import list_models

    def done(models):
        combo = page._control("model")
        current = combo.getText()
        combo.removeItems(0, combo.getItemCount())
        combo.addItems(tuple(models), 0)
        combo.setText(current)
        page._status(TEXT["models"] % len(models))
    background(page, list_models, done)


def test_key(page):
    from .ai_client import complete
    background(page, lambda s: complete(s, "Trả lời đúng một từ.", "Xin chào"), lambda _: page._status(TEXT["test_ok"]))
