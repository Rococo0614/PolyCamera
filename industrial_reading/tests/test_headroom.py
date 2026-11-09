import unittest

import numpy as np

from polread.headroom import (
    SuccessMatrix,
    build_success_matrix,
    cluster_bootstrap,
    fixed_and_oracle,
    headroom_with_ci,
    paired_delta_with_ci,
    selection_floor,
    split_by_group,
    train_best,
)
from polread.records import OCRRecord


def _record(sample, group, split, method, truth, prediction, condition="a"):
    return OCRRecord(
        sample_id=sample,
        group_id=group,
        split=split,
        method_id=method,
        ocr_backend="fake",
        ground_truth=truth,
        prediction=prediction,
        condition_id=condition,
    )


def _matrix(success, splits, groups=None, methods=("m0", "m1", "m2")):
    success = np.asarray(success, dtype=bool)
    count = success.shape[0]
    return SuccessMatrix(
        sample_ids=tuple(f"s{i}" for i in range(count)),
        groups=tuple(groups or [f"g{i % 4}" for i in range(count)]),
        splits=tuple(splits),
        conditions=tuple("a" for _ in range(count)),
        methods=tuple(methods),
        success=success,
        cer=np.where(success, 0.0, 0.5),
    )


class BuildMatrixTests(unittest.TestCase):
    def test_pivot_and_incomplete_samples_dropped(self):
        records = [
            _record("s1", "g1", "train", "m0", "AB", "AB"),
            _record("s1", "g1", "train", "m1", "AB", "AC"),
            _record("s2", "g2", "test", "m0", "XY", "XY"),  # m1 missing -> dropped
        ]
        matrix = build_success_matrix(records, ["m0", "m1"])
        self.assertEqual(matrix.sample_ids, ("s1",))
        self.assertEqual(matrix.success.tolist(), [[True, False]])
        self.assertEqual(matrix.splits, ("train",))
        self.assertAlmostEqual(float(matrix.cer[0, 1]), 0.5)

    def test_error_records_make_the_sample_incomplete(self):
        bad = OCRRecord("s1", "g", "test", "m1", "fake", "A", "A", status="error")
        records = [_record("s1", "g", "test", "m0", "A", "A"), bad]
        self.assertEqual(build_success_matrix(records, ["m0", "m1"]).sample_ids, ())

    def test_errors_can_be_counted_as_failed_reads_instead_of_dropping_the_sample(self):
        bad = OCRRecord("s1", "g", "test", "m1", "fake", "AB", "AB", status="error", error="boom")
        records = [_record("s1", "g", "test", "m0", "AB", "AB"), bad]
        kept = build_success_matrix(records, ["m0", "m1"], errors_as_failures=True)
        self.assertEqual(kept.sample_ids, ("s1",))
        self.assertEqual(kept.success.tolist(), [[True, False]])  # error text is never scored
        self.assertAlmostEqual(float(kept.cer[0, 1]), 1.0)
        # default behaviour is unchanged
        self.assertEqual(build_success_matrix(records, ["m0", "m1"]).sample_ids, ())

    def test_rejected_counts_as_failure(self):
        record = OCRRecord("s1", "g", "test", "m0", "fake", "A", "A", rejected=True)
        self.assertFalse(bool(build_success_matrix([record], ["m0"]).success[0, 0]))


class FixedOracleTests(unittest.TestCase):
    def setUp(self):
        # train: m0 wins; test: m1 and m2 each rescue samples m0 misses
        self.success = [
            [1, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 0],  # train
            [1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0],  # test
        ]
        self.splits = ["train"] * 4 + ["test"] * 4
        self.matrix = _matrix(self.success, self.splits)
        self.rows = np.ones(8, dtype=bool)

    def test_train_best_uses_only_train(self):
        self.assertEqual(train_best(self.matrix, ["m0", "m1", "m2"], rows=self.rows), "m0")
        flipped = _matrix([[0, 1, 0]] * 4 + self.success[4:], self.splits)
        self.assertEqual(train_best(flipped, ["m0", "m1", "m2"], rows=self.rows), "m1")

    def test_headroom_equals_oracle_minus_fixed(self):
        result = fixed_and_oracle(self.matrix, ["m0", "m1", "m2"], rows=self.rows)
        self.assertEqual(result["train_best"], "m0")
        self.assertAlmostEqual(result["fixed_exact"], 0.25)
        self.assertAlmostEqual(result["oracle_exact"], 0.75)
        self.assertAlmostEqual(result["headroom"], 0.5)
        self.assertEqual(result["samples"], 4)

    def test_oracle_never_below_fixed_and_monotone_in_candidates(self):
        small = fixed_and_oracle(self.matrix, ["m0", "m1"], rows=self.rows)
        large = fixed_and_oracle(self.matrix, ["m0", "m1", "m2"], rows=self.rows)
        for result in (small, large):
            self.assertGreaterEqual(result["oracle_exact"], result["fixed_exact"])
        self.assertGreaterEqual(large["oracle_exact"], small["oracle_exact"])

    def test_row_mask_restricts_both_train_and_test(self):
        rows = np.array([True, True, True, True, True, True, False, False])
        result = fixed_and_oracle(self.matrix, ["m0", "m1", "m2"], rows=rows)
        self.assertEqual(result["samples"], 2)
        self.assertAlmostEqual(result["oracle_exact"], 1.0)

    def test_no_train_rows_raises(self):
        with self.assertRaises(ValueError):
            train_best(self.matrix, ["m0"], rows=np.array([False] * 4 + [True] * 4))


class BootstrapTests(unittest.TestCase):
    def test_interval_brackets_point_and_is_reproducible(self):
        rng = np.random.default_rng(0)
        success = rng.random((400, 3)) < np.array([0.4, 0.2, 0.2])
        splits = ["train"] * 200 + ["test"] * 200
        groups = [f"g{i % 20}" for i in range(400)]
        matrix = _matrix(success, splits, groups)
        rows = np.ones(400, dtype=bool)
        first = headroom_with_ci(matrix, ["m0", "m1", "m2"], rows=rows, iterations=300)
        again = headroom_with_ci(matrix, ["m0", "m1", "m2"], rows=rows, iterations=300)
        self.assertEqual(first["headroom_ci95"], again["headroom_ci95"])
        low, high = first["headroom_ci95"]
        self.assertLessEqual(low, first["headroom"])
        self.assertGreaterEqual(high, first["headroom"])
        self.assertEqual(first["groups"], 20)

    def test_cluster_bootstrap_widens_with_group_dependence(self):
        values = {f"g{i}": np.full(10, float(i % 2)) for i in range(10)}  # fully clustered
        low, high = cluster_bootstrap(values, lambda stacked: float(stacked.mean()), iterations=400)
        independent = {f"g{i}": np.array([float(i % 2)]) for i in range(100)}
        low_i, high_i = cluster_bootstrap(independent, lambda stacked: float(stacked.mean()), iterations=400)
        self.assertGreater(high - low, high_i - low_i)

    def test_paired_delta(self):
        success = [[1, 0, 0]] * 6 + [[0, 1, 0]] * 2
        matrix = _matrix(success, ["test"] * 8, [f"g{i % 4}" for i in range(8)])
        result = paired_delta_with_ci(matrix, "m0", "m1", rows=np.ones(8, dtype=bool), iterations=200)
        self.assertAlmostEqual(result["delta_exact_a_minus_b"], 0.75 - 0.25)
        self.assertEqual(result["groups"], 4)

    def test_split_by_group_covers_masked_rows_once(self):
        matrix = _matrix([[1, 0, 0]] * 6, ["test"] * 6, ["a", "a", "b", "b", "c", "c"])
        buckets = split_by_group(matrix, np.array([True, True, True, False, True, True]))
        self.assertEqual(sorted(sum((list(v) for v in buckets.values()), [])), [0, 1, 2, 4, 5])


class SelectionFloorTests(unittest.TestCase):
    def test_iid_noise_views_have_positive_floor_growing_with_views(self):
        rng = np.random.default_rng(1)
        content = rng.random(3000) < 0.5  # every view succeeds w.p. 0.3/0.7 depending on content
        views = np.stack([rng.random(3000) < np.where(content, 0.7, 0.2) for _ in range(12)], axis=1)
        four = selection_floor(views, view_count=4, permutations=100)
        twelve = selection_floor(views, view_count=12, permutations=100)
        self.assertGreater(four["mean_gain"], 0.02)
        self.assertGreater(twelve["mean_gain"], four["mean_gain"])

    def test_identical_views_have_zero_floor(self):
        column = np.random.default_rng(2).random(500) < 0.4
        views = np.tile(column[:, None], (1, 6))
        self.assertEqual(selection_floor(views, view_count=4)["mean_gain"], 0.0)

    def test_view_count_bounds(self):
        with self.assertRaises(ValueError):
            selection_floor(np.zeros((5, 3), dtype=bool), view_count=4)


if __name__ == "__main__":
    unittest.main()
