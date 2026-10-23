import unittest

import numpy as np

from poldepth.metrics import (
    binary_auroc,
    binary_average_precision,
    depth_boundary_mask,
    depth_metrics,
    erode_mask,
    observed_support_bbox_mask,
    silent_error_detection_metrics,
)


class DepthMetricTests(unittest.TestCase):
    def test_exact_prediction(self):
        gt = np.array([[1.0, 2.0], [3.0, 4.0]])
        result = depth_metrics(gt.copy(), gt, unit_scale=1000.0)
        self.assertEqual(result["rmse"], 0.0)
        self.assertEqual(result["mae"], 0.0)
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["delta_1"], 1.0)

    def test_missing_prediction_reduces_coverage(self):
        gt = np.ones((2, 2))
        prediction = np.array([[1.0, 0.0], [1.0, 0.0]])
        result = depth_metrics(prediction, gt)
        self.assertEqual(result["evaluated_pixels"], 2)
        self.assertEqual(result["coverage"], 0.5)
        self.assertEqual(result["rmse"], 0.0)

    def test_report_unit_scaling(self):
        gt = np.array([[1.0]])
        prediction = np.array([[1.1]])
        result = depth_metrics(prediction, gt, unit_scale=1000.0)
        self.assertAlmostEqual(result["mae"], 100.0)
        self.assertAlmostEqual(result["rmse"], 100.0)
        self.assertAlmostEqual(result["mean_signed_error"], 100.0)
        self.assertAlmostEqual(result["median_signed_error"], 100.0)
        self.assertEqual(result["positive_error_fraction"], 1.0)

    def test_depth_boundary_mask(self):
        gt = np.array([[1.0, 1.0, 2.0], [1.0, 1.0, 2.0]])
        mask = depth_boundary_mask(gt, threshold=0.5, dilation_radius=0)
        expected = np.array([[False, True, True], [False, True, True]])
        np.testing.assert_array_equal(mask, expected)

    def test_observed_support_bbox(self):
        depth = np.zeros((4, 5))
        depth[1:3, 2:4] = 1.0
        mask, bbox = observed_support_bbox_mask(depth)
        self.assertEqual(bbox, (2, 1, 3, 2))
        self.assertEqual(int(mask.sum()), 4)

    def test_erode_mask(self):
        mask = np.ones((5, 5), dtype=bool)
        eroded = erode_mask(mask, radius=1)
        self.assertEqual(int(eroded.sum()), 9)
        np.testing.assert_array_equal(eroded[1:4, 1:4], np.ones((3, 3), dtype=bool))

    def test_binary_ranking_metrics(self):
        target = np.array([False, False, True, True])
        perfect = np.array([0.1, 0.2, 0.8, 0.9])
        inverse = perfect[::-1]
        self.assertEqual(binary_auroc(target, perfect), 1.0)
        self.assertEqual(binary_average_precision(target, perfect), 1.0)
        self.assertEqual(binary_auroc(target, inverse), 0.0)
        tied_target = np.array([False, True])
        tied_score = np.array([0.5, 0.5])
        self.assertEqual(binary_auroc(tied_target, tied_score), 0.5)
        self.assertEqual(binary_average_precision(tied_target, tied_score), 0.5)

    def test_silent_error_detection(self):
        gt = np.ones((2, 2)) * 1000
        prediction = np.array([[1000, 1010], [1200, 1300]])
        score = np.array([[0.0, 0.1], [0.8, 0.9]])
        result = silent_error_detection_metrics(
            prediction, gt, score, error_threshold=50
        )
        self.assertEqual(result["positive_pixels"], 2)
        self.assertEqual(result["auroc"], 1.0)


if __name__ == "__main__":
    unittest.main()
