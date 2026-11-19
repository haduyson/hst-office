# SPDX-License-Identifier: AGPL-3.0-only
"""Download the STEM corpus listed in a manifest, one directory per file, and check sha256.

The files are never opened here; Google Drive's "large file" confirmation page is followed.
"""
import hashlib
import http.cookiejar
import json
import os
import re
import sys
import urllib.request


def fetch(opener, url):
    data = opener.open(url, timeout=60).read()
    if data[:15].lower().startswith(b'<!doctype html') or data[:5] == b'<html':
        page = data.decode('utf8', 'ignore')
        action = re.search(r'action="([^"]+)"', page)
        if action:
            form = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', page))
            query = '&'.join('%s=%s' % kv for kv in form.items())
            data = opener.open(action.group(1).replace('&amp;', '&') + '?' + query, timeout=120).read()
    return data


def main(manifest, base):
    docs = json.load(open(manifest))['documents']
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
    for d in docs:
        folder = os.path.join(base, d['id'])
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, d['file'])
        if os.path.exists(path) and hashlib.sha256(open(path, 'rb').read()).hexdigest() == d['sha256']:
            print(d['id'], 'cached')
            continue
        try:
            data = fetch(opener, d['url'])
        except OSError as e:
            print(d['id'], 'ERR', e)
            continue
        open(path, 'wb').write(data)
        ok = hashlib.sha256(data).hexdigest() == d['sha256']
        print(d['id'], 'OK' if ok else 'SHA MISMATCH', len(data))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
