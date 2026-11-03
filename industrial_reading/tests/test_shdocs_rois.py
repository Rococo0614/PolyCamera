import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from polread.shdocs_rois import crop_roi, discover_annotated_rois, load_representation


class SHDocsROITests(unittest.TestCase):
    def test_discovery_and_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / "images"
            annotations = root / "annotations"
            capture = images / "doc1_a"
            capture.mkdir(parents=True)
            annotations.mkdir()
            values = {"i0": 70, "i45": 60, "i90": 30, "i135": 40}
            for name, value in values.items():
                Image.fromarray(np.full((20, 30), value, dtype=np.uint8)).save(
                    capture / f"{name}.png"
                )
            Image.fromarray(np.full((20, 30), 50, dtype=np.uint8)).save(
                capture / "s0_norm.png"
            )
            Image.fromarray(np.full((20, 30), 45, dtype=np.uint8)).save(
                capture / "deglared.png"
            )
            (annotations / "doc1.json").write_text(
                json.dumps({"form": [{"text": "AB12", "box": [2, 3, 12, 10]}]}),
                encoding="utf-8",
            )
            rois = discover_annotated_rois(images, annotations, conditions=("a",))
            self.assertEqual(len(rois), 1)
            self.assertEqual(rois[0].document_id, "doc1")
            self.assertEqual(rois[0].annotation_label, "unknown")
            virtual = load_representation(capture, "virtual_0")
            self.assertTrue(np.all(virtual == 70))
            cropped = crop_roi(virtual, rois[0].box, minimum_size=16)
            self.assertEqual(cropped.shape, (16, 16))

    def test_method_major_processed_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / "images"
            annotations = root / "annotations"
            annotations.mkdir(parents=True)
            values = {
                "i0": 70,
                "i45": 60,
                "i90": 30,
                "i135": 40,
                "s0_norm": 50,
                "deglared": 45,
            }
            for method, value in values.items():
                folder = images / method
                folder.mkdir(parents=True)
                Image.fromarray(np.full((20, 30), value, dtype=np.uint8)).save(
                    folder / "doc1_a.png"
                )
            (annotations / "doc1.json").write_text(
                json.dumps({"form": [{"text": "AB12", "box": [2, 3, 12, 10]}]}),
                encoding="utf-8",
            )
            rois = discover_annotated_rois(images, annotations, conditions=("a",))
            self.assertEqual(len(rois), 1)
            self.assertTrue(np.all(load_representation(rois[0].capture_dir, "i45") == 60))
            self.assertTrue(np.all(load_representation(rois[0].capture_dir, "virtual_0") == 70))


if __name__ == "__main__":
    unittest.main()
