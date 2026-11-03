import unittest

import numpy as np

from polread.instrument import (
    estimate_affine_instrument,
    ideal_linear_instrument,
    solve_stokes,
)


class InstrumentTests(unittest.TestCase):
    def test_ideal_roundtrip(self):
        matrix = ideal_linear_instrument([0, 45, 90, 135])
        stokes = np.array([[10.0, 2.0, -1.0], [5.0, 0.0, 2.0]])
        measurements = stokes @ matrix.T
        recovered = solve_stokes(measurements, matrix)
        self.assertTrue(np.allclose(recovered, stokes))

    def test_affine_calibration(self):
        rng = np.random.default_rng(4)
        stokes = rng.normal(size=(100, 3))
        matrix = ideal_linear_instrument([2, 44, 92, 137])
        offsets = np.array([0.1, 0.2, 0.05, -0.1])
        measurements = stokes @ matrix.T + offsets
        estimated, estimated_offsets = estimate_affine_instrument(stokes, measurements)
        self.assertTrue(np.allclose(estimated, matrix))
        self.assertTrue(np.allclose(estimated_offsets, offsets))


if __name__ == "__main__":
    unittest.main()
