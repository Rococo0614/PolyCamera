import unittest

from polrep.polargb import capture_groups, frozen_scene_split, release_summary


def metadata_fixture():
    siblings = []
    for subset, side, scene, capture in (
        ("train/easy", "input", "00", "0000"),
        ("train/easy", "gt", "00", "0000"),
        ("test", "input", "10", "0000"),
        ("test", "gt", "10", "0000"),
    ):
        for index, kind in enumerate(("000", "045", "090", "135", "rgb")):
            siblings.append(
                {
                    "rfilename": f"{subset}/{side}/{scene}/{capture}_{kind}.png",
                    "size": 100 + index,
                    "lfs": {"sha256": f"{subset}-{side}-{scene}-{kind}"},
                }
            )
    return {"sha": "revision", "cardData": {"license": "test"}, "siblings": siblings}


class PolaRGBTests(unittest.TestCase):
    def test_groups_and_summary(self):
        metadata = metadata_fixture()
        self.assertEqual(len(capture_groups(metadata)), 4)
        summary = release_summary(metadata)
        self.assertEqual(summary["input_captures"], 2)
        self.assertEqual(summary["unique_train_scenes"], 1)
        self.assertEqual(summary["unique_test_scenes"], 1)

    def test_split_is_stable_and_disjoint(self):
        split = frozen_scene_split([f"{x:02d}" for x in range(12)], ["90", "91"], validation_scenes=3)
        self.assertEqual(split, frozen_scene_split([f"{x:02d}" for x in range(12)], ["90", "91"], validation_scenes=3))
        self.assertFalse(set(split["fit"]) & set(split["validation"]))
        self.assertIn("scene_id_namespaces", split)


if __name__ == "__main__":
    unittest.main()
