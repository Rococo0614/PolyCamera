import json
import tempfile
import unittest
from pathlib import Path

from polread.protocol import (
    capture_key,
    drop_excluded,
    limit_regions_per_document,
    load_excluded_sample_ids,
    load_frozen_split,
    shard_of,
)
from polread.shdocs_rois import SHDocsROI


def _roi(document: str, condition: str, region: int) -> SHDocsROI:
    return SHDocsROI(
        sample_id=f"{document}_{condition}_{region}",
        document_id=document,
        condition_id=condition,
        region_index=region,
        ground_truth="X",
        annotation_label="unknown",
        box=(0, 0, 4, 4),
        capture_dir=Path(f"/x/{document}_{condition}"),
    )


def _grid(documents=("d1", "d2"), conditions=("a", "b", "c"), regions=range(12)):
    return [_roi(d, c, r) for d in documents for c in conditions for r in regions]


class ProtocolTests(unittest.TestCase):
    def test_region_limit_is_condition_independent_and_deterministic(self):
        rois = _grid()
        kept = limit_regions_per_document(rois, 5, seed=11)
        for document in ("d1", "d2"):
            per_condition = {
                condition: {r.region_index for r in kept if r.document_id == document and r.condition_id == condition}
                for condition in ("a", "b", "c")
            }
            self.assertEqual(len({frozenset(v) for v in per_condition.values()}), 1)
            self.assertEqual(len(per_condition["a"]), 5)
        again = limit_regions_per_document(rois, 5, seed=11)
        self.assertEqual([r.sample_id for r in kept], [r.sample_id for r in again])
        # Many seeds must not all collapse to the same subset (seed really matters).
        subsets = {
            frozenset(
                r.sample_id
                for r in limit_regions_per_document(rois, 5, seed=seed)
                if r.condition_id == "a"
            )
            for seed in range(20)
        }
        self.assertGreater(len(subsets), 5)

    def test_region_limit_ignores_unrelated_conditions(self):
        subset = [r for r in _grid() if r.condition_id == "a"]
        full = limit_regions_per_document(_grid(), 5, seed=3)
        only_a = limit_regions_per_document(subset, 5, seed=3)
        self.assertEqual(
            {r.sample_id for r in only_a},
            {r.sample_id for r in full if r.condition_id == "a"},
        )

    def test_limit_must_be_positive(self):
        with self.assertRaises(ValueError):
            limit_regions_per_document(_grid(), 0, seed=1)

    def test_exclusions(self):
        rois = _grid(documents=("d1",), conditions=("a",), regions=range(3))
        kept = drop_excluded(rois, {"d1_a_1"})
        self.assertEqual([r.region_index for r in kept], [0, 2])

    def test_shards_partition_and_keep_captures_together(self):
        rois = _grid(documents=("d1", "d2", "d3", "d4"), conditions=tuple("abcdef"), regions=range(4))
        shards = 5
        # Capture identity is defined independently of the function under test.
        seen: dict[tuple[str, str], int] = {}
        for roi in rois:
            shard = shard_of(roi, shards)
            self.assertIn(shard, range(shards))
            self.assertEqual(seen.setdefault((roi.document_id, roi.condition_id), shard), shard)
        self.assertEqual(len(seen), 24)
        self.assertGreater(len(set(seen.values())), 1)
        assigned = sum(sum(shard_of(r, shards) == s for r in rois) for s in range(shards))
        self.assertEqual(assigned, len(rois))
        with self.assertRaises(ValueError):
            shard_of(rois[0], 0)
        self.assertNotEqual(capture_key(rois[0]), capture_key(_roi("d1", "z", 0)))

    def test_frozen_files_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            split = root / "split.json"
            split.write_text(
                json.dumps({"split_version": "v", "assignment_sha256": "abc", "assignments": {"d1": "train"}}),
                encoding="utf-8",
            )
            excluded = root / "ex.json"
            excluded.write_text(json.dumps({"sample_ids": ["a", "b"]}), encoding="utf-8")
            self.assertEqual(load_frozen_split(split), ({"d1": "train"}, "v", "abc"))
            self.assertEqual(load_excluded_sample_ids(excluded), {"a", "b"})

    def test_repository_frozen_files_are_consistent(self):
        evidence = Path(__file__).resolve().parents[1] / "evidence"
        assignments, version, digest = load_frozen_split(evidence / "shdocs_document_split_v1.json")
        self.assertEqual(version, "shdocs-document-v1")
        self.assertEqual(len(assignments), 50)
        self.assertEqual(sorted({v for v in assignments.values()}), ["test", "train", "val"])
        self.assertEqual(sum(v == "test" for v in assignments.values()), 7)
        self.assertEqual(len(load_excluded_sample_ids(evidence / "shdocs_excluded_rois_v1.json")), 17)
        self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
