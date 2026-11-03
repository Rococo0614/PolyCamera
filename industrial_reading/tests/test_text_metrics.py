import unittest

from polread.text_metrics import (
    TextNormalization,
    evaluate_text,
    levenshtein_distance,
    normalize_text,
)


class TextMetricTests(unittest.TestCase):
    def test_levenshtein(self):
        self.assertEqual(levenshtein_distance("KIT", "SITTING"), 5)
        self.assertEqual(levenshtein_distance("ABC", "ADC"), 1)

    def test_explicit_normalization(self):
        config = TextNormalization(uppercase=True, whitespace="remove")
        self.assertEqual(normalize_text(" ab\n12 ", config), "AB12")
        metrics = evaluate_text("AB12", "ab 12", normalization=config)
        self.assertFalse(metrics["raw_exact_read"])
        self.assertTrue(metrics["normalized_exact_read"])
        self.assertEqual(metrics["cer"], 0.0)

    def test_no_dictionary_correction(self):
        metrics = evaluate_text("O0", "00")
        self.assertFalse(metrics["normalized_exact_read"])
        self.assertEqual(metrics["char_edits"], 1)


if __name__ == "__main__":
    unittest.main()
