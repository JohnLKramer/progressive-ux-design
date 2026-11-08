from __future__ import annotations

import os
import stat
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import unpack
from unpack import UnpackError, find_pages, safe_extract, source_name

SCRIPT = Path(unpack.__file__).resolve()


def make_zip(path: Path, entries, compression=zipfile.ZIP_DEFLATED) -> Path:
    """entries: iterable of (name, bytes) or (ZipInfo, bytes)."""
    with zipfile.ZipFile(path, "w", compression) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return path


def special_info(name: str, mode: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def assert_clean_failure(tmp_path: Path, dest: Path, message_part: str, zip_path: Path):
    before = sorted(p.name for p in tmp_path.iterdir())
    with pytest.raises(UnpackError) as excinfo:
        safe_extract(zip_path, dest)
    assert message_part in str(excinfo.value)
    assert not dest.exists() or list(dest.iterdir()) == []
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert not (tmp_path / "evil.txt").exists()


# ---- rejected archives ------------------------------------------------------


def test_parent_traversal_rejected(tmp_path):
    sub = tmp_path / "work"
    sub.mkdir()
    zp = make_zip(sub / "a.zip", [("ok.txt", b"x"), ("../evil.txt", b"x")])
    dest = sub / "out"
    with pytest.raises(UnpackError, match="evil.txt"):
        safe_extract(zp, dest)
    assert not dest.exists()
    assert not (tmp_path / "evil.txt").exists()
    assert sorted(p.name for p in sub.iterdir()) == ["a.zip"]


def test_absolute_path_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("/abs.txt", b"x")])
    assert_clean_failure(tmp_path, tmp_path / "out", "/abs.txt", zp)


def test_backslash_traversal_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("..\\evil.txt", b"x")])
    assert_clean_failure(tmp_path, tmp_path / "out", "evil.txt", zp)


def test_windows_drive_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("C:\\x", b"x")])
    assert_clean_failure(tmp_path, tmp_path / "out", "C:", zp)


def test_drive_prefix_with_forward_slash_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("C:/x", b"x")])
    assert_clean_failure(tmp_path, tmp_path / "out", "C:", zp)


def test_nul_in_name_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("good.txt", b"x")])
    data = zp.read_bytes().replace(b"good.txt", b"go\x00d.txt")  # same length, both headers
    zp.write_bytes(data)
    assert_clean_failure(tmp_path, tmp_path / "out", "NUL", zp)


def test_symlink_entry_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [(special_info("link", stat.S_IFLNK | 0o777), b"/etc/passwd")])
    assert_clean_failure(tmp_path, tmp_path / "out", "link", zp)


@pytest.mark.parametrize(
    "mode", [stat.S_IFBLK, stat.S_IFCHR, stat.S_IFIFO, stat.S_IFSOCK], ids=["blk", "chr", "fifo", "sock"]
)
def test_special_file_types_rejected(tmp_path, mode):
    zp = make_zip(tmp_path / "a.zip", [(special_info("dev", mode | 0o644), b"")])
    assert_clean_failure(tmp_path, tmp_path / "out", "dev", zp)


def test_duplicate_names_rejected(tmp_path):
    with pytest.warns(UserWarning):
        zp = make_zip(tmp_path / "a.zip", [("a.txt", b"1"), ("a.txt", b"2")])
    assert_clean_failure(tmp_path, tmp_path / "out", "a.txt", zp)


def test_duplicate_names_after_normalization_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("d/a.txt", b"1"), ("d//./a.txt", b"2")])
    assert_clean_failure(tmp_path, tmp_path / "out", "a.txt", zp)


def test_file_and_directory_conflict_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("a", b"1"), ("a/b.txt", b"2")])
    assert_clean_failure(tmp_path, tmp_path / "out", "a", zp)


def test_declared_size_bomb_rejected_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(unpack, "MAX_UNPACKED_BYTES", 1000)
    zp = make_zip(tmp_path / "a.zip", [("first.txt", b"a" * 600), ("second.txt", b"b" * 600)])
    assert_clean_failure(tmp_path, tmp_path / "out", "MAX_UNPACKED_BYTES", zp)


def test_real_size_bomb_with_default_cap(tmp_path):
    zp = tmp_path / "a.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
        with zf.open("big.bin", "w", force_zip64=True) as handle:
            chunk = b"\0" * (1024 * 1024)
            for _ in range(unpack.MAX_UNPACKED_BYTES // len(chunk) + 1):
                handle.write(chunk)
    assert_clean_failure(tmp_path, tmp_path / "out", "big.bin", zp)


def test_lying_header_smaller_declared_size_aborts_and_cleans(tmp_path):
    payload = bytes(range(256)) * 40
    zp = make_zip(tmp_path / "a.zip", [("ok.txt", b"fine"), ("lie.bin", payload)], zipfile.ZIP_STORED)
    raw = zp.read_bytes()
    real = struct.pack("<I", len(payload))
    fake = struct.pack("<I", 100)
    patched = raw.replace(real + real, fake + fake)  # compress_size + file_size, local + central
    assert patched != raw
    zp.write_bytes(patched)
    assert_clean_failure(tmp_path, tmp_path / "out", "lie.bin", zp)


def test_streaming_byte_count_aborts_when_stream_exceeds_declared_size(tmp_path, monkeypatch):
    zp = make_zip(tmp_path / "a.zip", [("ok.txt", b"fine"), ("grow.bin", b"x" * 10)])
    real_open = zipfile.ZipFile.open

    class Growing:
        def __init__(self, inner):
            self.inner = inner

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.inner.close()

        def read(self, n=-1):
            return self.inner.read(n) or b"y" * 50  # never reaches EOF

    def fake_open(self, name, *args, **kwargs):
        stream = real_open(self, name, *args, **kwargs)
        if getattr(name, "filename", name) == "grow.bin":
            return Growing(stream)
        return stream

    monkeypatch.setattr(zipfile.ZipFile, "open", fake_open)
    assert_clean_failure(tmp_path, tmp_path / "out", "grow.bin", zp)


def test_entry_count_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(unpack, "MAX_ENTRIES", 3)
    zp = make_zip(tmp_path / "a.zip", [("f%d.txt" % i, b"x") for i in range(4)])
    assert_clean_failure(tmp_path, tmp_path / "out", "MAX_ENTRIES", zp)


def test_encrypted_entry_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("secret.txt", b"x")])
    raw = bytearray(zp.read_bytes())
    local = raw.index(b"PK\x03\x04")
    central = raw.index(b"PK\x01\x02")
    raw[local + 6] |= 1  # general purpose flag bits
    raw[central + 8] |= 1
    zp.write_bytes(bytes(raw))
    assert_clean_failure(tmp_path, tmp_path / "out", "secret.txt", zp)


def test_corrupt_archive_rejected(tmp_path):
    zp = tmp_path / "a.zip"
    zp.write_bytes(b"this is not a zip file at all")
    assert_clean_failure(tmp_path, tmp_path / "out", "a.zip", zp)


def test_missing_archive_rejected(tmp_path):
    assert_clean_failure(tmp_path, tmp_path / "out", "nope.zip", tmp_path / "nope.zip")


def test_corrupt_crc_after_partial_write_cleans_up_new_dest(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("a.txt", b"first"), ("sub/b.txt", b"second payload")], zipfile.ZIP_STORED)
    raw = zp.read_bytes().replace(b"second payload", b"SECOND payload")  # CRC no longer matches
    zp.write_bytes(raw)
    assert_clean_failure(tmp_path, tmp_path / "out", "b.txt", zp)


def test_partial_write_into_existing_empty_dest_empties_it(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("a.txt", b"first"), ("sub/b.txt", b"second payload")], zipfile.ZIP_STORED)
    zp.write_bytes(zp.read_bytes().replace(b"second payload", b"SECOND payload"))
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(UnpackError, match="b.txt"):
        safe_extract(zp, dest)
    assert dest.is_dir()
    assert list(dest.iterdir()) == []


# ---- dest rules --------------------------------------------------------------


def test_non_empty_dest_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("a.txt", b"x")])
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(UnpackError, match="not empty"):
        safe_extract(zp, dest)
    assert (dest / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert [p.name for p in dest.iterdir()] == ["keep.txt"]


def test_dest_that_is_a_file_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("a.txt", b"x")])
    dest = tmp_path / "out"
    dest.write_text("x", encoding="utf-8")
    with pytest.raises(UnpackError, match="directory"):
        safe_extract(zp, dest)


def test_missing_dest_parent_rejected(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("a.txt", b"x")])
    with pytest.raises(UnpackError, match="parent"):
        safe_extract(zp, tmp_path / "no" / "out")


# ---- success -----------------------------------------------------------------


def test_clean_zip_extracts_with_normalized_permissions(tmp_path):
    exec_info = special_info("run.sh", stat.S_IFREG | 0o777)
    zp = tmp_path / "a.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("index.html", "<p>héllo</p>".encode("utf-8"))
        zf.writestr("assets/", b"")
        zf.writestr("assets/app.css", b"body{}")
        zf.writestr("deep/er/x.txt", b"x")
        zf.writestr(exec_info, b"#!/bin/sh\n")
        zf.writestr(special_info("private.txt", stat.S_IFREG | 0o600), b"p")
    dest = tmp_path / "out"
    files = safe_extract(zp, dest)
    assert files == sorted(files)
    assert files == sorted(
        [
            dest / "assets" / "app.css",
            dest / "deep" / "er" / "x.txt",
            dest / "index.html",
            dest / "private.txt",
            dest / "run.sh",
        ]
    )
    assert (dest / "index.html").read_bytes() == "<p>héllo</p>".encode("utf-8")
    assert (dest / "assets" / "app.css").read_bytes() == b"body{}"
    for path in files:
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o644
    for directory in (dest / "assets", dest / "deep", dest / "deep" / "er"):
        assert stat.S_IMODE(os.stat(directory).st_mode) == 0o755


def test_empty_directory_entry_created(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("only/", b""), ("f.txt", b"x")])
    dest = tmp_path / "out"
    assert safe_extract(zp, dest) == [dest / "f.txt"]
    assert (dest / "only").is_dir()


def test_existing_empty_dest_ok(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("a.txt", b"x")])
    dest = tmp_path / "out"
    dest.mkdir()
    assert safe_extract(zp, dest) == [dest / "a.txt"]


# ---- find_pages --------------------------------------------------------------


def test_find_pages(tmp_path):
    root = tmp_path / "src"
    (root / "sub" / "deeper").mkdir(parents=True)
    (root / "page_files").mkdir()
    (root / "__MACOSX").mkdir()
    (root / ".hidden").mkdir()
    (root / "real_files" / "inner").mkdir(parents=True)
    for rel in (
        "index.html",
        "sub/two.htm",
        "sub/deeper/THREE.HTML",
        "sub/Four.Htm",
        "page_files/saved.html",
        "real_files/inner/x.html",
        "__MACOSX/._index.html",
        "__MACOSX/mac.html",
        ".hidden/h.html",
        ".dot.html",
        ".DS_Store",
        "notes.txt",
        "style.css",
    ):
        (root / rel).write_text("x", encoding="utf-8")
    assert find_pages(root) == [
        root / "index.html",
        root / "sub" / "Four.Htm",
        root / "sub" / "deeper" / "THREE.HTML",
        root / "sub" / "two.htm",
    ]


def test_find_pages_does_not_follow_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.html").write_text("x", encoding="utf-8")
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.html").write_text("x", encoding="utf-8")
    os.symlink(outside, root / "linked")
    os.symlink(outside / "secret.html", root / "link.html")
    assert find_pages(root) == [root / "a.html"]


def test_find_pages_missing_dir(tmp_path):
    with pytest.raises(UnpackError, match="nope"):
        find_pages(tmp_path / "nope")


# ---- source_name -------------------------------------------------------------


def test_source_name_zip_without_name_txt_uses_stem(tmp_path):
    zp = make_zip(tmp_path / "2165_neon_carbon.zip", [("index.html", b"x")])
    assert source_name(zp) == "2165_neon_carbon"


def test_source_name_directory_name_txt(tmp_path):
    d = tmp_path / "gym"
    d.mkdir()
    (d / "name.txt").write_text("  Big Box Gym  \nsecond line\n", encoding="utf-8")
    assert source_name(d) == "Big Box Gym"


def test_source_name_directory_without_name_txt(tmp_path):
    d = tmp_path / "plain_dir"
    d.mkdir()
    assert source_name(d) == "plain_dir"


@pytest.mark.parametrize("content", ["", "\n", "   \n  \n"])
def test_source_name_empty_name_txt_is_absent(tmp_path, content):
    d = tmp_path / "fallback"
    d.mkdir()
    (d / "name.txt").write_text(content, encoding="utf-8")
    assert source_name(d) == "fallback"
    zp = make_zip(tmp_path / "zipstem.zip", [("name.txt", content.encode("utf-8"))])
    assert source_name(zp) == "zipstem"


def test_source_name_zip_with_name_txt(tmp_path):
    zp = make_zip(tmp_path / "x.zip", [("name.txt", "Café Gym\nmore".encode("utf-8")), ("index.html", b"x")])
    assert source_name(zp) == "Café Gym"
    assert not (tmp_path / "name.txt").exists()


def test_source_name_zip_ignores_nested_name_txt(tmp_path):
    zp = make_zip(tmp_path / "x.zip", [("sub/name.txt", b"Nested")])
    assert source_name(zp) == "x"


def test_source_name_zip_undecodable_fails(tmp_path):
    zp = make_zip(tmp_path / "x.zip", [("name.txt", b"\xff\xfe\xfa")])
    with pytest.raises(UnpackError, match="name.txt"):
        source_name(zp)


def test_source_name_directory_undecodable_fails(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "name.txt").write_bytes(b"\xff\xfe\xfa")
    with pytest.raises(UnpackError, match="name.txt"):
        source_name(d)


def test_source_name_reads_only_first_kilobyte(tmp_path):
    zp = make_zip(tmp_path / "x.zip", [("name.txt", b"Short\n" + b"z" * 5_000_000)])
    assert source_name(zp) == "Short"


def test_source_name_missing_source(tmp_path):
    with pytest.raises(UnpackError, match="nope"):
        source_name(tmp_path / "nope.zip")


def test_source_name_corrupt_zip(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"junk")
    with pytest.raises(UnpackError, match="bad.zip"):
        source_name(bad)


# ---- CLI ---------------------------------------------------------------------


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_cli_extract_pages_name(tmp_path):
    zp = make_zip(tmp_path / "Site.zip", [("a/index.html", b"x"), ("b.txt", b"y")])
    dest = tmp_path / "out"
    result = run_cli("extract", str(zp), str(dest))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["2", str(dest)]
    assert result.stderr == ""

    result = run_cli("pages", str(dest))
    assert result.returncode == 0
    assert result.stdout.splitlines() == [str(dest / "a" / "index.html")]

    assert run_cli("name", str(zp)).stdout == "Site\n"
    assert run_cli("name", str(dest)).stdout == "out\n"


def test_cli_unpack_error_exits_1_with_one_stderr_line(tmp_path):
    zp = make_zip(tmp_path / "a.zip", [("../evil.txt", b"x")])
    result = run_cli("extract", str(zp), str(tmp_path / "out"))
    assert result.returncode == 1
    assert result.stdout == ""
    assert len(result.stderr.splitlines()) == 1
    assert "evil.txt" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "args",
    [[], ["extract"], ["extract", "a.zip"], ["pages"], ["pages", "a", "b"], ["name"], ["bogus", "x"]],
)
def test_cli_usage_errors_exit_2_with_one_stderr_line(args):
    result = run_cli(*args)
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.splitlines()) == 1
    assert "usage" in result.stderr


def test_cli_missing_name_source_exits_1(tmp_path):
    result = run_cli("name", str(tmp_path / "nope"))
    assert result.returncode == 1
    assert len(result.stderr.splitlines()) == 1
