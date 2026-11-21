# SPDX-License-Identifier: AGPL-3.0-only
"""Check that centimetres are the default measurement unit on a real HST Office build (hst-measure-unit-cm.patch).

Usage: <instdir>/program/python tests/runtime/check-measure-unit-cm.py --instdir <instdir> [--out DIR]

For each locale (en-US, a non-metric locale, and vi-VN), with a fresh profile, headless:
- the unit each app reads is centimetres (2): Writer and Writer/Web Layout/Other/MeasureUnit, Sheets, Slides and Draw
  Layout/Other/MeasureUnit/NonMetric (en-US) or /Metric (vi-VN);
- a unit the user chose (inch, 8, written to the profile's registrymodifications.xcu as Tools › Options does) still
  wins over the default.
The locale is set both in the environment (LANG) and in the profile (Setup/L10N/ooSetupSystemLocale), so the result
does not depend on which system locales the test machine has installed.
Writes evidence.json to --out; exit 1 when a check fails.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CENTIMETRE, INCH = 2, 8
LOCALES = {"en-US": ("en_US.UTF-8", False), "vi-VN": ("vi_VN.UTF-8", True)}
WRITER_PATHS = ("org.openoffice.Office.Writer/Layout/Other/MeasureUnit",
                "org.openoffice.Office.WriterWeb/Layout/Other/MeasureUnit")
OTHER_APPS = ("Calc", "Impress", "Draw")


def read_paths(metric):
    """The configuration path each app reads in a metric or non-metric locale."""
    variant = "Metric" if metric else "NonMetric"
    return list(WRITER_PATHS) + [f"org.openoffice.Office.{app}/Layout/Other/MeasureUnit/{variant}"
                                 for app in OTHER_APPS]


def item(path, value):
    node, prop = path.rsplit("/", 1)
    package, rest = node.split("/", 1)
    return (f'<item oor:path="/{package}/{rest}"><prop oor:name="{prop}" oor:op="fuse">'
            f'<value>{value}</value></prop></item>')


def write_profile_settings(profile, items):
    """registrymodifications.xcu as the office writes it for changed settings."""
    user = os.path.join(profile, "user")
    os.makedirs(user, exist_ok=True)
    with open(os.path.join(user, "registrymodifications.xcu"), "w", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/'
                     'registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                     'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n')
        handle.write("\n".join(items))
        handle.write("\n</oor:items>\n")


def connect(pipe, timeout=90):
    import uno
    local = uno.getComponentContext()
    deadline = time.time() + timeout
    time.sleep(6)  # calls made before startup settles get disposed
    while True:
        try:
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:  # NoConnectException until soffice listens
            if time.time() > deadline:
                raise
            time.sleep(1)


def read_config(ctx, path):
    from com.sun.star.beans import PropertyValue
    node, key = path.rsplit("/", 1)
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = PropertyValue()
    arg.Name, arg.Value = "nodepath", "/" + node
    return provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
                                                (arg,)).getByName(key)


def run_office(program, profile, env, paths):
    """Start a headless office on the profile and return {path: value}."""
    pipe = f"hstunit{os.getpid()}{len(os.listdir(os.path.dirname(profile)))}"
    proc = subprocess.Popen([os.path.join(program, "soffice"), "--headless", "--norestore", "--nologo",
                             f"-env:UserInstallation=file://{profile}", f"--accept=pipe,name={pipe};urp;"], env=env)
    try:
        ctx = connect(pipe)
        values = {}
        for path in paths + ["org.openoffice.Setup/L10N/ooSetupSystemLocale"]:
            try:
                values[path] = read_config(ctx, path)
            except Exception as error:  # report missing keys as values that fail the check
                values[path] = f"ERROR {error}"
        try:
            ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).terminate()
        except Exception:  # the bridge drops while the office exits
            pass
        proc.wait(timeout=30)
        return values
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/measure-unit-cm"))
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    program = os.path.join(os.path.abspath(args.instdir), "program")
    if os.path.exists(os.path.join(program, "uno.py")) and program not in sys.path:
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    import uno  # noqa: F401  (needs the build's program directory on sys.path)

    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    results, failed = {}, 0
    for locale, (lang, metric) in LOCALES.items():
        env = {k: v for k, v in os.environ.items() if k not in ("URE_BOOTSTRAP", "LC_ALL", "LANGUAGE")}
        env["LANG"] = lang
        paths = read_paths(metric)
        locale_item = item("org.openoffice.Setup/L10N/ooSetupSystemLocale", locale)
        for case, expected in (("default", CENTIMETRE), ("user chose inch", INCH)):
            profile = os.path.join(out, f"profile-{locale}-{case.replace(' ', '-')}")
            items = [locale_item] + ([item(path, INCH) for path in paths] if expected == INCH else [])
            # A fresh profile makes soffice restart once while it is created; initialise it first.
            for _ in range(3):
                write_profile_settings(profile, items)
                warm = subprocess.run([os.path.join(program, "soffice.bin"), "--headless", "--norestore",
                                       "--terminate_after_init", f"-env:UserInstallation=file://{profile}"],
                                      env=env, timeout=120, check=False)
                if warm.returncode == 0:
                    break
            values = run_office(program, profile, env, paths)
            bad = {path: values[path] for path in paths if values[path] != expected}
            if values["org.openoffice.Setup/L10N/ooSetupSystemLocale"] != locale:
                bad["locale"] = values["org.openoffice.Setup/L10N/ooSetupSystemLocale"]
            failed += bool(bad)
            name = f"{locale} {case}"
            results[name] = {"status": "FAIL" if bad else "PASS", "expected": expected, "values": values,
                             "wrong": bad}
            print(f"{'FAIL' if bad else 'PASS'}  {name}: {json.dumps(bad or values, ensure_ascii=False)[:300]}")
    with open(os.path.join(out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": args.instdir, "failed": failed, "checks": results}, handle, indent=2,
                  ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
