"""Safely unpack a zip (untrusted input) and discover pages and a name in a source.

`safe_extract` validates every entry before writing anything, streams entries in chunks
while counting real bytes, never takes permissions from the archive and, on any failure,
leaves `dest` empty (removing `dest` itself when it did not exist before).

Rejected: absolute, `..`, backslash and drive-letter names, NUL bytes, symlinks and other
special file types, duplicate or conflicting paths, encrypted entries, more than
MAX_ENTRIES entries, more than MAX_UNPACKED_BYTES declared or actually read, and an entry
that yields more bytes than it declared.
"""
from __future__ import annotations

import codecs
import os
import re
import shutil
import stat
import sys
import zipfile
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

MAX_UNPACKED_BYTES = 200 * 1024 * 1024
MAX_ENTRIES = 20000
NAME_TXT_MAX_BYTES = 1024
_CHUNK = 64 * 1024
_DRIVE = re.compile(r"^[A-Za-z]:")

USAGE = "usage: unpack.py extract <zip> <dest> | pages <dir> | name <dir-or-zip>"


class UnpackError(Exception):
    """The archive or source cannot be used safely; nothing is left behind."""


def _entry_parts(name: str) -> Tuple[str, ...]:
    if "\x00" in name:
        raise UnpackError("entry %r: NUL byte in name" % name)
    if "\\" in name:
        raise UnpackError("entry %r: backslash in name" % name)
    if name.startswith("/"):
        raise UnpackError("entry %r: absolute path" % name)
    parts: List[str] = []
    for part in name.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise UnpackError("entry %r: path escapes the destination" % name)
        if _DRIVE.match(part):
            raise UnpackError("entry %r: drive-letter path" % name)
        parts.append(part)
    if not parts:
        raise UnpackError("entry %r: empty path" % name)
    return tuple(parts)


class _Entry:
    def __init__(self, info: zipfile.ZipInfo, parts: Tuple[str, ...], is_dir: bool) -> None:
        self.info = info
        self.parts = parts
        self.is_dir = is_dir


def _plan(infos: List[zipfile.ZipInfo], dest: Path) -> List[_Entry]:
    """Validate every entry; returns the entries to create. Writes nothing."""
    if len(infos) > MAX_ENTRIES:
        raise UnpackError("archive has %d entries, more than MAX_ENTRIES (%d)" % (len(infos), MAX_ENTRIES))
    root = dest.resolve()
    entries: List[_Entry] = []
    seen: Dict[Tuple[str, ...], str] = {}  # case-folded path -> name (macOS folds case)
    files: Set[Tuple[str, ...]] = set()
    dirs: Set[Tuple[str, ...]] = set()
    declared = 0
    for info in infos:
        name = info.orig_filename  # ZipInfo.filename is cut at the first NUL
        parts = _entry_parts(name)
        if info.flag_bits & 0x1:
            raise UnpackError("entry %r: encrypted" % name)
        kind = stat.S_IFMT(info.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise UnpackError("entry %r: symlink or special file type (mode %o)" % (name, kind))
        is_dir = name.endswith("/") or kind == stat.S_IFDIR
        key = tuple(part.casefold() for part in parts)
        if key in seen:
            raise UnpackError("entry %r: duplicate of %r" % (name, seen[key]))
        seen[key] = name
        for depth in range(1, len(key)):
            if key[:depth] in files:
                raise UnpackError("entry %r: parent path is a file" % name)
            dirs.add(key[:depth])
        if is_dir:
            if key in files:
                raise UnpackError("entry %r: conflicts with a file" % name)
            dirs.add(key)
        else:
            if key in dirs:
                raise UnpackError("entry %r: conflicts with a directory" % name)
            files.add(key)
            declared += info.file_size
            if declared > MAX_UNPACKED_BYTES:
                raise UnpackError(
                    "entry %r: declared sizes exceed MAX_UNPACKED_BYTES (%d)" % (name, MAX_UNPACKED_BYTES)
                )
        target = root.joinpath(*parts).resolve()
        if root not in target.parents:
            raise UnpackError("entry %r: resolves outside the destination" % name)
        entries.append(_Entry(info, parts, is_dir))
    return entries


def _make_dirs(dest: Path, parts: Tuple[str, ...]) -> None:
    current = dest
    for part in parts:
        current = current / part
        if not current.is_dir():
            current.mkdir()
            os.chmod(current, 0o755)


def _write_entry(zf: zipfile.ZipFile, entry: _Entry, dest: Path, total: int) -> int:
    """Stream one file; returns the cumulative real byte count."""
    info = entry.info
    name = info.filename
    _make_dirs(dest, entry.parts[:-1])
    path = dest.joinpath(*entry.parts)
    written = 0
    with zf.open(info) as source, open(path, "xb") as out:
        while True:
            chunk = source.read(_CHUNK)
            if not chunk:
                break
            written += len(chunk)
            total += len(chunk)
            if written > info.file_size:
                raise UnpackError("entry %r: data exceeds its declared size (%d)" % (name, info.file_size))
            if total > MAX_UNPACKED_BYTES:
                raise UnpackError("entry %r: unpacked data exceeds MAX_UNPACKED_BYTES (%d)" % (name, MAX_UNPACKED_BYTES))
            out.write(chunk)
    os.chmod(path, 0o644)
    return total


def _empty(directory: Path) -> None:
    for child in directory.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def safe_extract(zip_path: Path, dest: Path) -> List[Path]:
    zip_path, dest = Path(zip_path), Path(dest)
    dest_existed = dest.exists() or dest.is_symlink()
    if dest.is_symlink() or (dest_existed and not dest.is_dir()):
        raise UnpackError("destination is not a directory: %s" % dest)
    if dest_existed and any(dest.iterdir()):
        raise UnpackError("destination is not empty: %s" % dest)
    if not dest_existed and not dest.parent.is_dir():
        raise UnpackError("destination parent does not exist: %s" % dest.parent)
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise UnpackError("%s: not a valid zip (%s)" % (zip_path, exc)) from exc
    except OSError as exc:
        raise UnpackError("%s: cannot read archive (%s)" % (zip_path, exc)) from exc
    with zf:
        entries = _plan(zf.infolist(), dest)  # raises before dest is touched
        if not dest_existed:
            dest.mkdir()
            os.chmod(dest, 0o755)
        extracted: List[Path] = []
        total = 0
        current = ""
        try:
            for entry in entries:
                current = entry.info.filename
                if entry.is_dir:
                    _make_dirs(dest, entry.parts)
                else:
                    total = _write_entry(zf, entry, dest, total)
                    extracted.append(dest.joinpath(*entry.parts))
        except Exception as exc:
            if dest_existed:
                _empty(dest)
            else:
                shutil.rmtree(dest)
            if isinstance(exc, UnpackError):
                raise
            if isinstance(exc, (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, OSError)):
                raise UnpackError("entry %r: %s" % (current, exc)) from exc
            raise
    return sorted(extracted)


def _skip_dir(name: str) -> bool:
    return name.startswith(".") or name == "__MACOSX" or name.lower().endswith("_files")


def find_pages(source_dir: Path) -> List[Path]:
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        raise UnpackError("not a directory: %s" % source_dir)
    found: List[Tuple[str, Path]] = []
    for current, dirnames, filenames in os.walk(source_dir, followlinks=False):
        dirnames[:] = [d for d in dirnames if not _skip_dir(d) and not os.path.islink(os.path.join(current, d))]
        for filename in filenames:
            path = Path(current) / filename
            if filename.startswith(".") or path.is_symlink():
                continue
            if filename.lower().endswith((".html", ".htm")):
                found.append((path.relative_to(source_dir).as_posix(), path))
    return [path for _, path in sorted(found)]


def _decode_name(data: bytes, label: str) -> Optional[str]:
    """First non-empty line of a possibly 1 KB-truncated utf-8 name.txt, else None."""
    truncated = len(data) > NAME_TXT_MAX_BYTES
    try:
        text = codecs.getincrementaldecoder("utf-8")().decode(data[:NAME_TXT_MAX_BYTES], final=not truncated)
    except UnicodeDecodeError as exc:
        raise UnpackError("%s: name.txt is not valid utf-8 (%s)" % (label, exc)) from exc
    lines = text.splitlines()
    first = lines[0].strip() if lines else ""
    return first or None


def source_name(source: Path) -> str:
    source = Path(source)
    if not (source.exists() or source.is_symlink()):
        raise UnpackError("source does not exist: %s" % source)
    if source.is_dir():
        name_file = source / "name.txt"
        if name_file.is_file() and not name_file.is_symlink():
            with open(name_file, "rb") as handle:
                name = _decode_name(handle.read(NAME_TXT_MAX_BYTES + 1), str(source))
            if name:
                return name
        return source.resolve().name
    try:
        zf = zipfile.ZipFile(source)
    except zipfile.BadZipFile as exc:
        raise UnpackError("%s: not a valid zip (%s)" % (source, exc)) from exc
    except OSError as exc:
        raise UnpackError("%s: cannot read archive (%s)" % (source, exc)) from exc
    with zf:
        try:
            info = zf.getinfo("name.txt")
        except KeyError:
            return source.stem
        if info.flag_bits & 0x1:
            raise UnpackError("%s: name.txt is encrypted" % source)
        try:
            with zf.open(info) as handle:
                data = handle.read(NAME_TXT_MAX_BYTES + 1)
        except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, OSError) as exc:
            raise UnpackError("%s: cannot read name.txt (%s)" % (source, exc)) from exc
    return _decode_name(data, str(source)) or source.stem


def main(argv: List[str]) -> int:
    command, args = (argv[0], argv[1:]) if argv else ("", [])
    arity = {"extract": 2, "pages": 1, "name": 1}
    if command not in arity or len(args) != arity[command]:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        if command == "extract":
            files = safe_extract(Path(args[0]), Path(args[1]))
            print(len(files))
            print(args[1])
        elif command == "pages":
            for page in find_pages(Path(args[0])):
                print(page)
        else:
            print(source_name(Path(args[0])))
    except UnpackError as exc:
        print("error: %s" % str(exc).replace("\n", " "), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
