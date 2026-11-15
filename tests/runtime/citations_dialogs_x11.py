# SPDX-License-Identifier: AGPL-3.0-only
"""X11 driver of check-citations-dialogs.py: find a window by its exact title, measure it, screenshot it and type
keys into it (xdotool and ImageMagick's import on a dedicated display such as Xvfb)."""
import os
import subprocess
import time


class X11Driver:
    def __init__(self, display):
        self.display = display
        self.env = dict(os.environ, DISPLAY=display)

    def _xdotool(self, *args):
        return subprocess.run(["xdotool", *args], env=self.env, capture_output=True, text=True, timeout=60)

    def wait_window(self, title, timeout=25):
        """The newest visible window titled exactly ``title``, or None."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            found = self._xdotool("search", "--onlyvisible", "--name", "^%s$" % title).stdout.split()
            if found:
                return found[-1]
            time.sleep(0.5)
        return None

    def document_window(self):
        found = self._xdotool("search", "--onlyvisible", "--name", "HST Writer").stdout.split()
        return found[0] if found else None

    def size(self, window):
        values = dict(line.split("=", 1) for line in
                      self._xdotool("getwindowgeometry", "--shell", window).stdout.split() if "=" in line)
        return int(values.get("WIDTH", 0)), int(values.get("HEIGHT", 0))

    def screenshot(self, window, path):
        subprocess.run(["import", "-window", window, path], env=self.env, check=False, timeout=60)

    def keys(self, window, *keys):
        """xdotool key names: "Tab", "space", "Escape", "Return", "alt+shift+i"."""
        if window:
            self._xdotool("windowfocus", "--sync", window)
        self._xdotool("key", "--delay", "120", *keys)
