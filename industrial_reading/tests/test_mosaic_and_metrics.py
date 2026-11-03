import unittest

import numpy as np

from polread.mosaic import demosaic_bilinear, demosaic_nearest, make_mpfa_mosaic
from polread.polar_metrics import polarization_reconstruction_metrics


class MosaicAndMetricTests(unittest.TestCase):
    def test_constant_channels_roundtrip(self):
        channels = {
            "i0": np.full((8, 10), 0.7),
            "i45": np.full((8, 10), 0.6),
            "i90": np.full((8, 10), 0.3),
            "i135": np.full((8, 10), 0.4),
        }
        mosaic = make_mpfa_mosaic(channels)
        for reconstruction in (demosaic_nearest(mosaic), demosaic_bilinear(mosaic)):
            for key in channels:
                self.assertTrue(np.allclose(reconstruction[key], channels[key]))
            metrics = polarization_reconstruction_metrics(reconstruction, channels)
            self.assertAlmostEqual(metrics["intensity_mae"], 0.0)
            self.assertAlmostEqual(metrics["dolp_mae"], 0.0)
            self.assertAlmostEqual(metrics["aolp_mae_deg"], 0.0)

    def test_mosaic_pattern(self):
        channels = {
            "i0": np.full((4, 4), 0.0),
            "i45": np.full((4, 4), 45.0),
            "i90": np.full((4, 4), 90.0),
            "i135": np.full((4, 4), 135.0),
        }
        mosaic = make_mpfa_mosaic(channels)
        self.assertEqual(mosaic[0, 0], 90.0)
        self.assertEqual(mosaic[0, 1], 45.0)
        self.assertEqual(mosaic[1, 0], 135.0)
        self.assertEqual(mosaic[1, 1], 0.0)


if __name__ == "__main__":
    unittest.main()
