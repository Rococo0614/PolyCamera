#!/usr/bin/env python3
"""Fetch only the PDD 2025 PNG entries from the remote ZIP using HTTP Range.

The full archive is ~12.2 GB, of which ~11.1 GB is MATLAB data that the Python
experiments do not use. This reads the ZIP central directory remotely, selects
``GT_{0,45,90,135}.png`` and ``Test_{0,45,90,135}.png`` entries, downloads only
those, and verifies every extracted file against the CRC-32 stored in the
archive. It never claims to have verified the whole-archive SHA-256.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
import time
import urllib.request
import zipfile

DEFAULT_URL = "http://www.ok.sc.e.titech.ac.jp/res/PolarDem/data/DatasetPDD.zip"
WANTED = re.compile(r"(?:^|/)ImagePNG/.+/(?:GT|Test)_(?:0|45|90|135)\.png$")


class RangeFile:
    """Read-only seekable file over HTTP Range requests with block caching."""

    def __init__(self, url: str, *, block_bytes: int = 4 * 1024 * 1024, timeout: float = 60.0):
        self.url = url
        self.block_bytes = block_bytes
        self.timeout = timeout
        self.position = 0
        self._cache: dict[int, bytes] = {}
        self.requests = 0
        self.bytes_fetched = 0
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            self.size = int(response.headers["Content-Length"])
            if response.headers.get("Accept-Ranges", "").lower() != "bytes":
                raise RuntimeError("Server does not advertise byte-range support")

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self.position = offset
        elif whence == 1:
            self.position += offset
        elif whence == 2:
            self.position = self.size + offset
        else:
            raise ValueError(whence)
        self.position = max(0, min(self.position, self.size))
        return self.position

    def _block(self, index: int) -> bytes:
        cached = self._cache.get(index)
        if cached is not None:
            return cached
        start = index * self.block_bytes
        end = min(self.size, start + self.block_bytes) - 1
        last_error: Exception | None = None
        for attempt in range(6):
            try:
                request = urllib.request.Request(
                    self.url, headers={"Range": f"bytes={start}-{end}"}
                )
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    if response.status != 206:
                        raise RuntimeError(f"Expected HTTP 206, got {response.status}")
                    data = response.read()
                if len(data) != end - start + 1:
                    raise RuntimeError(f"Short read {len(data)} for {start}-{end}")
                self.requests += 1
                self.bytes_fetched += len(data)
                if len(self._cache) >= 8:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[index] = data
                return data
            except Exception as exc:  # noqa: BLE001 - retried and re-raised below
                last_error = exc
                time.sleep(min(30, 2**attempt))
        raise RuntimeError(f"Range {start}-{end} failed after retries: {last_error}")

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = self.size - self.position
        size = min(size, self.size - self.position)
        chunks: list[bytes] = []
        while size > 0:
            index, offset = divmod(self.position, self.block_bytes)
            block = self._block(index)
            piece = block[offset : offset + size]
            chunks.append(piece)
            self.position += len(piece)
            size -= len(piece)
        return b"".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args()

    remote = RangeFile(args.url)
    archive = zipfile.ZipFile(remote)  # type: ignore[arg-type]
    infos = [info for info in archive.infolist() if WANTED.search(info.filename)]
    total = sum(info.file_size for info in infos)
    print(
        f"archive_bytes={remote.size} entries={len(archive.infolist())} "
        f"selected_png={len(infos)} selected_bytes={total}",
        flush=True,
    )
    if args.list_only:
        for info in infos[:6]:
            print(info.filename, info.file_size, info.compress_type)
        return

    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    started = time.time()
    for index, info in enumerate(infos, start=1):
        relative = PurePosixPath(info.filename)
        destination = args.output_root.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and destination.stat().st_size == info.file_size:
            status = "present"
        else:
            with archive.open(info) as source, destination.open("wb") as handle:
                handle.write(source.read())  # zipfile verifies CRC-32 at EOF
            status = "downloaded"
        manifest.append(
            {
                "path": info.filename,
                "bytes": info.file_size,
                "crc32": f"{info.CRC:08x}",
                "status": status,
            }
        )
        if index % 40 == 0 or index == len(infos):
            print(
                f"{index}/{len(infos)} elapsed={time.time() - started:.0f}s "
                f"fetched={remote.bytes_fetched / 1e6:.0f}MB requests={remote.requests}",
                flush=True,
            )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(
            {
                "url": args.url,
                "archive_bytes": remote.size,
                "selected_png_files": len(manifest),
                "selected_bytes": total,
                "files": manifest,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print("done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
