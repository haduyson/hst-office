# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up phases of one office launch, from window samples and the Python trace (pure; used by startup-timing.py).

A sample is (t, [(pid, width, height, title, kind)]) with t in seconds since launch and kind one of "splash",
"frame", "dialog" or "" (the sampler's own classification when the OS tells it, else ""). Without a kind the size
decides: a window the size of the splash bitmap (at any of the usual scale factors) is the splash, a larger one the
first document or Start Center frame.
"""
SCALES = (1.0, 1.25, 1.5, 1.75, 2.0)
TOLERANCE = 4  # pixels; window managers may add a border


def splash_sizes(bitmap):
    """Window sizes the splash may take on screen: the bitmap at each scale factor."""
    width, height = bitmap
    return [(round(width * scale), round(height * scale)) for scale in SCALES] + [
        (round(width / scale), round(height / scale)) for scale in SCALES[1:]]


def kind_of(window, bitmap):
    _pid, width, height, _title, kind = window[:5]  # Windows samples add the left and top pixel
    if kind:
        return kind
    for w, h in splash_sizes(bitmap):
        if abs(width - w) <= TOLERANCE and abs(height - h) <= TOLERANCE:
            return "splash"
    return "frame" if width * height > bitmap[0] * bitmap[1] * 1.5 else "dialog"


def phases(samples, bitmap):
    """{"splash_shown", "splash_gone", "frame_shown", "splash_visible_s", "launch_to_frame_s", "pids",
    "splash_windows"}: first splash, last time a splash was seen before the frame, first frame; None when not seen."""
    splash_shown = splash_last = frame_shown = None
    pids, splash_windows = [], []
    for t, windows in samples:
        kinds = [(kind_of(w, bitmap), w) for w in windows]
        for _kind, window in kinds:
            if window[0] not in pids:
                pids.append(window[0])
        if frame_shown is None and any(kind == "frame" for kind, _w in kinds):
            frame_shown = t
        for kind, window in kinds:
            if kind != "splash":
                continue
            if splash_shown is None:
                splash_shown = t
            if frame_shown is None:
                splash_last = t
            size = (window[1], window[2])
            if size not in splash_windows:
                splash_windows.append(size)
    return {"splash_shown": splash_shown, "splash_gone": splash_last, "frame_shown": frame_shown,
            "splash_visible_s": None if splash_shown is None else round((splash_last or splash_shown) - splash_shown, 3),
            "launch_to_frame_s": frame_shown, "pids": pids, "splash_windows": splash_windows}


def python_breakdown(events, launched, frame_shown=None):
    """Python's share of a start from the tracer's events (scripts/perf/startup_trace/sitecustomize.py).

    Returns {"python_init_s": first interpreter start after launch, "imports_s": top-level import time per process,
    "compiled": source files compiled, "compile_s": time spent compiling them, "from_bytecode": the other
    Python modules (bytecode, frozen), "slowest": the ten slowest
    top-level imports, "calls": HST entry points with their thread, "network": DNS lookups and connects}."""
    out = {"python_init_s": None, "imports_s": 0.0, "compiled": 0, "compile_s": 0.0, "from_bytecode": 0, "slowest": [], "calls": [],
           "network": []}
    inits = [e for e in events if e.get("ev") == "python-init"]
    if inits:
        out["python_init_s"] = round(min(e["t"] for e in inits) - launched, 3)
    imports = [e for e in events if e.get("ev") == "import"]
    # an import event is written when its module finished: one that ends inside another's span is nested in it
    spans = [(e["t"] - e["dt"], e["t"], e) for e in imports]
    top = [e for start, end, e in spans  # nested: inside a longer span of the same process (1 us clock slack)
           if not any(s <= start + 1e-6 and end <= t2 + 1e-6 and t2 - s > end - start and other["pid"] == e["pid"]
                      for s, t2, other in spans)]
    out["imports_s"] = round(sum(e["dt"] for e in top), 3)
    compiles = [e for e in events if e.get("ev") == "compile"]
    out["compiled"] = len(compiles)
    out["compile_s"] = round(sum(e["dt"] for e in compiles), 3)
    out["from_bytecode"] = sum(e.get("src") == "pyc" for e in imports) + sum(e.get("src") == "py" for e in imports) \
        - len(compiles)
    out["slowest"] = [(e["mod"], round(e["dt"], 3)) for e in sorted(top, key=lambda e: -e["dt"])[:10]]
    if frame_shown is not None:  # the part the user waits for: Python work before the first window was on screen
        cut = launched + frame_shown
        out["before_frame"] = {
            "imports_s": round(sum(min(e["t"], cut) - (e["t"] - e["dt"]) for e in top if e["t"] - e["dt"] < cut), 3),
            "modules": sum(e["t"] <= cut for e in imports),
            "compiled": sum(e["t"] <= cut for e in compiles),
            "compile_s": round(sum(e["dt"] for e in compiles if e["t"] <= cut), 3),
            "hst_modules": sorted(e["mod"] for e in imports if e["t"] <= cut and e["mod"].startswith("hst_office"))}
    out["calls"] = [(round(e["t"] - e["dt"] - launched, 3), e["what"], round(e["dt"], 3), e.get("thread"))
                    for e in events if e.get("ev") == "call"]
    out["network"] = [(round(e["t"] - launched, 3), e["what"], str(e.get("host")), e.get("thread"))
                      for e in events if e.get("ev") == "net"]
    return out
