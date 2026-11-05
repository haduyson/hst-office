# SPDX-License-Identifier: AGPL-3.0-only
"""Second run of a failing procedure with every module instrumented, to name the module and line of the error.

Handlers go on existing lines (joined with ":"), so line numbers stay those of the file's own code. Procedures with their own
On Error are left alone; a run with handlers is only for diagnosis, the pass/fail result comes from the first, clean run.
"""
import re

from sandbox_common import HARNESS, WRAPPER, load, wrap_module
from sandbox_office import call_with_timeout

HEAD = re.compile(r"^[ \t]*(?:(?:Public|Private|Friend|Static)[ \t]+)*(Sub|Function|Property[ \t]+(?:Get|Let|Set))[ \t]+[^\s(]+[^\n]*$", re.I)
END = re.compile(r"^[ \t]*End[ \t]+(Sub|Function|Property)[ \t]*(?:'.*)?$", re.I)
CONTINUED = re.compile(r"[ \t]_[ \t]*$")
TRAILING_COMMENT = re.compile(r"'[^\"]*$")


def instrument(source, module, harness):
    lines = source.split("\n")
    out, index, count = [], 0, 0
    while index < len(lines):
        line = lines[index].rstrip("\r")
        head = HEAD.match(line)
        if not head:
            out.append(line)
            index += 1
            continue
        kind = head.group(1).split()[0]
        close = index
        while close < len(lines) and not END.match(lines[close].rstrip("\r")):
            close += 1
        body = lines[index:close + 1]
        if close >= len(lines) or any(re.match(r"^\s*On\s+Error\b", b, re.I) for b in body):
            out.extend(b.rstrip("\r") for b in body)
            index = close + 1
            continue
        count += 1
        first = index
        while first < close and CONTINUED.search(lines[first].rstrip("\r")):
            first += 1
        label = f"HstE{count}"
        for number in range(index, close + 1):
            text = lines[number].rstrip("\r")
            if number == first:
                text = TRAILING_COMMENT.sub("", text).rstrip() + f" : On Error GoTo {label}"
            elif number == close:
                text = (f'Exit {kind} : {label}: {harness}.HstNote "{module}", Erl, Err.Number, Err.Description : '
                        f"Err.Raise Err.Number : {text.strip()}")
            out.append(text)
        index = close + 1
    return "\n".join(out)


NOTE = '''
Public HstTrace As String
Public Sub HstNote(m As String, l As Long, n As Long, d As String)
  If Len(HstTrace) = 0 Then HstTrace = m & "|" & l & "|" & n & "|" & d
End Sub
Public Function HstGetTrace()
  HstGetTrace = HstTrace
End Function
'''


def trace_failure(office, path, target, timeout, shown_name):
    """Where the error of a failing procedure happens: {module, line, number, text, source}."""
    state, doc = call_with_timeout(lambda: load(office, path, shown_name), 60)
    if state != "done" or doc is None:
        return None

    def invoke():
        library = doc.BasicLibraries.getByName(target["library"])
        sources = {}
        for module in library.getElementNames():
            if module != HARNESS:
                sources[module] = library.getByName(module)
                library.replaceByName(module, instrument(sources[module], module, HARNESS))
        call = f"hstR = {target['module']}.{target['proc']}()" if target.get("kind") == "Function" else f"{target['module']}.{target['proc']}"
        wrap_module(library, WRAPPER.format(call=call) + NOTE)
        provider = doc.getScriptProvider()
        uri = f"vnd.sun.star.script:{target['library']}.{HARNESS}.%s?language=Basic&location=document"
        provider.getScript(uri % "HstCall").invoke((), (), ())
        note = provider.getScript(uri % "HstGetTrace").invoke((), (), ())[0]
        parts = (note or "").split("|", 3)
        if len(parts) < 4:
            return None
        lines = sources.get(parts[0], "").split("\n")
        number = int(parts[1])
        return dict(module=parts[0], line=number, source=lines[number - 1].strip()[:200] if 0 < number <= len(lines) else "")

    state, value = call_with_timeout(invoke, timeout)
    office.watcher.take()
    return value if state == "done" else None
