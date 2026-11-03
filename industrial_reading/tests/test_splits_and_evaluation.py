import tempfile
import unittest
from pathlib import Path

from polread.evaluation import (
    complementary_success_diagnostics,
    confidence_selector_summary,
    oracle_exact_rate,
    paired_group_bootstrap_exact_delta,
    paired_group_bootstrap_oracle_delta,
    select_train_best,
)
from polread.records import OCRRecord, read_jsonl, write_jsonl
from polread.splits import assert_group_isolation, grouped_split


class SplitAndEvaluationTests(unittest.TestCase):
    def test_group_split_is_deterministic_and_isolated(self):
        groups = [f"doc-{index}" for index in range(20)]
        first = grouped_split(groups, seed=8)
        second = grouped_split(reversed(groups), seed=8)
        self.assertEqual(first, second)
        sample_groups = {f"sample-{i}": group for i, group in enumerate(groups)}
        sample_splits = {sample: first[group] for sample, group in sample_groups.items()}
        assert_group_isolation(sample_splits, sample_groups)

    def test_records_train_best_and_oracle(self):
        records = []
        for split, sample, group, truth, predictions in (
            ("train", "a", "g1", "AB", {"i0": "AB", "i45": "AX"}),
            ("train", "b", "g2", "CD", {"i0": "CD", "i45": "XX"}),
            ("test", "c", "g3", "EF", {"i0": "EX", "i45": "EF"}),
            ("test", "d", "g4", "GH", {"i0": "GH", "i45": "GX"}),
        ):
            for method, prediction in predictions.items():
                records.append(
                    OCRRecord(
                        sample_id=sample,
                        group_id=group,
                        split=split,
                        method_id=method,
                        ocr_backend="test",
                        ground_truth=truth,
                        prediction=prediction,
                    )
                )
        self.assertEqual(select_train_best(records, {"i0", "i45"}), "i0")
        oracle = oracle_exact_rate(records, {"i0", "i45"})
        self.assertEqual(oracle["normalized_exact_read"], 1.0)
        complementarity = complementary_success_diagnostics(records, {"i0", "i45"})
        self.assertEqual(complementarity["exactly_one_success_samples"], 2)
        self.assertEqual(complementarity["all_fail_samples"], 0)
        confidence = confidence_selector_summary(records, {"i0", "i45"})
        self.assertEqual(confidence["samples"], 2)
        interval = paired_group_bootstrap_exact_delta(
            records, "i45", "i0", iterations=100, seed=3
        )
        self.assertEqual(interval["paired_samples"], 2)
        oracle_interval = paired_group_bootstrap_oracle_delta(
            records, "i0", {"i0", "i45"}, iterations=100, seed=3
        )
        self.assertEqual(oracle_interval["oracle_only_successes"], 1)
        self.assertEqual(oracle_interval["fixed_only_successes"], 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            write_jsonl(records, path)
            self.assertEqual(read_jsonl(path), records)


if __name__ == "__main__":
    unittest.main()
