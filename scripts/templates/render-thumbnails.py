#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Developer tool: real thumbnails of the templates, rendered by a built office. The PNG files are committed.

Usage (as the build user, under the shared build lock):
    render-thumbnails.py catalog --soffice .../instdir/program/soffice --templates dist/templates --out assets/templates/thumbnails --work DIR
    render-thumbnails.py presnt --office-python-path .../instdir/program --presnt .../share/template/common/presnt --out assets/templates/presnt-thumbnails --port 2193 --work DIR
`catalog`: first page of every template of the manifest, through PDF. `presnt`: first slide of each presentation background,
with Vietnamese text in its empty placeholders; the template itself is not saved.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

WIDTH = 256
TITLE, SUBTITLE, BODY = "Tiêu đề bài trình bày", "Tên đơn vị, ngày trình bày", "Nội dung chính của trang\nÝ thứ hai của trang\nÝ thứ ba của trang"


def catalog(args):
    manifest = json.loads((args.templates / "manifest.json").read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    pdf = args.work / "pdf"
    pdf.mkdir(parents=True, exist_ok=True)
    files = [str(args.templates / e["output"]) for e in manifest["templates"]]
    env = {**os.environ, "SAL_USE_VCLPLUGIN": "svp", "HOME": str(args.work)}
    for start in range(0, len(files), 20):
        subprocess.run([args.soffice, "--headless", f"-env:UserInstallation=file://{args.work}/profile", "--convert-to", "pdf", "--outdir", str(pdf), *files[start:start + 20]],
                       env=env, check=True, timeout=600, stdout=subprocess.DEVNULL)
    for entry in manifest["templates"]:
        stem = args.work / entry["id"]
        subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-scale-to", str(WIDTH), "-png", str(pdf / (Path(entry["output"]).stem + ".pdf")), str(stem)], check=True, timeout=120)
        shutil.copyfile(f"{stem}.png", args.out / (entry["id"] + ".png"))


def _fill(slide):
    """Vietnamese text in the empty placeholders of a slide, as a person would type it."""
    for index in range(slide.getCount()):
        shape = slide.getByIndex(index)
        kind = shape.getShapeType()
        if not (shape.supportsService("com.sun.star.presentation.Shape") and shape.IsEmptyPresentationObject):
            continue
        if "Title" in kind and "Subtitle" not in kind:
            shape.setString(TITLE)
        elif "Subtitle" in kind:
            shape.setString(SUBTITLE)
        elif "Outliner" in kind:
            shape.setString(BODY)


def _connect(uno, port):
    resolver = uno.getComponentContext().ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", uno.getComponentContext())
    for _ in range(120):
        try:
            return resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
        except Exception:  # noqa: BLE001 - the office is still starting
            time.sleep(1)
    raise TimeoutError("no office on port %d" % port)


def presnt(args):
    sys.path.insert(0, args.office_python_path)
    os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(args.office_python_path, "fundamentalrc")
    import uno
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        item = PropertyValue()
        item.Name, item.Value = name, value
        return item
    env = {**os.environ, "SAL_USE_VCLPLUGIN": "svp", "HOME": str(args.work)}
    office = subprocess.Popen([os.path.join(args.office_python_path, "soffice"), "--headless", "--norestore", "--nologo", f"-env:UserInstallation=file://{args.work}/profile",
                               f"--accept=socket,host=127.0.0.1,port={args.port};urp;"], env=env)
    try:
        ctx = _connect(uno, args.port)
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        args.out.mkdir(parents=True, exist_ok=True)
        for path in sorted(args.presnt.glob("*.otp")):
            doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(path)), "_blank", 0, (prop("Hidden", True), prop("AsTemplate", True)))
            slide = doc.getDrawPages().getByIndex(0)
            _fill(slide)
            exporter = smgr.createInstanceWithContext("com.sun.star.drawing.GraphicExportFilter", ctx)
            exporter.setSourceDocument(slide)
            data = uno.Any("[]com.sun.star.beans.PropertyValue", (prop("PixelWidth", WIDTH), prop("PixelHeight", WIDTH * slide.Height // slide.Width)))
            target = args.work / (path.stem + ".png")
            uno.invoke(exporter, "filter", ((prop("MediaType", "image/png"), prop("URL", uno.systemPathToFileUrl(str(target))), prop("FilterData", data)),))
            shutil.copyfile(target, args.out / (path.stem + ".png"))
            doc.close(True)
        try:
            desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes down with the office
            pass
        office.wait(timeout=60)
    finally:
        if office.poll() is None:
            office.terminate()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("catalog", "presnt"))
    parser.add_argument("--soffice")
    parser.add_argument("--templates", type=Path)
    parser.add_argument("--office-python-path")
    parser.add_argument("--presnt", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2193)
    args = parser.parse_args()
    (catalog if args.mode == "catalog" else presnt)(args)


if __name__ == "__main__":
    main()
