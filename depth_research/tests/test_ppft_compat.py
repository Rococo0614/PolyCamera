import unittest


class PPFTCompatibilityTests(unittest.TestCase):
    def test_torchvision_dcn_shim_matches_regular_convolution_at_zero_offset(self):
        try:
            import torch
            import torch.nn.functional as functional
        except ImportError:
            self.skipTest("PyTorch is an optional baseline dependency")

        from poldepth.ppft_compat import _install_dcn_inference_shim

        _install_dcn_inference_shim()
        import DCN

        torch.manual_seed(7)
        image = torch.randn(2, 2, 9, 11)
        weight = torch.randn(3, 2, 3, 3)
        bias = torch.randn(3)
        offset = torch.zeros(2, 18, 9, 11)
        mask = torch.ones(2, 9, 9, 11)
        expected = functional.conv2d(image, weight, bias, padding=1)
        actual = DCN.modulated_deform_conv_forward(
            image,
            weight,
            bias,
            offset,
            mask,
            3,
            3,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            64,
        )
        self.assertTrue(torch.allclose(actual, expected, atol=1e-5, rtol=1e-5))


if __name__ == "__main__":
    unittest.main()
