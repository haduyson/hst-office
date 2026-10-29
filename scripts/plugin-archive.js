// Read .plugin (ZIP) archives through Python's zipfile so Node checks need no
// extra dependency. Returns entry names and lets callers read text entries.
import { execFileSync } from 'node:child_process';

const PY_LIST = `import json,sys,zipfile
z=zipfile.ZipFile(sys.argv[1])
print(json.dumps([{"name":i.filename,"mode":(i.external_attr>>16)&0o777777,"time":list(i.date_time)} for i in z.infolist()]))`;

const PY_READ = `import sys,zipfile
sys.stdout.buffer.write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]))`;

export function listEntries(file) {
  return JSON.parse(execFileSync('python3', ['-c', PY_LIST, file], { encoding: 'utf8' }));
}

export function readEntry(file, name, encoding = 'utf8') {
  return execFileSync('python3', ['-c', PY_READ, file, name], { encoding, maxBuffer: 64 * 1024 * 1024 });
}
