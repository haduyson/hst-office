# SPDX-License-Identifier: AGPL-3.0-only
"""Rebind only the internal module in a private copy of an NSS module store."""
import re

from .usb_token_errors import SetupError
from .usb_token_nss import _value, parse

PAIRS = dict(zip("\"'<{[(", "\"'>}])"))
SPACE = " \t\n\r\v\f"
BINDINGS = {'configdir', 'certprefix', 'keyprefix', 'secmod'}
POLICY = {'flags', 'manufacturerid', 'librarydescription', 'cryptotokendescription',
          'dbtokendescription', 'cryptoslotdescription', 'dbslotdescription',
          'fipsslotdescription', 'fipstokendescription', 'minpwlen'}
UPDATES = {'updatedir', 'updatecertprefix', 'updatekeyprefix', 'updateid', 'updatetokendescription'}
REFUSAL = ("Tham số mô-đun NSS nội bộ chưa hỗ trợ chuyển kho an toàn; chưa thay đổi kho chứng thư. "
           "Hãy chọn một kho NSS SQL mới trong Bảo mật → Chứng chỉ… rồi thử lại.")


def quote(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def arguments(text):
    """NSS ArgFetchValue grammar, including all six delimiters and escapes.

    Yield decoded values and their source spans. Reject ambiguous/malformed input
    rather than guessing at NSS's permissive handling of an incomplete argument.
    """
    index = 0
    while index < len(text):
        if text[index] in SPACE:
            index += 1
            continue
        match = re.match(r'([^=\s]+)=', text[index:])
        if not match:
            raise SetupError(REFUSAL)
        key = match[1].lower()
        index += match.end()
        start = index
        end = PAIRS.get(text[index:index + 1])
        if end:
            index += 1
        value = []
        while index < len(text):
            char = text[index]
            if (end and char == end) or (not end and char in SPACE):
                break
            if char == '\\':
                index += 1
                if index == len(text):
                    raise SetupError(REFUSAL)
            value.append(text[index])
            index += 1
        if end:
            if index == len(text):
                raise SetupError(REFUSAL)
            index += 1
            if index < len(text) and text[index] not in SPACE:
                raise SetupError(REFUSAL)
        yield key, ''.join(value), start, index


def parameters(raw, target):
    text = _value(raw)
    replacements, seen = [], set()
    values = dict(configdir='sql:' + str(target), certprefix='', keyprefix='', secmod='secmod.db')
    for key, value, start, end in arguments(text):
        if key in seen or key not in BINDINGS | POLICY | UPDATES or (key in UPDATES and value):
            # In particular, tokens/updateDir can bind additional old databases.
            raise SetupError(REFUSAL)
        seen.add(key)
        if key == 'flags' and any(flag.lower() not in ('', 'passwordrequired', 'optimizespace', 'forceopen')
                                  for flag in value.split(',')):
            # A read-only/noCertDB policy cannot initialize a new writable store.
            raise SetupError(REFUSAL)
        if key in BINDINGS:
            replacements.append((start, end, quote(values[key])))
    for start, end, value in reversed(replacements):
        text = text[:start] + value + text[end:]
    for key in sorted(BINDINGS - seen):
        text += ' ' + key + '=' + quote(values[key])
    # Quoting makes the explicit binding and preserved policy authoritative.
    line = 'parameters=' + quote(text)
    if len(line.encode('utf-8', 'surrogateescape')) >= 2047 or '\0' in line:
        raise SetupError(REFUSAL)
    return line


def relocate(text, target):
    """Preserve all other records, comments, NSS flags and slot policy verbatim."""
    parse(text)
    blocks = text.split('\n\n')
    for index, block in enumerate(blocks):
        lines = block.split('\n')
        fields = {}
        for number, line in enumerate(lines):
            if line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            fields.setdefault(key.lower(), []).append((number, value))
        if 'library' not in fields:
            continue
        internal = not _value(fields['library'][0][1])
        if not internal:
            # Do not rewrite a vendor record masquerading as an internal module.
            if any('internal' in value for _, value in fields.get('nss', [])):
                raise SetupError(REFUSAL)
            continue
        params = fields.get('parameters', [])
        if len(params) > 1:
            raise SetupError(REFUSAL)
        if params:
            number, raw = params[0]
            lines[number] = parameters(raw, target)
        else:
            lines.append(parameters('', target))
        blocks[index] = '\n'.join(lines)
    return '\n\n'.join(blocks)
