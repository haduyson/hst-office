# SPDX-License-Identifier: AGPL-3.0-only
"""Keep GStreamer's DirectFB video sink away from HST Office's media playback (the shared program/soffice script).

avmedia plays video through GStreamer's autovideosink (gen/kf5, or gtk3 without gtksink). On a system with
gstreamer1.0-plugins-bad (which ships dfbvideosink) but without gstreamer1.0-x (ximagesink/xvimagesink),
autovideosink picks dfbvideosink, whose DirectFB start-up crashes the whole office (SIGSEGV in the
"Fusion Dispatch" thread of libfusion) as soon as a presentation with a video is opened.

The .deb's program/soffice script (also the .rpm's and the AppImage's: both repack the .deb) therefore ranks
dfbvideosink NONE through GST_PLUGIN_FEATURE_RANK: set when the user has not set the variable, appended to the
user's value otherwise, and left alone when the user already ranks dfbvideosink themselves.
"""
import re

MARKER = "# HST Office: GStreamer DirectFB video sink"
SNIPPET = MARKER + """ (scripts/linux/soffice_gstreamer_env.py)
case ",${GST_PLUGIN_FEATURE_RANK}," in
    *,dfbvideosink:*) ;;
    ,,) GST_PLUGIN_FEATURE_RANK=dfbvideosink:NONE ;;
    *) GST_PLUGIN_FEATURE_RANK="${GST_PLUGIN_FEATURE_RANK},dfbvideosink:NONE" ;;
esac
export GST_PLUGIN_FEATURE_RANK

"""
_LAST_EXEC = re.compile(r'(?m)^exec [^\n]*"\$sd_prog/oosplash" "\$@"\n')


def add_to_script(text):
    """program/soffice with SNIPPET before its final exec of oosplash (unchanged when already there)."""
    if MARKER in text:
        return text
    found = list(_LAST_EXEC.finditer(text))
    if not found:
        raise ValueError("program/soffice: no exec of oosplash found")
    at = found[-1].start()
    return text[:at] + SNIPPET + text[at:]


def patch_tree(stage, install_root):
    """Apply add_to_script to <stage>/<install_root>/program/soffice; returns the path."""
    path = stage / install_root.lstrip("/") / "program/soffice"
    mode = path.stat().st_mode
    path.write_text(add_to_script(path.read_text(encoding="utf-8")), encoding="utf-8")
    path.chmod(mode)
    return path
