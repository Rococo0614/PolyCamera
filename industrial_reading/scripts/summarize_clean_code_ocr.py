#!/usr/bin/env python3
"""Summarize exact-read and CER for the clean-code E0 sanity set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from polread.evaluation import summarize_records
from polread.records import read_jsonl
from polread.text_metrics import TextNormalization


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = read_jsonl(args.records)
    normalization = TextNormalization(whitespace="collapse")
    payload = {
        "experiment": "offline-e0-synthetic-clean-code",
        "proxy_only": True,
        "ocr_backend": sorted({record.ocr_backend for record in records}),
        "overall": summarize_records(records, normalization=normalization)["clean"],
        "by_condition": {
            condition: summarize_records(
                [record for record in records if record.condition_id == condition],
                normalization=normalization,
            )["clean"]
            for condition in sorted({record.condition_id for record in records})
        },
        "by_prefix": {
            prefix: summarize_records(
                [
                    record
                    for record in records
                    if record.ground_truth.split(maxsplit=1)[0] == prefix
                ],
                normalization=normalization,
            )["clean"]
            for prefix in sorted(
                {record.ground_truth.split(maxsplit=1)[0] for record in records}
            )
        },
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    print(f"sha256={hashlib.sha256(encoded.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
