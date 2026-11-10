import unittest

import numpy as np

from polrep.physics import (
    analyze_stokes,
    demosaic_mpfa_bilinear,
    fresnel_reflection_unpolarized,
    make_mpfa_mosaic,
    rotate_reference,
    solve_stokes,
    stokes_from_intensity,
)


class PhysicsTests(unittest.TestCase):
    def test_ideal_round_trip(self):
        stokes = np.array([[2.0, 0.5, -0.25], [1.0, 0.0, 0.0]])
        np.testing.assert_allclose(solve_stokes(analyze_stokes(stokes)), stokes, atol=1e-12)

    def test_stokes_builder_has_requested_mean_intensity(self):
        intensity = np.array([[0.2, 0.7]])
        stokes = stokes_from_intensity(intensity, 0.5, 30.0)
        np.testing.assert_allclose(analyze_stokes(stokes).mean(axis=-1), intensity)

    def test_reference_rotation_matches_angle_shift(self):
        stokes = np.array([[2.0, 0.6, 0.2]])
        rotated = rotate_reference(stokes, 17.0)
        shifted_measurement = analyze_stokes(stokes, (17.0, 62.0, 107.0, 152.0))
        np.testing.assert_allclose(analyze_stokes(rotated), shifted_measurement, atol=1e-12)

    def test_mpfa_round_trip_preserves_constant_states(self):
        measurements = np.zeros((8, 10, 4), dtype=np.float64)
        measurements[...] = np.array([0.2, 0.4, 0.6, 0.8])
        reconstructed = demosaic_mpfa_bilinear(make_mpfa_mosaic(measurements))
        np.testing.assert_allclose(reconstructed, measurements)

    def test_fresnel_reflection_is_fully_polarized_at_brewster_angle(self):
        brewster = np.rad2deg(np.arctan(1.5))
        result = fresnel_reflection_unpolarized(brewster)
        self.assertAlmostEqual(float(result["reflected_dolp"]), 1.0, places=12)
        normal = fresnel_reflection_unpolarized(0.0)
        self.assertAlmostEqual(float(normal["reflected_dolp"]), 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
