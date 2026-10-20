#!/usr/bin/env python3
"""Prepare pinned public source and apply a patch. Never builds/installs/runs EAP."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def prepare(archive=None):
    record = json.loads((ROOT / "third_party/minieap-source.json").read_text())
    if archive is None:
        with urllib.request.urlopen(record["archive_url"], timeout=30) as response:
            blob = response.read(10000001)
    else:
        with archive.open("rb") as source:
            blob = source.read(10000001)
    if len(blob) > 10000000 or hashlib.sha256(blob).hexdigest() != record["archive_sha256"]:
        raise ValueError("pinned source archive digest mismatch")
    patch = ROOT / "patches/minieap-safety-guards.patch"
    if hashlib.sha256(patch.read_bytes()).hexdigest() != record["patch_sha256"]:
        raise ValueError("local patch digest mismatch")
    target = ROOT / "build" / ("minieap-" + record["commit"])
    if target.parent.is_symlink() or (target.parent.exists() and not target.parent.is_dir()):
        raise ValueError("source parent is not an ordinary local directory")
    if target.exists() or target.is_symlink():
        raise ValueError("source target already exists; inspect rather than overwrite")
    prefix = "minieap-" + record["commit"]
    with zipfile.ZipFile(io.BytesIO(blob)) as source:
        members = source.infolist()
        if len(members) > 512 or sum(m.file_size for m in members) > 5000000:
            raise ValueError("source archive exceeds its bound")
        for member in members:
            parts = PurePosixPath(member.filename).parts
            if (not parts or parts[0] != prefix or ".." in parts or "\\" in member.filename
                    or any(":" in part for part in parts)
                    or PurePosixPath(member.filename).is_absolute()
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError("unsafe archive member")
        target.mkdir(parents=True)
        for member in members:
            parts = PurePosixPath(member.filename).parts[1:]
            if not parts or member.is_dir() or parts[-1] == "minieap.conf":
                continue
            destination = target.joinpath(*parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as out:
                out.write(source.read(member))
    subprocess.run(["patch", "--batch", "--forward", "-p1", "-i", str(patch)], cwd=target, check=True)
    print("Pinned source prepared and patched; nothing installed or authenticated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--archive", type=Path, help="Optional already-downloaded exact public ZIP")
    args = parser.parse_args()
    if args.prepare:
        try:
            prepare(args.archive)
        except (OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError):
            print("Source preparation stopped; inspect the local public archive, patch and tool availability.", file=sys.stderr)
            raise SystemExit(2)
    else:
        parser.print_help()
