#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Mail merge engine still held by a UNO client when the office quits: the office must exit cleanly (Linux, headless).

com.sun.star.text.MailMerge loads its DocumentURL as a hidden document and closes it when the engine is destroyed.
A client that still holds the engine at Desktop.terminate() (HST's Trộn thư merging to a new document over UNO) had
it destroyed when the URP bridge went away at shutdown, after Writer's module was gone: SIGSEGV in SwDoc::~SwDoc
(lcl_DelFormatIndices found no pool default), 1.0.2. Here: a CSV data source, a letter with two database fields, a
merge to one file, then terminate with the engine alive. A second run releases the engine first (the control).
Usage: <office python> check-mail-merge-engine-at-quit.py --instdir DIR --out DIR. Exit 1 on a failure.
"""
import argparse, os, shutil, socket, subprocess, sys, time  # noqa: E401

failures = []


def check(ok, text):
    print(("PASS  " if ok else "FAIL  ") + text, flush=True)
    failures.extend([] if ok else [text])


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run(program, work, keep_engine):
    import uno
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        item = PropertyValue()
        item.Name, item.Value = name, value
        return item

    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(os.path.join(work, "data"))
    os.makedirs(os.path.join(work, "out"))
    with open(os.path.join(work, "data", "list.csv"), "w", encoding="utf-8") as handle:
        handle.write("Name,Title\nAn,Boss\nBinh,\nChi,Clerk\n")
    soffice = os.path.join(program, "soffice.bin")
    profile = uno.systemPathToFileUrl(os.path.join(work, "profile"))
    subprocess.run([soffice, "--headless", "--terminate_after_init", "-env:UserInstallation=" + profile], timeout=300)
    port = free_port()
    log = open(os.path.join(work, "office.log"), "w")

    def start():
        return subprocess.Popen([soffice, "--headless", "--norestore", "--nologo", "-env:UserInstallation=" + profile,
                                 f"--accept=socket,host=127.0.0.1,port={port};urp;"], stderr=log)
    proc = start()
    try:
        if proc.wait(15) == 81:  # the first start of a new profile asks for a restart
            proc = start()
    except subprocess.TimeoutExpired:
        pass
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    ctx = None
    for _ in range(90):
        try:
            ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
            break
        except Exception:  # noqa: BLE001 - still starting
            time.sleep(1)
    if ctx is None:
        proc.kill()
        return None
    smgr = ctx.ServiceManager
    databases = smgr.createInstanceWithContext("com.sun.star.sdb.DatabaseContext", ctx)
    source = databases.createInstance()
    source.URL = "sdbc:flat:" + uno.systemPathToFileUrl(os.path.join(work, "data"))
    source.Info = (prop("Extension", "csv"), prop("HeaderLine", True), prop("FieldDelimiter", ","),
                   prop("StringDelimiter", '"'), prop("CharSet", "UTF-8"))
    source.DatabaseDocument.storeAsURL(uno.systemPathToFileUrl(os.path.join(work, "list.odb")), ())
    name = "HSTMailMergeQuitCheck"
    if databases.hasByName(name):
        databases.revokeObject(name)
    databases.registerObject(name, source)
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, (prop("Hidden", True),))
    text = doc.Text
    for column in ("Name", "Title"):
        master = doc.createInstance("com.sun.star.text.FieldMaster.Database")
        master.DataBaseName, master.DataTableName, master.DataColumnName = name, "list", column
        field = doc.createInstance("com.sun.star.text.TextField.Database")
        field.attachTextFieldMaster(master)
        text.insertString(text.getEnd(), column + ": ", False)
        text.insertTextContent(text.getEnd(), field, False)
        text.insertControlCharacter(text.getEnd(), 0, False)
    letter = os.path.join(work, "letter.odt")
    doc.storeToURL(uno.systemPathToFileUrl(letter), (prop("FilterName", "writer8"),))
    doc.close(True)
    engine = smgr.createInstanceWithContext("com.sun.star.text.MailMerge", ctx)
    engine.DataSourceName, engine.Command, engine.CommandType = name, "list", 0
    engine.DocumentURL = uno.systemPathToFileUrl(letter)
    engine.OutputType, engine.SaveAsSingleFile, engine.SaveFilter = 2, True, "writer8"  # FILE
    engine.OutputURL, engine.FileNamePrefix = uno.systemPathToFileUrl(os.path.join(work, "out")), "merged"
    engine.execute(())
    merged = os.listdir(os.path.join(work, "out"))
    if not keep_engine:
        del engine
        time.sleep(2)
    try:
        desktop.terminate()
    except Exception:  # noqa: BLE001 - the bridge may go away while the office quits
        pass
    try:
        code = proc.wait(60)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = "hung"
    return merged, code


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    program = os.path.join(os.path.abspath(args.instdir), "program")
    sys.path.insert(0, program)
    out = os.path.abspath(args.out)
    for keep_engine in (False, True):
        label = "engine still held at quit" if keep_engine else "engine released before quit"
        result = run(program, os.path.join(out, "held" if keep_engine else "released"), keep_engine)
        if result is None:
            check(False, f"{label}: the office started")
            continue
        merged, code = result
        check(len(merged) == 1, f"{label}: one merged file {merged}")
        check(code == 0, f"{label}: the office exits cleanly (exit code {code})")
    print("RESULT", "FAIL" if failures else "PASS", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
