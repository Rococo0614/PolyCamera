#!/usr/bin/env python3
"""List or selectively extract files from a large HTTP ZIP via Range requests.

This avoids downloading the full ~159 GiB HAMMER archive. The server must
support byte ranges. Listing still downloads the ZIP central directory
(approximately tens of MiB for HAMMER) and may take a few minutes.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import os
import shutil
import urllib.request
import zipfile
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path, PurePosixPath


class HTTPRangeReader(io.RawIOBase):
    def __init__(
        self,
        url: str,
        *,
        block_size: int = 8 * 1024 * 1024,
        cache_blocks: int = 8,
        timeout: float = 60.0,
        disk_cache: Path | None = None,
    ) -> None:
        self.url = url
        self.block_size = block_size
        self.cache_blocks = cache_blocks
        self.timeout = timeout
        self.position = 0
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self.disk_cache = disk_cache
        if self.disk_cache is not None:
            cache_key = hashlib.sha256(
                f"{url}|{block_size}".encode("utf-8")
            ).hexdigest()[:20]
            self.disk_cache = self.disk_cache / cache_key
            self.disk_cache.mkdir(parents=True, exist_ok=True)
        self._size = self._discover_size()

    def _request(self, *, method: str = "GET", headers: dict[str, str] | None = None):
        request = urllib.request.Request(
            self.url,
            method=method,
            headers={"User-Agent": "PolyCamera-research/0.1", **(headers or {})},
        )
        return urllib.request.urlopen(request, timeout=self.timeout)

    def _discover_size(self) -> int:
        with self._request(method="HEAD") as response:
            length = response.headers.get("Content-Length")
            if length is None:
                raise OSError("Remote server did not provide Content-Length")
            return int(length)

    def _get_block(self, block_index: int) -> bytes:
        if block_index in self._cache:
            data = self._cache.pop(block_index)
            self._cache[block_index] = data
            return data

        start = block_index * self.block_size
        end = min(start + self.block_size, self._size) - 1
        if start >= self._size:
            return b""
        expected = end - start + 1
        cache_path = (
            self.disk_cache / f"{block_index:08d}.bin"
            if self.disk_cache is not None
            else None
        )
        if cache_path is not None and cache_path.exists():
            data = cache_path.read_bytes()
            if len(data) == expected:
                self._cache[block_index] = data
                return data
            cache_path.unlink()

        with self._request(headers={"Range": f"bytes={start}-{end}"}) as response:
            if response.status != 206:
                raise OSError(f"Server ignored Range request (HTTP {response.status})")
            data = response.read()
        if len(data) != expected:
            raise OSError(f"Short Range response: expected {expected}, got {len(data)}")

        if cache_path is not None:
            temporary = cache_path.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(cache_path)

        self._cache[block_index] = data
        while len(self._cache) > self.cache_blocks:
            self._cache.popitem(last=False)
        return data

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence == os.SEEK_SET:
            target = offset
        elif whence == os.SEEK_CUR:
            target = self.position + offset
        elif whence == os.SEEK_END:
            target = self._size + offset
        else:
            raise ValueError(f"Unsupported whence: {whence}")
        if target < 0:
            raise ValueError("Negative seek position")
        self.position = target
        return target

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = self._size - self.position
        size = min(size, self._size - self.position)
        if size <= 0:
            return b""

        chunks: list[bytes] = []
        remaining = size
        while remaining:
            block_index = self.position // self.block_size
            block_offset = self.position % self.block_size
            block = self._get_block(block_index)
            take = min(remaining, len(block) - block_offset)
            if take <= 0:
                break
            chunks.append(block[block_offset : block_offset + take])
            self.position += take
            remaining -= take
        return b"".join(chunks)


def is_safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def matching_members(
    archive: zipfile.ZipFile,
    patterns: Sequence[str],
    limit: int | None,
) -> list[zipfile.ZipInfo]:
    matches: list[zipfile.ZipInfo] = []
    for info in archive.infolist():
        if not info.is_dir() and any(
            fnmatch.fnmatch(info.filename, pattern) for pattern in patterns
        ):
            matches.append(info)
            if limit is not None and len(matches) >= limit:
                break
    return matches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--block-size-mib", type=int, default=8)
    parser.add_argument(
        "--cache-dir",
        default=str(Path(__file__).resolve().parents[1] / ".cache" / "remote_zip"),
        help="Persistent Range-block cache; use an empty string to disable",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument(
        "--pattern", action="append", help="Glob; repeat to combine patterns"
    )
    list_parser.add_argument("--limit", type=int, default=100)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument(
        "--pattern", action="append", required=True, help="Glob; repeat as needed"
    )
    extract_parser.add_argument("--output", required=True)
    extract_parser.add_argument("--limit", type=int, default=100)
    extract_parser.add_argument(
        "--max-uncompressed-mib",
        type=int,
        default=2048,
        help="Safety limit across selected files",
    )
    extract_parser.add_argument(
        "--minimum-free-gib",
        type=float,
        default=10.0,
        help="Refuse extraction if projected free space would fall below this",
    )
    args = parser.parse_args()

    reader = HTTPRangeReader(
        args.url,
        block_size=args.block_size_mib * 1024 * 1024,
        disk_cache=Path(args.cache_dir) if args.cache_dir else None,
    )
    with zipfile.ZipFile(reader) as archive:
        patterns = args.pattern or ["*"]
        members = matching_members(archive, patterns, args.limit)
        if args.command == "list":
            for info in members:
                print(f"{info.file_size}\t{info.compress_size}\t{info.filename}")
            print(f"matched={len(members)}")
            return

        total = sum(info.file_size for info in members)
        limit_bytes = args.max_uncompressed_mib * 1024 * 1024
        if total > limit_bytes:
            raise SystemExit(
                f"Refusing to extract {total / 2**20:.1f} MiB; "
                f"limit is {args.max_uncompressed_mib} MiB"
            )
        output_root = Path(args.output).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        free_bytes = shutil.disk_usage(output_root).free
        minimum_free_bytes = int(args.minimum_free_gib * 2**30)
        if free_bytes - total < minimum_free_bytes:
            raise SystemExit(
                f"Refusing extraction: projected free space is "
                f"{(free_bytes - total) / 2**30:.1f} GiB, below "
                f"{args.minimum_free_gib:.1f} GiB"
            )
        for info in members:
            if not is_safe_member(info.filename):
                raise SystemExit(f"Unsafe ZIP member path: {info.filename}")
            destination = (output_root / PurePosixPath(info.filename)).resolve()
            if output_root not in destination.parents:
                raise SystemExit(f"Path escapes output root: {info.filename}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and destination.stat().st_size == info.file_size:
                print(f"exists\t{destination}")
                continue
            temporary = destination.with_name(destination.name + ".part")
            try:
                with archive.open(info) as source, temporary.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                if temporary.stat().st_size != info.file_size:
                    raise OSError(
                        f"Extracted size mismatch for {info.filename}: "
                        f"expected {info.file_size}, got {temporary.stat().st_size}"
                    )
                temporary.replace(destination)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
            print(destination)
        print(f"extracted={len(members)} bytes={total}")


if __name__ == "__main__":
    main()
