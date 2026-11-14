# SPDX-License-Identifier: AGPL-3.0-only
"""Has the user started working since the start-up questions were scheduled?

The questions wait for the end of every document load (welcome_job.run_later). On a busy machine that can be long
after the first window: the user (or a launcher) has meanwhile opened further documents, typed, closed a tab. A modal
question that opens then lands on top of the work and holds closing the tab or quitting until it is answered. Such a
question waits for a calmer start instead; only the crash question, which is read once per start, still runs.

snapshot() is taken when the questions are scheduled (onFirstVisibleTask), started_working() when they are due.
"""


def _frames(ctx):
    access = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getFrames()
    return [access.getByIndex(index) for index in range(access.getCount())]


def snapshot(ctx):
    """[(frame, controller)] of the desktop now; the controller is None while a document is still being imported."""
    return [(frame, frame.getController()) for frame in _frames(ctx)]


def _contains(items, item):
    return any(item == other for other in items)  # pyuno proxies compare by UNO object identity


def _hidden_load(frame):
    """A hidden load (a macro, a conversion, an extension's helper document) is not the user's work."""
    controller = frame.getController()
    if controller is None:
        window = frame.getContainerWindow()
        return window is None or not window.isVisible()
    model = controller.getModel()
    if model is None:
        return False
    return any(arg.Name == "Hidden" and arg.Value is True for arg in model.getArgs())


def _modified(frame):
    controller = frame.getController()
    model = controller.getModel() if controller is not None else None
    return bool(model is not None and hasattr(model, "isModified") and model.isModified())


def started_working(ctx, before):
    """True when, since `before` (snapshot()), a document was opened or closed, a window got another document (the
    Start Center replaced by a new document) or a document was modified."""
    now = _frames(ctx)
    old_frames = [frame for frame, _controller in before]
    if any(not _contains(old_frames, frame) and not _hidden_load(frame) for frame in now):
        return True
    if any(not _contains(now, frame) for frame in old_frames):
        return True
    for frame, controller in before:
        current = frame.getController()
        # None: a document opened at start was still loading then; its controller arriving is no work of the user
        if controller is not None and (current is None or not current == controller):
            return True
    return any(_modified(frame) for frame in now)
