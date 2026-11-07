# SPDX-License-Identifier: AGPL-3.0-only
"""Deterministic icon archives and directory sync for build-hst-icon-theme.py."""
import io
import zipfile


def archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def sync(directory, files, check=False):
    expected = set(files)
    existing = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    errors = []
    for name in sorted(existing - expected):
        if check:
            errors.append(f"unexpected: {directory / name}")
        else:
            (directory / name).unlink()
    for name, data in files.items():
        path = directory / name
        if path.is_file() and path.read_bytes() == data:
            continue
        if check:
            errors.append(f"missing or stale: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
    if errors:
        raise ValueError("\n".join(errors))
