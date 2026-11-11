#!/usr/bin/env python3
"""Audit SHDocs E2 string lengths under the frozen ROI sampling protocol."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import statistics
import unicodedata
import zipfile


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(text: object) -> str:
    value = unicodedata.normalize("NFKC", str(text)).upper()
    return re.sub(r"\s+", " ", value).strip()


def summarize_lengths(values: list[int]) -> dict[str, float | int]:
    quartiles = statistics.quantiles(values, n=4, method="inclusive")
    ordered = sorted(values)
    return {
        "min": min(values),
        "q1": float(quartiles[0]),
        "median": float(statistics.median(values)),
        "mean": float(statistics.mean(values)),
        "q3": float(quartiles[2]),
        "p90": int(ordered[round(0.9 * (len(ordered) - 1))]),
        "max": max(values),
    }


def length_bin(length: int) -> str:
    if length <= 5:
        return "1-5"
    if length <= 10:
        return "6-10"
    if length <= 20:
        return "11-20"
    if length <= 40:
        return "21-40"
    return "41+"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--exclusions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-sha256", default="")
    parser.add_argument("--seed", type=int, default=20261102)
    parser.add_argument("--regions-per-document", type=int, default=10)
    parser.add_argument("--conditions", default="a,b,c,d,e,f,g,h,i,j,k,l,m,n,o")
    args = parser.parse_args()

    split_payload = json.loads(args.split.read_text(encoding="utf-8"))
    assignments = {str(key): str(value) for key, value in split_payload["assignments"].items()}
    exclusions_payload = json.loads(args.exclusions.read_text(encoding="utf-8"))
    exclusions = {str(value) for value in exclusions_payload.get("sample_ids", [])}
    conditions = tuple(value.strip() for value in args.conditions.split(",") if value.strip())

    annotations: dict[str, dict[str, object]] = {}
    with zipfile.ZipFile(args.archive) as archive:
        for name in archive.namelist():
            if "/annotations/" not in name or not name.endswith(".json"):
                continue
            document = Path(name).stem
            if document not in assignments:
                continue
            payload = json.loads(archive.read(name))
            if document in annotations and annotations[document] != payload:
                raise ValueError(f"Conflicting annotations for {document}")
            annotations[document] = payload
    if set(annotations) != set(assignments):
        missing = sorted(set(assignments) - set(annotations))
        raise ValueError(f"Missing annotations for frozen documents: {missing}")

    selected: list[dict[str, object]] = []
    for document, payload in annotations.items():
        form = payload.get("form")
        if not isinstance(form, list):
            raise ValueError(f"Annotation has no form list: {document}")
        eligible: list[int] = []
        for index, element in enumerate(form):
            if not isinstance(element, dict):
                continue
            text = str(element.get("text", ""))
            box = element.get("box")
            if not text or not isinstance(box, list) or len(box) != 4:
                continue
            x0, y0, x1, y1 = (int(value) for value in box)
            if x1 > x0 and y1 > y0:
                eligible.append(index)
        ranked = sorted(
            eligible,
            key=lambda index: hashlib.sha256(
                f"{args.seed}:{document}:{index}".encode()
            ).hexdigest(),
        )[: args.regions_per_document]
        for index in ranked:
            element = form[index]
            assert isinstance(element, dict)
            selected.append(
                {
                    "document": document,
                    "region_index": index,
                    "split": assignments[document],
                    "text": normalize_text(element["text"]),
                    "label": str(element.get("label", "unknown")),
                }
            )

    test_unique = [row for row in selected if row["split"] == "test"]
    expanded_test: list[dict[str, object]] = []
    for row in test_unique:
        for condition in conditions:
            sample_id = f"{row['document']}_{condition}_{row['region_index']}"
            if sample_id not in exclusions:
                expanded_test.append({**row, "condition": condition, "sample_id": sample_id})

    unique_lengths = [len(str(row["text"])) for row in test_unique]
    expanded_lengths = [len(str(row["text"])) for row in expanded_test]
    payload = {
        "experiment": "shdocs-e2-string-length-audit-v1",
        "date": "2026-11-11",
        "proxy_only": True,
        "claim_boundary": (
            "This audits the frozen SHDocs/FUNSD GT-ROI strings used by E2. "
            "They are mixed form fields, phrases and paragraphs, not industrial spray codes."
        ),
        "dataset": {
            "archive_bytes": args.archive.stat().st_size,
            "archive_sha256": args.archive_sha256 or sha256(args.archive),
            "documents": len(annotations),
        },
        "protocol": {
            "split_version": split_payload.get("split_version", "unknown"),
            "split_assignment_sha256": split_payload.get("assignment_sha256", ""),
            "split_file_sha256": sha256(args.split),
            "exclusions_file_sha256": sha256(args.exclusions),
            "seed": args.seed,
            "regions_per_document": args.regions_per_document,
            "conditions": list(conditions),
            "normalization": "NFKC + uppercase + collapsed whitespace",
        },
        "test_unique_strings": {
            "documents": len({str(row["document"]) for row in test_unique}),
            "regions": len(test_unique),
            "character_length": summarize_lengths(unique_lengths),
            "length_bins": dict(sorted(Counter(length_bin(value) for value in unique_lengths).items())),
            "annotation_labels": dict(
                sorted(Counter(str(row["label"]) for row in test_unique).items())
            ),
        },
        "test_roi_conditions": {
            "before_exclusions": len(test_unique) * len(conditions),
            "excluded": len(test_unique) * len(conditions) - len(expanded_test),
            "evaluated": len(expanded_test),
            "character_length": summarize_lengths(expanded_lengths),
        },
        "interpretation": [
            "The page-6 absolute exact-read rate combines strings from 1 to 376 characters; one normalized character error fails the whole ROI.",
            "The four analyzer views remain paired on the same ROI and string, so relative fixed-versus-oracle comparisons hold text length constant within each sample.",
            "Absolute exact-read must not be interpreted as an industrial date/lot-code accuracy ceiling.",
        ],
        "source_sha256": {
            str(Path(__file__).relative_to(Path.cwd())): sha256(Path(__file__)),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
