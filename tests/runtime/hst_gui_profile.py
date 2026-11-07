# SPDX-License-Identifier: AGPL-3.0-only
"""Profile side of the GUI runtime checks (hst_gui.py): the build user, the private locale, a settled and seeded
fresh profile."""
import os
import subprocess

BUILD_USER = os.environ.get("HST_BUILD_USER", "hstbuild")


def _as_user_prefix():
    return ["runuser", "-u", BUILD_USER, "--"] if os.geteuid() == 0 else []


def ensure_locale(base, locale="vi_VN"):
    """Compile <locale>.UTF-8 into base/locpath once; return the LOCPATH directory."""
    locpath = os.path.join(base, "locpath")
    target = os.path.join(locpath, f"{locale}.UTF-8")
    if not os.path.isdir(target):
        os.makedirs(locpath, exist_ok=True)
        subprocess.run(["localedef", "-i", locale, "-f", "UTF-8", target], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return locpath


def settle_extensions(program, workdir, profile, env, user_installation):
    """Finish the bundled-extension sync before seeding. A --terminate_after_init start registers the extensions
    but never writes user/extensions/bundled/lastsynchronized, so the next start synchronizes again and re-inserts
    the extensions' schemas, dropping values seeded for them (/org.hasontech.hstoffice.Welcome/Shown read back
    false) while core values survive. One short full run (converting an empty file) completes the sync."""
    marker = os.path.join(profile, "user", "extensions", "bundled", "lastsynchronized")
    settle = os.path.join(workdir, "settle")
    os.makedirs(settle, exist_ok=True)
    empty = os.path.join(settle, "empty.txt")
    open(empty, "w").close()
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", BUILD_USER, settle], check=True)
    # The first such run ends with 81 (restart requested after the sync); run again until a clean exit, as the
    # warm-up does; with the restart left pending, the AT-SPI menu lookups of check-vietnamese-utilities failed.
    for _ in range(3):
        done = subprocess.run(_as_user_prefix() + [os.path.join(program, "soffice.bin"), "--headless", "--norestore",
                              user_installation, "--convert-to", "pdf", "--outdir", settle, empty],
                              env=env, timeout=180, check=False, capture_output=True)
        if done.returncode == 0 and os.path.exists(marker):
            return


def seed_profile(profile, config):
    """Append (node path, property, xml value) items to the fresh profile's registrymodifications.xcu."""
    path = os.path.join(profile, "user", "registrymodifications.xcu")
    items = "".join(f'<item oor:path="{node}"><prop oor:name="{name}" oor:op="fuse"><value>{value}</value></prop></item>\n'
                    for node, name, value in config)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace("</oor:items>", items + "</oor:items>"))
