import unittest

import numpy as np

from polread.analysis import (
    GainSample,
    bracket_doses,
    clean_base_gain_sample,
    cluster_mean_ci,
    contrast_with_ci,
    exact_delta_with_ci,
    exact_rate_by_view,
    exchangeable_gain_sample,
    fixed_gain_sample,
    outcome_agreement,
    summarize_gain,
)
from polread.headroom import SuccessMatrix, headroom_with_ci, paired_delta_with_ci, selection_floor


def _matrix(success, splits, groups=None, methods=None):
    success = np.asarray(success, dtype=bool)
    count, width = success.shape
    return SuccessMatrix(
        sample_ids=tuple(f"s{i}" for i in range(count)),
        groups=tuple(groups or [f"g{i % 5}" for i in range(count)]),
        splits=tuple(splits),
        conditions=tuple("a" for _ in range(count)),
        methods=tuple(methods or [f"m{j}" for j in range(width)]),
        success=success,
        cer=np.where(success, 0.0, 0.5),
    )


class FixedGainTests(unittest.TestCase):
    def setUp(self):
        # train: m0 wins; test: m1 and m2 each rescue one sample m0 misses
        self.success = [
            [1, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 0],  # train
            [1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0],  # test
        ]
        self.matrix = _matrix(self.success, ["train"] * 4 + ["test"] * 4)
        self.rows = np.ones(8, dtype=bool)

    def test_gain_is_oracle_minus_fixed_and_binary(self):
        sample = fixed_gain_sample(self.matrix, ["m0", "m1", "m2"], rows=self.rows)
        self.assertEqual(sample.chosen, "m0")
        self.assertEqual(sorted(set(sample.values.tolist())), [0.0, 1.0])
        self.assertAlmostEqual(float(sample.values.mean()), 0.5)
        self.assertAlmostEqual(sample.single_exact, 0.25)
        self.assertAlmostEqual(sample.any_exact, 0.75)
        self.assertEqual(sample.indices.tolist(), [4, 5, 6, 7])

    def test_selection_uses_train_only(self):
        flipped = _matrix([[0, 1, 0]] * 4 + self.success[4:], ["train"] * 4 + ["test"] * 4)
        sample = fixed_gain_sample(flipped, ["m0", "m1", "m2"], rows=self.rows)
        self.assertEqual(sample.chosen, "m1")
        self.assertAlmostEqual(sample.single_exact, 0.25)  # m1 on the test rows

    def test_validation_split_can_be_evaluated(self):
        matrix = _matrix(self.success, ["train"] * 4 + ["val"] * 4)
        sample = fixed_gain_sample(matrix, ["m0", "m1"], rows=self.rows, split="val")
        self.assertEqual(sample.indices.tolist(), [4, 5, 6, 7])
        with self.assertRaises(ValueError):
            fixed_gain_sample(matrix, ["m0", "m1"], rows=self.rows)  # no test rows

    def test_duplicate_or_empty_candidates_rejected(self):
        with self.assertRaises(ValueError):
            fixed_gain_sample(self.matrix, ["m0", "m0"], rows=self.rows)
        with self.assertRaises(ValueError):
            fixed_gain_sample(self.matrix, [], rows=self.rows)

    def test_matches_headroom_with_ci(self):
        rng = np.random.default_rng(7)
        success = rng.random((600, 4)) < np.array([0.4, 0.25, 0.2, 0.3])
        matrix = _matrix(
            success, ["train"] * 300 + ["test"] * 300, [f"g{i % 30}" for i in range(600)]
        )
        rows = np.ones(600, dtype=bool)
        names = ["m0", "m1", "m2", "m3"]
        reference = headroom_with_ci(matrix, names, rows=rows, iterations=400)
        summary = summarize_gain(
            matrix, fixed_gain_sample(matrix, names, rows=rows), iterations=400
        )
        self.assertEqual(summary["train_best"], reference["train_best"])
        self.assertAlmostEqual(summary["gain"], reference["headroom"], places=12)
        self.assertAlmostEqual(summary["single_exact"], reference["fixed_exact"], places=12)
        self.assertAlmostEqual(summary["oracle_exact"], reference["oracle_exact"], places=12)
        self.assertAlmostEqual(summary["gain_ci95"][0], reference["headroom_ci95"][0], places=12)
        self.assertAlmostEqual(summary["gain_ci95"][1], reference["headroom_ci95"][1], places=12)
        self.assertEqual(summary["groups"], reference["groups"])


class ExchangeableGainTests(unittest.TestCase):
    def test_identical_views_have_no_selection_gain(self):
        column = np.random.default_rng(3).random(300) < 0.4
        matrix = _matrix(np.tile(column[:, None], (1, 4)), ["test"] * 300)
        sample = exchangeable_gain_sample(matrix, ["m0", "m1", "m2", "m3"], rows=np.ones(300, bool))
        self.assertTrue(np.all(sample.values == 0.0))
        self.assertIsNone(sample.chosen)
        self.assertAlmostEqual(sample.single_exact, float(column.mean()))

    def test_independent_redraws_gain_and_agree_with_selection_floor(self):
        rng = np.random.default_rng(4)
        content = rng.random(4000) < 0.5
        success = np.stack(
            [rng.random(4000) < np.where(content, 0.6, 0.15) for _ in range(4)], axis=1
        )
        matrix = _matrix(success, ["test"] * 4000)
        rows = np.ones(4000, dtype=bool)
        sample = exchangeable_gain_sample(matrix, list(matrix.methods), rows=rows)
        self.assertGreater(float(sample.values.mean()), 0.05)
        self.assertTrue(np.all(sample.values >= 0.0))
        self.assertTrue(np.all(sample.values < 1.0))
        floor = selection_floor(success, view_count=4, permutations=400)["mean_gain"]
        self.assertAlmostEqual(float(sample.values.mean()), floor, delta=0.01)

    def test_gain_is_oracle_minus_the_mean_not_the_first_column(self):
        # one sample read by 1 of 4 views (first), one by none, one by 3 of 4 (not the first)
        success = np.array([[1, 0, 0, 0], [0, 0, 0, 0], [0, 1, 1, 1]], dtype=bool)
        matrix = _matrix(success, ["test"] * 3)
        sample = exchangeable_gain_sample(matrix, list(matrix.methods), rows=np.ones(3, bool))
        self.assertEqual(sample.values.tolist(), [0.75, 0.0, 0.25])
        self.assertAlmostEqual(sample.single_exact, 4 / 12)
        self.assertAlmostEqual(sample.any_exact, 2 / 3)

    def test_needs_two_views(self):
        matrix = _matrix([[1, 0]] * 4, ["test"] * 4)
        with self.assertRaises(ValueError):
            exchangeable_gain_sample(matrix, ["m0"], rows=np.ones(4, bool))

    def test_gain_never_negative_and_grows_with_more_views(self):
        rng = np.random.default_rng(5)
        success = rng.random((1500, 8)) < 0.3
        matrix = _matrix(success, ["test"] * 1500)
        rows = np.ones(1500, dtype=bool)
        two = exchangeable_gain_sample(matrix, ["m0", "m1"], rows=rows)
        eight = exchangeable_gain_sample(matrix, list(matrix.methods), rows=rows)
        self.assertGreater(float(eight.values.mean()), float(two.values.mean()))


class CleanBaseGainTests(unittest.TestCase):
    METHODS = ("base", "n0", "n1", "n2", "n3")

    def _matrix(self, success):
        return _matrix(success, ["test"] * len(success), methods=self.METHODS)

    def test_copies_identical_to_the_base_give_zero_gain(self):
        column = np.random.default_rng(10).random(200) < 0.3
        matrix = self._matrix(np.tile(column[:, None], (1, 5)))
        sample = clean_base_gain_sample(
            matrix, "base", ["n0", "n1", "n2", "n3"], rows=np.ones(200, bool)
        )
        self.assertTrue(np.all(sample.values == 0.0))
        self.assertEqual(sample.chosen, "base")

    def test_always_correct_copies_rescue_every_base_failure(self):
        base = np.array([1, 0, 0, 1, 0], dtype=bool)
        success = np.column_stack([base] + [np.ones(5, dtype=bool)] * 4)
        sample = clean_base_gain_sample(
            self._matrix(success), "base", ["n0", "n1", "n2", "n3"], rows=np.ones(5, bool)
        )
        self.assertEqual(sample.values.tolist(), [0.0, 1.0, 1.0, 0.0, 1.0])
        self.assertAlmostEqual(sample.single_exact, 0.4)
        self.assertAlmostEqual(sample.any_exact, 1.0)

    def test_average_over_subsets_is_the_fraction_of_triples_containing_a_rescuer(self):
        # base fails; only n2 reads -> 3 of the 4 triples of 4 re-draws contain n2
        success = np.array([[0, 0, 0, 1, 0]], dtype=bool)
        sample = clean_base_gain_sample(
            self._matrix(success), "base", ["n0", "n1", "n2", "n3"], rows=np.ones(1, bool)
        )
        self.assertAlmostEqual(float(sample.values[0]), 0.75)

    def test_alternatives_parameter_changes_the_subset_size(self):
        success = np.array([[0, 0, 0, 1, 0]], dtype=bool)
        matrix = self._matrix(success)
        names = ["n0", "n1", "n2", "n3"]
        one = clean_base_gain_sample(matrix, "base", names, alternatives=1, rows=np.ones(1, bool))
        four = clean_base_gain_sample(matrix, "base", names, alternatives=4, rows=np.ones(1, bool))
        self.assertAlmostEqual(float(one.values[0]), 0.25)
        self.assertAlmostEqual(float(four.values[0]), 1.0)

    def test_gain_grows_with_independent_redraw_instability(self):
        rng = np.random.default_rng(11)
        content = rng.random(3000) < 0.5
        base = rng.random(3000) < np.where(content, 0.6, 0.15)
        stable = np.column_stack([base] * 5)
        unstable = np.column_stack(
            [base] + [rng.random(3000) < np.where(content, 0.6, 0.15) for _ in range(4)]
        )
        rows = np.ones(3000, bool)
        names = ["n0", "n1", "n2", "n3"]
        low = clean_base_gain_sample(self._matrix(stable), "base", names, rows=rows)
        high = clean_base_gain_sample(self._matrix(unstable), "base", names, rows=rows)
        self.assertEqual(float(low.values.mean()), 0.0)
        self.assertGreater(float(high.values.mean()), 0.05)
        self.assertTrue(np.all(high.values >= 0.0))

    def test_input_validation(self):
        matrix = self._matrix(np.zeros((3, 5), dtype=bool))
        rows = np.ones(3, bool)
        with self.assertRaises(ValueError):
            clean_base_gain_sample(matrix, "base", ["n0", "n1"], alternatives=3, rows=rows)
        with self.assertRaises(ValueError):
            clean_base_gain_sample(matrix, "base", ["base", "n0", "n1"], rows=rows)
        with self.assertRaises(ValueError):
            clean_base_gain_sample(matrix, "base", ["n0", "n1", "n2"], alternatives=0, rows=rows)

    def test_contrastable_with_the_real_fixed_gain(self):
        rng = np.random.default_rng(12)
        success = rng.random((400, 5)) < 0.3
        matrix = _matrix(
            success, ["train"] * 200 + ["test"] * 200, [f"g{i % 20}" for i in range(400)],
            methods=self.METHODS,
        )
        rows = np.ones(400, bool)
        real = fixed_gain_sample(matrix, ["base", "n0", "n1", "n2"], rows=rows, label="real")
        null = clean_base_gain_sample(matrix, "base", ["n0", "n1", "n2", "n3"], rows=rows, label="null")
        result = contrast_with_ci(matrix, real, null, iterations=200)
        self.assertEqual(result["samples"], 200)


class ContrastAndIntervalTests(unittest.TestCase):
    def test_cluster_mean_ci_reproducible_and_brackets_mean(self):
        groups = [f"g{i % 10}" for i in range(200)]
        values = np.random.default_rng(1).random(200)
        first = cluster_mean_ci(groups, values, iterations=300)
        again = cluster_mean_ci(groups, values, iterations=300)
        self.assertEqual(first, again)
        self.assertLessEqual(first["ci95"][0], first["mean"])
        self.assertGreaterEqual(first["ci95"][1], first["mean"])
        self.assertEqual(first["groups"], 10)
        self.assertEqual(first["samples"], 200)

    def test_cluster_mean_ci_input_validation(self):
        with self.assertRaises(ValueError):
            cluster_mean_ci(["a", "b"], np.array([1.0]))
        with self.assertRaises(ValueError):
            cluster_mean_ci([], np.array([]))
        with self.assertRaises(ValueError):
            cluster_mean_ci(["a"], np.zeros((1, 2)))

    def test_contrast_is_difference_of_gains(self):
        rng = np.random.default_rng(6)
        success = rng.random((500, 8)) < 0.3
        splits = ["train"] * 250 + ["test"] * 250
        matrix = _matrix(success, splits, [f"g{i % 25}" for i in range(500)])
        rows = np.ones(500, dtype=bool)
        real = fixed_gain_sample(matrix, ["m0", "m1", "m2", "m3"], rows=rows, label="real")
        null = exchangeable_gain_sample(matrix, ["m4", "m5", "m6", "m7"], rows=rows, label="null")
        result = contrast_with_ci(matrix, real, null, iterations=300)
        self.assertAlmostEqual(
            result["delta_gain"], float(real.values.mean() - null.values.mean()), places=12
        )
        self.assertEqual((result["first"], result["second"]), ("real", "null"))
        self.assertLessEqual(result["ci95"][0], result["delta_gain"])
        self.assertGreaterEqual(result["ci95"][1], result["delta_gain"])

    def test_contrast_of_a_sample_with_itself_is_exactly_zero(self):
        matrix = _matrix(np.random.default_rng(8).random((100, 3)) < 0.4, ["train"] * 50 + ["test"] * 50)
        sample = fixed_gain_sample(matrix, ["m0", "m1", "m2"], rows=np.ones(100, bool))
        result = contrast_with_ci(matrix, sample, sample, iterations=100)
        self.assertEqual(result["delta_gain"], 0.0)
        self.assertEqual(result["ci95"], [0.0, 0.0])

    def test_contrast_requires_identical_rows(self):
        matrix = _matrix(np.random.default_rng(9).random((60, 3)) < 0.4, ["train"] * 30 + ["test"] * 30)
        everything = np.ones(60, dtype=bool)
        drop_first = everything.copy()
        drop_first[30:35] = False  # 25 test samples, but not the same 25
        drop_last = everything.copy()
        drop_last[55:60] = False
        one = fixed_gain_sample(matrix, ["m0", "m1"], rows=drop_first)
        two = fixed_gain_sample(matrix, ["m0", "m1"], rows=drop_last)
        self.assertEqual(len(one.indices), len(two.indices))  # same length: only the guard can catch it
        with self.assertRaisesRegex(ValueError, "identical samples"):
            contrast_with_ci(matrix, one, two)
        # different lengths are rejected as well, with the same message rather than a broadcast error
        short = fixed_gain_sample(matrix, ["m0", "m1"], rows=everything)
        with self.assertRaisesRegex(ValueError, "identical samples"):
            contrast_with_ci(matrix, short, one)

    def test_gain_sample_is_immutable_container(self):
        sample = GainSample("x", np.arange(2), np.zeros(2), ("a",), None, 0.0, 0.0)
        with self.assertRaises(Exception):
            sample.label = "y"  # type: ignore[misc]


class SplitAndDeltaTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(13)
        success = rng.random((600, 3)) < np.array([0.5, 0.3, 0.2])
        self.matrix = _matrix(
            success,
            ["train"] * 300 + ["val"] * 100 + ["test"] * 200,
            [f"g{i % 30}" for i in range(600)],
        )
        self.rows = np.ones(600, bool)

    def test_split_none_evaluates_every_selected_row_but_selects_on_train(self):
        pooled = fixed_gain_sample(self.matrix, ["m0", "m1", "m2"], rows=self.rows, split=None)
        held_out = fixed_gain_sample(self.matrix, ["m0", "m1", "m2"], rows=self.rows)
        self.assertEqual(len(pooled.indices), 600)
        self.assertEqual(len(held_out.indices), 200)
        self.assertEqual(pooled.chosen, held_out.chosen)  # train-only selection either way

    def test_split_none_respects_the_row_mask(self):
        rows = self.rows.copy()
        rows[:100] = False
        sample = exchangeable_gain_sample(self.matrix, ["m0", "m1"], rows=rows, split=None)
        self.assertEqual(len(sample.indices), 500)
        self.assertEqual(int(sample.indices.min()), 100)

    def test_val_split_selectable(self):
        sample = fixed_gain_sample(self.matrix, ["m0", "m1"], rows=self.rows, split="val")
        self.assertEqual(len(sample.indices), 100)

    def test_exact_delta_matches_paired_delta_with_ci(self):
        reference = paired_delta_with_ci(self.matrix, "m0", "m1", rows=self.rows, iterations=300)
        result = exact_delta_with_ci(self.matrix, "m0", "m1", rows=self.rows, iterations=300)
        self.assertAlmostEqual(result["delta_exact_a_minus_b"], reference["delta_exact_a_minus_b"], places=12)
        self.assertAlmostEqual(result["ci95"][0], reference["ci95"][0], places=12)
        self.assertAlmostEqual(result["ci95"][1], reference["ci95"][1], places=12)
        self.assertEqual(result["groups"], reference["groups"])

    def test_exact_delta_over_all_rows_uses_more_samples_and_narrower_interval(self):
        test_only = exact_delta_with_ci(self.matrix, "m0", "m1", rows=self.rows, iterations=300)
        pooled = exact_delta_with_ci(self.matrix, "m0", "m1", rows=self.rows, split=None, iterations=300)
        self.assertEqual((test_only["samples"], pooled["samples"]), (200, 600))
        self.assertLess(pooled["ci95"][1] - pooled["ci95"][0], test_only["ci95"][1] - test_only["ci95"][0])


class BracketDosesTests(unittest.TestCase):
    RISING = [(0.25, 1.8), (0.5, 3.6), (0.75, 5.4), (1.0, 7.1), (1.5, 10.7)]  # pixel distance
    FALLING = [(0.25, 23.0), (0.5, 21.0), (0.75, 14.8), (1.0, 8.3), (1.5, 3.0)]  # exact rate

    def test_all_doses_inside_the_interval_are_returned(self):
        self.assertEqual(bracket_doses(self.RISING, 6.95, 9.70), [1.0])
        self.assertEqual(bracket_doses(self.RISING, 3.0, 8.0), [0.5, 0.75, 1.0])

    def test_interval_end_points_are_inside(self):
        points = [(1.0, 5.0), (2.0, 5.5), (3.0, 6.0), (4.0, 7.0)]
        self.assertEqual(bracket_doses(points, 5.0, 6.0), [1.0, 2.0, 3.0])

    def test_target_between_grid_points_is_bracketed_not_snapped(self):
        self.assertEqual(bracket_doses(self.FALLING, 17.8, 17.8), [0.5, 0.75])
        self.assertEqual(bracket_doses(self.RISING, 8.5, 9.0), [1.0, 1.5])

    def test_target_outside_the_grid_returns_the_single_available_side(self):
        self.assertEqual(bracket_doses(self.RISING, 12.0, 13.0), [1.5])
        self.assertEqual(bracket_doses(self.RISING, 0.5, 1.0), [0.25])

    def test_input_order_does_not_matter(self):
        shuffled = [self.FALLING[i] for i in (3, 0, 4, 2, 1)]
        self.assertEqual(bracket_doses(shuffled, 17.8, 17.8), [0.5, 0.75])

    def test_validation(self):
        with self.assertRaises(ValueError):
            bracket_doses([], 0.0, 1.0)
        with self.assertRaises(ValueError):
            bracket_doses(self.RISING, 2.0, 1.0)


class DescriptiveHelpersTests(unittest.TestCase):
    def test_exact_rate_by_view_uses_the_requested_split_only(self):
        matrix = _matrix([[1, 0], [1, 0], [0, 1], [1, 1]], ["train", "train", "test", "test"])
        rates = exact_rate_by_view(matrix, ["m0", "m1"], rows=np.ones(4, bool))
        self.assertEqual(rates, {"m0": 0.5, "m1": 1.0})

    def test_outcome_agreement_partitions_samples(self):
        matrix = _matrix([[1, 1], [1, 0], [0, 1], [0, 0], [1, 1]], ["test"] * 5)
        result = outcome_agreement(matrix, "m0", "m1", rows=np.ones(5, bool))
        self.assertAlmostEqual(result["both"], 0.4)
        self.assertAlmostEqual(result["only_first"], 0.2)
        self.assertAlmostEqual(result["only_second"], 0.2)
        self.assertAlmostEqual(result["neither"], 0.2)
        self.assertAlmostEqual(result["agreement"], 0.6)
        self.assertAlmostEqual(
            result["both"] + result["only_first"] + result["only_second"] + result["neither"], 1.0
        )
        self.assertEqual(result["samples"], 5)


if __name__ == "__main__":
    unittest.main()
