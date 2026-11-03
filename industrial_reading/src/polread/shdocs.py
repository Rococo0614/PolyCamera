"""Read-only discovery of SHDocs four-direction capture directories."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
from pathlib import Path
import re

from PIL import Image


REQUIRED_STEMS = ("i0", "i45", "i90", "i135")
OPTIONAL_STEMS = ("s0_norm", "deglared")


@dataclass(frozen=True)
class SHDocsCapture:
    sample_id: str
    document_id: str
    condition_id: str
    capture_dir: str
    i0_path: str
    i45_path: str
    i90_path: str
    i135_path: str
    s0_norm_path: str
    deglared_path: str
    width: int
    height: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def infer_document_condition(name: str) -> tuple[str, str]:
    match = re.match(r"^(?P<document>.+)_(?P<condition>[a-o])$", name, re.IGNORECASE)
    if match:
        return match.group("document"), match.group("condition").lower()
    return name, "unknown"


def _image_map(directory: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            result[path.stem.lower()] = path
    return result


def discover_captures(root: Path) -> list[SHDocsCapture]:
    root = Path(root).resolve()
    captures: list[SHDocsCapture] = []
    if all((root / stem).is_dir() for stem in REQUIRED_STEMS):
        for i0_path in sorted((root / "i0").glob("*.png")):
            capture_id = i0_path.stem
            files = {
                stem: root / stem / f"{capture_id}.png"
                for stem in (*REQUIRED_STEMS, *OPTIONAL_STEMS)
            }
            if not all(files[stem].is_file() for stem in REQUIRED_STEMS):
                continue
            document_id, condition_id = infer_document_condition(capture_id)
            if condition_id == "unknown":
                condition_id = "camera"
            with Image.open(i0_path) as image:
                width, height = image.size
            captures.append(
                SHDocsCapture(
                    sample_id=capture_id,
                    document_id=document_id,
                    condition_id=condition_id,
                    capture_dir=str(root / capture_id),
                    i0_path=str(files["i0"]),
                    i45_path=str(files["i45"]),
                    i90_path=str(files["i90"]),
                    i135_path=str(files["i135"]),
                    s0_norm_path=str(files["s0_norm"]) if files["s0_norm"].is_file() else "",
                    deglared_path=str(files["deglared"]) if files["deglared"].is_file() else "",
                    width=width,
                    height=height,
                )
            )
        return captures
    for directory in sorted(path for path in root.rglob("*") if path.is_dir()):
        files = _image_map(directory)
        if not set(REQUIRED_STEMS).issubset(files):
            continue
        relative = directory.relative_to(root).as_posix()
        document_id, condition_id = infer_document_condition(directory.name)
        with Image.open(files["i0"]) as image:
            width, height = image.size
        captures.append(
            SHDocsCapture(
                sample_id=relative,
                document_id=document_id,
                condition_id=condition_id,
                capture_dir=str(directory),
                i0_path=str(files["i0"]),
                i45_path=str(files["i45"]),
                i90_path=str(files["i90"]),
                i135_path=str(files["i135"]),
                s0_norm_path=str(files.get("s0_norm", "")),
                deglared_path=str(files.get("deglared", "")),
                width=width,
                height=height,
            )
        )
    return captures


def write_manifest(captures: list[SHDocsCapture], output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(SHDocsCapture.__dataclass_fields__)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for capture in captures:
            writer.writerow(capture.to_dict())
