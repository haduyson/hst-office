# SPDX-License-Identifier: AGPL-3.0-only
"""Command org.hst.office.vi:NumberToWords. Sheets: dialog "Đọc số thành chữ" reads the selected cell or column and
writes the words (plain text, which every spreadsheet keeps) or a DOCSO/DOCTIEN formula into the column to its
right, one undo step for the whole column. Writer: the selected number is replaced by its words. The dialog opens
with the file's default unit, else the user's last choice, else "đồng" (number_words_defaults.py)."""
from . import number_words
from . import number_words_calc as calc
from . import number_words_defaults as defaults
from . import number_words_file_default as file_default
from . import number_words_prefs as prefs
from . import utilities_texts as T
from .number_words_choice import error_text, words
from .number_words_dialog import NumberWordsDialog
from .number_words_range import plan
from .undo import undo_step


def run(host):
    if host.is_calc():
        return _calc(host)
    if host.is_writer():
        return _writer(host)


def _occupied(host, sheet, choice):
    """Target cells that already hold data among the rows the dialog would write (0 when the fields are wrong:
    the error is reported once the dialog closes)."""
    try:
        job = calc.resolve(host.doc, sheet, choice)
        return plan(job.values(), job.existing(), choice).occupied
    except Exception:  # noqa: BLE001 - bad address or unreadable cells: let the write path report it
        return 0


def _preview_value(host, sheet, text):
    try:
        return calc.first_value(host.doc, sheet, text)
    except ValueError:  # a wrong address: the preview says so
        raise
    except Exception:  # noqa: BLE001 - unreadable cell: the preview shows "Không đọc được số"
        return None


def _keep_file_default(doc, choice, stored):
    """The ticked box makes the unit pair the file's default; clearing it removes the file's default."""
    if choice["file_default"]:
        wanted = file_default.parse(choice["unit"], choice["sub_unit"])
        return file_default.store(doc, wanted) if wanted else True
    return file_default.store(doc, None) if stored else True


def _calc(host):
    selection = host.controller.getSelection()
    sheet = host.controller.getActiveSheet()
    if selection is None or not hasattr(selection, "getRangeAddress"):
        return host.say(T.MESSAGES["no-cells"], error=True)
    if sheet.isProtected():
        return host.say(T.MESSAGES["protected"], error=True)
    try:
        source, target = calc.selection_fields(sheet, selection.getRangeAddress())
    except ValueError as exc:
        return host.say(str(exc), error=True)
    stored = file_default.read(host.doc)
    values = defaults.resolve(defaults.unit_layer(stored), prefs.load(host.ctx))
    dialog = NumberWordsDialog(host.ctx, True, source, target, initial=values, file_default=stored)
    dialog.read_cell = lambda text: _preview_value(host, sheet, text)
    dialog.occupied = lambda choice: _occupied(host, sheet, choice)
    choice = dialog.run(host.peer)
    if choice is None:
        return
    try:
        job = calc.resolve(host.doc, sheet, choice)
        result = plan(job.values(), job.existing(), choice)
    except ValueError as exc:
        return host.say(str(exc), error=True)
    single = job.source.getRows().getCount() == 1
    if not result.writes:
        if not single:
            return host.say(T.MESSAGES["range-none"] % (choice["source"], result.skipped), error=True)
        if result.error is None:
            return host.say(T.MESSAGES["empty-cell"] % choice["source"], error=True)
        return host.say(error_text(result.error), error=True)
    host.doc.lockControllers()  # no repaint per block
    try:
        with undo_step(host.doc, T.UNDO["words"]):
            calc.write(job, result, choice)
    except Exception:  # noqa: BLE001 - protected target sheet or read-only document: nothing is left half written
        return host.say(T.MESSAGES["write-failed"], error=True)
    finally:
        host.doc.unlockControllers()
    prefs.save(host.ctx, prefs.from_choice(choice), True)
    saved = _keep_file_default(host.doc, choice, stored)
    if not single:
        done = len(result.writes)
        host.say(T.MESSAGES["range-skipped"] % (done, result.skipped) if result.skipped else T.MESSAGES["range-done"] % done)
    if not saved:
        host.say(T.MESSAGES["file-default-failed"], error=True)


def _writer(host):
    selection = host.controller.getSelection()
    if selection is None or not hasattr(selection, "getCount") or selection.getCount() != 1:
        return host.say(T.MESSAGES["writer-selection"], error=True)
    rng = selection.getByIndex(0)
    selected = rng.getString() if hasattr(rng, "getString") else ""
    if not selected.strip():
        return host.say(T.MESSAGES["writer-selection"], error=True)
    try:
        value = number_words.parse_number_text(selected)
    except number_words.NumberWordsError as exc:
        return host.say(error_text(exc), error=True)
    values = defaults.resolve(prefs.load(host.ctx))
    choice = NumberWordsDialog(host.ctx, False, selected.strip(), sample=value, initial=values).run(host.peer)
    if choice is None:
        return
    try:
        text = words(value, choice)
    except number_words.NumberWordsError as exc:
        return host.say(error_text(exc), error=True)
    try:
        with undo_step(host.doc, T.UNDO["words"]):
            # keep the spaces around the number, replace only the number itself
            lead = selected[:len(selected) - len(selected.lstrip())]
            trail = selected[len(selected.rstrip()):]
            rng.setString(lead + text + trail)
    except Exception:  # noqa: BLE001 - protected section, read-only document
        return host.say(T.MESSAGES["writer-protected"], error=True)
    prefs.save(host.ctx, prefs.from_choice(choice), False)
