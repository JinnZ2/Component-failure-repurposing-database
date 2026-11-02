#!/usr/bin/env python3
"""
fetch_ims_bearings.py -- download and extract the IMS bearing run-to-failure data set.

Co-authored (2026-10-31). CC0 for this script. The data set keeps its own
license (see data/README_ims_bearings.md; license status VERIFY until read from the NASA page).

Imports: Python standard library only. Extraction of the inner archives needs the system
libarchive shared library (called through stdlib ctypes): the archive is
    4. Bearings.zip  (zip, stdlib zipfile)
      -> IMS.7z      (7z / LZMA)
        -> 1st_test.rar, 2nd_test.rar, 3rd_test.rar  (RAR 2.9 solid; no stdlib decoder)
        -> Readme Document for IMS Bearing Data.pdf
Raw data is written under data/external/ (git-ignored) and is never committed.

USAGE
  python3 scripts/fetch_ims_bearings.py            download (resumable), verify, extract
  python3 scripts/fetch_ims_bearings.py --verify   checksums + snapshot counts only
"""
import argparse
import ctypes
import ctypes.util
import hashlib
import os
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "external", "ims_bearings")
URL = "https://phm-datasets.s3.amazonaws.com/NASA/4.+Bearings.zip"
ZIP_NAME = "bearings.zip"
ZIP_MEMBER = "4. Bearings/IMS.7z"
# Recorded 2026-10-31 from the download used for the first run.
ZIP_SHA256 = "21001ac266c465f5d345ec42d7b508c6a6328487fd9d4d7774422dd5ea10ad83"
ZIP_SIZE = 1075597174
# Snapshot counts stated in the data set's own readme (IMS Bearing Data, section 2).
# Note 2026-10-31: set 3 is delivered as 3rd_test.rar -> folder 4th_test/txt/ holding 6324
# snapshots (to 2004-04-18); the readme states 4448 files ending 2004-04-04 19:01:57, and
# exactly 4448 delivered files fall inside that window. Mismatch kept as delivered.
README_COUNTS = {"1st_test": 2156, "2nd_test": 984, "4th_test": 4448}
SET_DIRS = {1: "1st_test", 2: "2nd_test", 3: os.path.join("4th_test", "txt")}
SET3_README_END = "2004.04.04.19.01.57"


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                return h.hexdigest()
            h.update(b)


def download(url=URL, dest=None, opener=urllib.request.urlopen):
    """Resumable download with a Range request. Returns the local path."""
    dest = dest or os.path.join(OUT, ZIP_NAME)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    have = os.path.getsize(dest) if os.path.exists(dest) else 0
    if have == ZIP_SIZE:
        return dest
    req = urllib.request.Request(url, headers={"Range": "bytes=%d-" % have} if have else {})
    with opener(req, timeout=120) as r, open(dest, "ab" if have else "wb") as f:
        while True:
            b = r.read(1 << 22)
            if not b:
                break
            f.write(b)
    return dest


def check_zip(path, expected=ZIP_SHA256):
    got = sha256_file(path)
    if got != expected:
        raise SystemExit("checksum mismatch for %s: %s != %s" % (path, got, expected))
    return got


# ------------------------------------------------------------------ libarchive via ctypes

class LibArchive:
    """Minimal read-only libarchive binding (stdlib ctypes)."""

    def __init__(self, name=None):
        name = name or ctypes.util.find_library("archive")
        if not name:
            raise SystemExit("libarchive shared library not found; it is required to read the "
                             "7z/RAR layers (no stdlib decoder for RAR)")
        la = ctypes.CDLL(name)
        vp, cp = ctypes.c_void_p, ctypes.c_char_p
        la.archive_read_new.restype = vp
        for fn in ("archive_read_support_format_all", "archive_read_support_filter_all",
                   "archive_read_free"):
            getattr(la, fn).argtypes = [vp]
        la.archive_read_open_filename.argtypes = [vp, cp, ctypes.c_size_t]
        la.archive_read_next_header.argtypes = [vp, ctypes.POINTER(vp)]
        la.archive_entry_pathname.argtypes = [vp]
        la.archive_entry_pathname.restype = cp
        la.archive_entry_size.argtypes = [vp]
        la.archive_entry_size.restype = ctypes.c_int64
        la.archive_read_data.argtypes = [vp, vp, ctypes.c_size_t]
        la.archive_read_data.restype = ctypes.c_ssize_t
        la.archive_error_string.argtypes = [vp]
        la.archive_error_string.restype = cp
        la.archive_version_string.restype = cp
        self.la = la
        self.version = la.archive_version_string().decode()

    def entries(self, path):
        """Yield (name, bytes) for each entry of the archive at `path`."""
        la = self.la
        a = la.archive_read_new()
        la.archive_read_support_format_all(a)
        la.archive_read_support_filter_all(a)
        if la.archive_read_open_filename(a, path.encode(), 1 << 16) != 0:
            raise SystemExit("libarchive cannot open %s: %s" % (path, la.archive_error_string(a)))
        ent = ctypes.c_void_p()
        buf = ctypes.create_string_buffer(1 << 20)
        try:
            while True:
                r = la.archive_read_next_header(a, ctypes.byref(ent))
                if r == 1:  # ARCHIVE_EOF
                    return
                if r != 0:
                    raise SystemExit("libarchive header error: %s" % la.archive_error_string(a))
                name = la.archive_entry_pathname(ent).decode("utf-8", "replace")
                parts = []
                while True:
                    n = la.archive_read_data(a, buf, len(buf))
                    if n < 0:
                        raise SystemExit("libarchive data error in %s: %s"
                                         % (name, la.archive_error_string(a)))
                    if n == 0:
                        break
                    parts.append(buf.raw[:n])
                yield name, b"".join(parts)
        finally:
            la.archive_read_free(a)


def extract(zip_path, out=OUT, lib=None):
    lib = lib or LibArchive()
    seven = os.path.join(out, "IMS.7z")
    if not os.path.exists(seven):
        with zipfile.ZipFile(zip_path) as z, z.open(ZIP_MEMBER) as src, open(seven, "wb") as dst:
            while True:
                b = src.read(1 << 22)
                if not b:
                    break
                dst.write(b)
    inner = {}
    for name, data in lib.entries(seven):
        p = os.path.join(out, os.path.basename(name))
        with open(p, "wb") as f:
            f.write(data)
        inner[os.path.basename(name)] = hashlib.sha256(data).hexdigest()
    ext = os.path.join(out, "extracted")
    counts = {}
    for rar in sorted(n for n in inner if n.endswith(".rar")):
        for name, data in lib.entries(os.path.join(out, rar)):
            if not data:
                continue
            p = os.path.join(ext, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(data)
            top = name.split("/")[0]
            counts[top] = counts.get(top, 0) + 1
    return {"inner_sha256": inner, "snapshot_counts": counts, "libarchive": lib.version}


def snapshot_counts(out=OUT):
    ext = os.path.join(out, "extracted")
    if not os.path.isdir(ext):
        return {}
    out_counts = {}
    for d in sorted(os.listdir(ext)):
        n = sum(len(files) for _, _, files in os.walk(os.path.join(ext, d)))
        if n:
            out_counts[d] = n
    return out_counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    zp = os.path.join(OUT, ZIP_NAME)
    if not a.verify:
        zp = download()
    print("zip sha256", check_zip(zp))
    if not a.verify:
        info = extract(zp)
        print("libarchive", info["libarchive"])
        for k, v in sorted(info["inner_sha256"].items()):
            print("inner sha256", v, k)
    counts = snapshot_counts()
    for k, n in counts.items():
        note = "" if README_COUNTS.get(k) == n else "  (readme states %s)" % README_COUNTS.get(k)
        print("snapshots %-9s %5d%s" % (k, n, note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
