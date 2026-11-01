import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_support_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_support_masks.py"
    spec = importlib.util.spec_from_file_location("build_support_masks", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SupportMaskTests(unittest.TestCase):
    def test_depth_files_ignore_unpaired_archive_artifacts(self):
        module = load_support_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trajectory = root / "scene2_traj2_1"
            ground_truth = trajectory / "_gt" / "000000.png"
            paired = trajectory / "depth_d435" / "000000.png"
            malformed = trajectory / "depth_d435" / "{06d}.png"
            for path in (ground_truth, paired, malformed):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            files, ignored = module.depth_files(root, "depth_d435")

            self.assertEqual(files, [paired])
            self.assertEqual(ignored, [malformed])


if __name__ == "__main__":
    unittest.main()
