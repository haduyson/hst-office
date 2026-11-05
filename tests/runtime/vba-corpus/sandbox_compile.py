# SPDX-License-Identifier: AGPL-3.0-only
"""Inside the disposable container: which code does the Basic compiler refuse? Nothing from the file runs: a macro is only compiled.

argv: jobs.json. The file is loaded with macros off; each module, then each of its procedures, then each line of a failing procedure
is compiled alone in a hidden document. One JSON line per failing line or procedure. Options are dropped: other modules are not there.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, "/opt/hst/program")
os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:/opt/hst/program/fundamentalrc"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandbox_office import Office, call_with_timeout, pv  # noqa: E402

CORPUS = os.environ.get("HST_CORPUS", "/corpus")
HEAD = re.compile(r"^[ \t]*(?:(?:Public|Private|Friend|Static)[ \t]+)*(Sub|Function|Property[ \t]+(?:Get|Let|Set))[ \t]+[^\s(]+", re.I)
END = re.compile(r"^[ \t]*End[ \t]+(Sub|Function|Property)\b", re.I)
OPTION = re.compile(r"(?im)^\s*(Option\s+(Explicit|Private\s+Module|Compare\s+\w+)|Attribute\s+.*)\s*$")


class Compiler:
    def __init__(self, office):
        self.office = office
        self.count = 0
        self.fresh()

    def fresh(self):
        self.doc = self.office.desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, (pv("Hidden", True), pv("MacroExecutionMode", 3)))
        libs = self.doc.BasicLibraries
        libs.createLibrary("HstC") if not libs.hasByName("HstC") else None
        libs.VBACompatibilityMode = True
        libs.ProjectName = "HstC"
        self.library = libs.getByName("HstC")

    def message(self):
        """The compiler's text, when it was shown."""
        seen = self.office.watcher.take()
        return [t for d in seen for t in d["text"][1:2]][:1]

    def ok(self, code):
        """True when code compiles (its check function returns), False when not, None when the office went away."""
        self.count += 1
        name = f"M{self.count}"
        source = 'Option VBASupport 1\nFunction HstCheck()\n  HstCheck = "c"\nEnd Function\n' + code + "\n"

        self.office.watcher.take()

        def compile_once():
            self.library.insertByName(name, source)
            value = self.doc.getScriptProvider().getScript(
                f"vnd.sun.star.script:HstC.{name}.HstCheck?language=Basic&location=document").invoke((), (), ())[0]
            self.library.removeByName(name)
            return value == "c"

        state, value = call_with_timeout(compile_once, 20)
        if state != "done":
            self.office.restart()
            self.fresh()
            return None
        return value


def procedures(source):
    lines, current, out = source.split("\n"), None, []
    for number, line in enumerate(lines, 1):
        if current is None and HEAD.match(line):
            current = [number, []]
        if current is not None:
            current[1].append(line)
            if END.match(line):
                out.append(current)
                current = None
    return out


def logical_lines(body):
    """(line number within body, text) with continuation lines joined."""
    out, index = [], 0
    while index < len(body):
        first, text = index, body[index].rstrip()
        while text.endswith(" _") and index + 1 < len(body):
            index += 1
            text = text[:-1] + " " + body[index].strip()
        out.append((first, text))
        index += 1
    return out


def wrap(text):
    """Code that compiles alone when this one line is right."""
    plain = re.sub(r"\s'[^\"]*$", "", text).strip()
    low = plain.lower()
    if re.match(r"if\b.*\bthen$", low):
        return f"{plain}\nEnd If"
    if low.startswith("elseif "):
        return f"If 1 Then\n{plain}\nEnd If"
    if low == "else" or low.startswith(("end if", "end select", "end with", "next", "loop", "wend")) or END.match(plain):
        return None
    if re.match(r"for\b", low):
        return f"{plain}\nNext"
    if re.match(r"do\b", low):
        return f"{plain}\nLoop"
    if re.match(r"while\b", low):
        return f"{plain}\nWend"
    if re.match(r"with\b", low):
        return f"{plain}\nEnd With"
    if low.startswith("select "):
        return f"{plain}\nEnd Select"
    if low.startswith("case "):
        return f"Select Case 1\n{plain}\nEnd Select"
    if plain.startswith(".") or re.search(r"(?i)\bcall\s+\.|\bexit\s+(do|for)\b|\b(goto|resume)\b|^\w+:$|^#|[(\s=,]\.\w", plain):
        return None  # needs the With, loop or label around it
    return plain


def blame(compiler, emit_row, module, source):
    """Reports the procedures that fail and, where it can, the single line."""
    for first, body in procedures(source):
        if compiler.ok("\n".join(body)) is not False:
            continue
        lines = logical_lines(body)
        kind = HEAD.match(lines[0][1]).group(1).split()
        closing = "End " + kind[0]
        if compiler.ok(lines[0][1] + "\n" + closing) is False:
            emit_row(dict(module=module, line=first, text=lines[0][1].strip()[:240], message=compiler.message()))
            continue
        found = False
        for offset, text in lines[1:-1]:
            code = wrap(text) if text.strip() else None
            if code and compiler.ok(f"Sub HstL()\n{code}\nEnd Sub") is False:
                emit_row(dict(module=module, line=first + offset, text=text.strip()[:240], message=compiler.message()))
                found = True
        if not found:
            emit_row(dict(module=module, line=first, text=lines[0][1].strip()[:120], whole_procedure=len(body)))


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        jobs = json.load(handle)
    office = Office()
    office.start()
    compiler = Compiler(office)
    import uno
    for job in jobs:
        out = dict(file=job["file"], event="compile", failures=[])
        started = time.time()
        state, doc = call_with_timeout(lambda: office.desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(os.path.join(CORPUS, job["file"])), "_blank", 0, (pv("MacroExecutionMode", 0), pv("ReadOnly", True))), 60)
        if state != "done" or doc is None:
            out["status"] = "load-" + state
            print("@@R " + json.dumps(out), flush=True)
            office.restart()
            compiler.fresh()
            continue

        def sources():
            libs = doc.BasicLibraries
            result = []
            for name in libs.getElementNames():
                libs.loadLibrary(name)
                library = libs.getByName(name)
                result += [(module, library.getByName(module)) for module in library.getElementNames()]
            return result

        state, modules = call_with_timeout(sources, 30)
        for module, source in (modules or []) if state == "done" else []:
            clean = OPTION.sub("", source)
            if compiler.ok(clean) is False:
                blame(compiler, out["failures"].append, module, clean)
                out.setdefault("modules_failed", []).append(module)
            if time.time() - started > 120:
                out["truncated"] = True
                break
        call_with_timeout(lambda: doc.close(True), 20)
        out["modules"] = len(modules or [])
        print("@@R " + json.dumps(out, ensure_ascii=False), flush=True)
    office.shutdown()


if __name__ == "__main__":
    main()
