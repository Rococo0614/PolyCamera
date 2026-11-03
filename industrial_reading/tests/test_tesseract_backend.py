import unittest

from polread.tesseract_backend import parse_tesseract_tsv


class TesseractBackendTests(unittest.TestCase):
    def test_tsv_parsing(self):
        tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        tsv += "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90.0\tLOT\n"
        tsv += "5\t1\t1\t1\t1\t2\t12\t0\t10\t10\t80.0\tA12\n"
        prediction = parse_tesseract_tsv(tsv)
        self.assertEqual(prediction.text, "LOT A12")
        self.assertAlmostEqual(prediction.confidence, 0.85)


if __name__ == "__main__":
    unittest.main()
