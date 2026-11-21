# SPDX-License-Identifier: AGPL-3.0-only
"""The Start Center has no empty band below the menu bar (gtk3), and the document tab strip still takes its row.

Usage: python3 tests/runtime/check-start-center-top-border.py --instdir DIR [--display :396]

The display must already run (e.g. `Xvfb :396 -screen 0 1366x768x24`); the check never starts or stops it.
On gtk3 the native menu bar is built on an idle (hst-gtk-menubar-lazy-build.patch). The VCL menu bar window kept
its own height meanwhile, and the window's border kept that much space at the top of the client: a white band of
about 34 px between the menu bar and the Start Center. Checks:
- a lone Start Center frame (the office's default start, menu bar shown): the container window reserves no top
  inset and the Start Center fills it;
- two Writer documents (regression guard): they share one window with the document tab strip, which still takes
  its row above the document.
Exit 1 on a failure.
"""
import argparse
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402


def wait_for(predicate, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.5)
    return predicate()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":396")
    parser.add_argument("--workdir")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    workdir = args.workdir or tempfile.mkdtemp(prefix="hst-sc-top-border-")
    office = hst_gui.Office(args.instdir, workdir, hst_gui.free_port(), display=args.display, nodefault=False)
    failures = []
    try:
        office.start()
        frames = office.desktop().getFrames()
        if not wait_for(lambda: frames.getCount() == 1 and frames.getByIndex(0).getController() is not None):
            failures.append("no Start Center frame after the start")
        else:
            frame = frames.getByIndex(0)
            container = frame.getContainerWindow()

            def settled():
                # the native menu bar is built on an idle after the window shows: wait for the band to go
                return container.getInfo().TopInset == 0
            wait_for(settled)
            inset = container.getInfo().TopInset
            outer = container.getPosSize().Height
            inner = frame.getComponentWindow().getPosSize().Height
            print("Start Center: top inset %d px, container %d px, Start Center %d px" % (inset, outer, inner))
            if frame.getController().getImplementationName() != "com.sun.star.comp.sfx2.BackingComp":
                failures.append("the first frame is not the Start Center")
            if inset != 0:
                failures.append("the Start Center window reserves %d px at the top (empty band)" % inset)
            if inner != outer:
                failures.append("the Start Center is %d px high in a %d px window" % (inner, outer))

        # regression guard: two documents in one window show the document tab strip
        docs = [office.desktop().loadComponentFromURL("private:factory/swriter", "_blank", 0, ()) for _ in range(2)]
        time.sleep(4)
        shown = docs[-1].getCurrentController().getFrame()
        strip = shown.getComponentWindow().getPosSize().Y
        print("two documents: the document starts %d px below the window's top" % strip)
        if strip <= 0:
            failures.append("with two documents the tab strip takes no row above the document")
        for doc in docs:
            doc.close(True)
    finally:
        office.stop()
    for failure in failures:
        print("FAIL:", failure)
    print("PASS" if not failures else "FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
