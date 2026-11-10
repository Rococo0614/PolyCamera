import unittest

from polrep.simulation import SimulationConfig, score_simulation, simulate


class SimulationTests(unittest.TestCase):
    def test_ideal_stokes_recovery(self):
        score = score_simulation(simulate(SimulationConfig(0.05, 0.7), size=32))
        self.assertLess(score["stokes_rmse"], 1e-12)

    def test_fully_polarized_reflection_can_be_suppressed(self):
        score = score_simulation(simulate(SimulationConfig(0.4, 1.0), size=32))
        self.assertGreater(score["virtual_min_gain_db"], 0.0)

    def test_unpolarized_reflection_has_no_directional_solution(self):
        score = score_simulation(simulate(SimulationConfig(0.4, 0.0), size=32))
        self.assertAlmostEqual(score["virtual_min_gain_db"], 0.0, places=10)


if __name__ == "__main__":
    unittest.main()
