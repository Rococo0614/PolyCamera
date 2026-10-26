"""Compatibility helpers for running the public PPFT model on modern PyTorch.

The upstream CVPR 2024 code targets PyTorch 1.10, Apex, mmcv-full 1.4 and a
custom DCN extension.  This module keeps the upstream model definition and
checkpoint intact while replacing only import-time infrastructure needed for
single-GPU inference.  In particular, the old modulated deformable convolution
forward pass is mapped to :func:`torchvision.ops.deform_conv2d`.

The compatibility path is intentionally limited to inference.  It does not
pretend that the author's distributed/Apex training entry point is reproduced.
"""

from __future__ import annotations

import importlib
import logging
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any


UPSTREAM_COMMIT = "9b1145d87e50895fd17068fad9cec1199092f67a"


def _trusted_torch_load(path: str | Path) -> Any:
    """Load a trusted author checkpoint across old and new PyTorch releases."""

    import torch

    try:
        # PyTorch >=2.6 defaults to weights_only=True.  PPFT checkpoints also
        # contain an argparse Namespace, so an explicit trusted load is needed.
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:  # pragma: no cover - for older PyTorch only
        return torch.load(path, map_location="cpu")


def _install_dcn_inference_shim() -> None:
    """Expose the old ``DCN`` forward API through torchvision.

    The upstream custom autograd Function calls this API.  Its backward entry
    point is deliberately rejected: modern training needs a separately
    validated migration rather than silently using an untested gradient path.
    """

    if "DCN" in sys.modules:
        return

    import torch
    from torchvision.ops import deform_conv2d

    module = types.ModuleType("DCN")

    def forward(
        input_tensor,
        weight,
        bias,
        offset,
        mask,
        kernel_h,
        kernel_w,
        stride_h,
        stride_w,
        pad_h,
        pad_w,
        dilation_h,
        dilation_w,
        groups,
        deformable_groups,
        im2col_step,
    ):
        del im2col_step
        if tuple(weight.shape[-2:]) != (kernel_h, kernel_w):
            raise ValueError("DCN kernel metadata does not match its weight")
        inferred_groups = input_tensor.shape[1] // weight.shape[1]
        if inferred_groups != groups:
            raise ValueError(
                f"DCN groups mismatch: requested {groups}, inferred {inferred_groups}"
            )
        expected_offset_channels = 2 * deformable_groups * kernel_h * kernel_w
        expected_mask_channels = deformable_groups * kernel_h * kernel_w
        if offset.shape[1] != expected_offset_channels:
            raise ValueError(
                f"DCN offset has {offset.shape[1]} channels; "
                f"expected {expected_offset_channels}"
            )
        if mask.shape[1] != expected_mask_channels:
            raise ValueError(
                f"DCN mask has {mask.shape[1]} channels; "
                f"expected {expected_mask_channels}"
            )
        return deform_conv2d(
            input_tensor,
            offset,
            weight,
            bias,
            stride=(stride_h, stride_w),
            padding=(pad_h, pad_w),
            dilation=(dilation_h, dilation_w),
            mask=mask,
        )

    def backward(*_args, **_kwargs):
        raise RuntimeError(
            "The PPFT compatibility DCN shim is inference-only; "
            "a training backward pass has not been validated"
        )

    module.modulated_deform_conv_forward = forward
    module.modulated_deform_conv_backward = backward
    sys.modules["DCN"] = module


def _install_legacy_import_shims() -> None:
    """Provide the two legacy mmcv/mmseg imports used during model import."""

    import torch

    if "mmcv.runner" not in sys.modules:
        runner = types.ModuleType("mmcv.runner")

        def load_checkpoint(
            model,
            filename,
            map_location="cpu",
            strict=False,
            logger=None,
        ):
            del map_location, logger
            checkpoint = _trusted_torch_load(filename)
            state = checkpoint.get("state_dict", checkpoint.get("net", checkpoint))
            return model.load_state_dict(state, strict=strict)

        runner.load_checkpoint = load_checkpoint
        sys.modules["mmcv.runner"] = runner

    if "mmseg.utils" not in sys.modules:
        mmseg = sys.modules.setdefault("mmseg", types.ModuleType("mmseg"))
        utils = types.ModuleType("mmseg.utils")
        utils.get_root_logger = lambda: logging.getLogger("ppft")
        mmseg.utils = utils
        sys.modules["mmseg.utils"] = utils

    # Keep a reference so static analyzers do not mistake this for an import
    # shim that can work without PyTorch at runtime.
    _ = torch.__version__


def _fresh_resnet34(*, weights=None, pretrained=False, **_kwargs):
    """Construct the initialization scaffold without downloading old weights."""

    del pretrained
    from torchvision.models import resnet34

    return resnet34(weights=weights)


def _patch_ppft_constructor(ppft_module, completionformer_module, backbone_module):
    """Make the foundation checkpoint optional before loading the full PPFT state."""

    import torch
    import torch.nn as nn

    def modern_init(self, args):
        nn.Module.__init__(self)
        self.args = args
        self.foundation = completionformer_module.CompletionFormer(args)

        foundation_path = getattr(args, "pretrained_completionformer", None)
        if foundation_path:
            checkpoint = _trusted_torch_load(foundation_path)
            state = checkpoint.get("net", checkpoint)
            self.foundation.load_state_dict(state, strict=True)

        self.prop_time = args.prop_time
        self.num_neighbors = args.prop_kernel * args.prop_kernel - 1
        self.backbone = backbone_module.PPFTBackbone(
            args, self.foundation.backbone, mode="rgbd"
        )
        if self.prop_time > 0:
            self.prop_layer = self.foundation.prop_layer

    ppft_module.PPFT.__init__ = modern_init
    # ``torch`` is used by the original class's forward method and remains in
    # its defining module.  Referencing it here documents that dependency.
    _ = torch.__version__


def import_modern_ppft(upstream_root: str | Path):
    """Import and minimally adapt an upstream PPFT checkout for inference."""

    root = Path(upstream_root).resolve()
    required = root / "model" / "ppft" / "ppft.py"
    if not required.is_file():
        raise FileNotFoundError(f"Not a PPFT source tree: missing {required}")

    _install_dcn_inference_shim()
    _install_legacy_import_shims()

    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    existing_model = sys.modules.get("model")
    if existing_model is not None:
        model_file = Path(getattr(existing_model, "__file__", "")).resolve()
        if root not in model_file.parents:
            raise RuntimeError(
                "A different top-level 'model' package is already imported; "
                "run PPFT compatibility in a fresh Python process"
            )

    model_package = importlib.import_module("model")
    pvt_module = importlib.import_module("model.completionformer.pvt")
    ppft_module = importlib.import_module("model.ppft.ppft")
    completionformer_module = importlib.import_module(
        "model.completionformer.completionformer"
    )
    backbone_module = importlib.import_module("model.ppft.ppft_backbone")

    # The full author checkpoint overwrites these initialization values.  Do
    # not require obsolete pvt/resnet initialization files merely to construct
    # the module graph.
    pvt_module.get_resnet34 = _fresh_resnet34
    pvt_module.load_checkpoint = lambda *_args, **_kwargs: None
    _patch_ppft_constructor(ppft_module, completionformer_module, backbone_module)
    model_package.PPFT = ppft_module.PPFT
    return ppft_module.PPFT


def default_ppft_args(*, foundation_checkpoint: str | Path | None = None):
    """Return the inference-relevant arguments used by the author test script."""

    return SimpleNamespace(
        prop_time=6,
        prop_kernel=3,
        preserve_input=False,
        affinity="TGASS",
        affinity_gamma=0.5,
        conf_prop=True,
        legacy=False,
        pol_rep="leichenyang-7",
        pretrained_completionformer=(
            str(Path(foundation_checkpoint).resolve())
            if foundation_checkpoint
            else None
        ),
    )


def load_ppft_model(
    upstream_root: str | Path,
    checkpoint_path: str | Path,
    *,
    foundation_checkpoint: str | Path | None = None,
    device: str = "cuda",
):
    """Construct PPFT, strictly load the author state, and move it to a device."""

    PPFT = import_modern_ppft(upstream_root)
    checkpoint = _trusted_torch_load(checkpoint_path)
    if not isinstance(checkpoint, dict):
        raise TypeError("PPFT checkpoint must be a mapping")
    args = default_ppft_args(foundation_checkpoint=foundation_checkpoint)
    checkpoint_args = checkpoint.get("args")
    behavior_arguments = (
        "prop_time",
        "prop_kernel",
        "preserve_input",
        "affinity",
        "affinity_gamma",
        "conf_prop",
        "legacy",
        "pol_rep",
    )
    mismatches = {
        name: (getattr(args, name), getattr(checkpoint_args, name))
        for name in behavior_arguments
        if checkpoint_args is not None
        and hasattr(checkpoint_args, name)
        and getattr(args, name) != getattr(checkpoint_args, name)
    }
    if mismatches:
        raise ValueError(f"PPFT checkpoint behavior arguments do not match: {mismatches}")
    model = PPFT(args)

    state = checkpoint.get("net", checkpoint)
    if not isinstance(state, dict):
        raise TypeError("PPFT checkpoint does not contain a state dictionary")
    if state and all(key.startswith("module.") for key in state):
        state = {key.removeprefix("module."): value for key, value in state.items()}
    model.load_state_dict(state, strict=True)
    model.eval().to(device)

    relevant_argument_names = (
        "model",
        "prop_time",
        "prop_kernel",
        "preserve_input",
        "affinity",
        "affinity_gamma",
        "conf_prop",
        "legacy",
        "pol_rep",
        "completionformer_mode",
        "pre_pvt",
        "pre_res",
        "max_depth",
    )
    metadata = {
        "strict_checkpoint_load": True,
        "checkpoint_keys": len(state),
        "checkpoint_tensor_numel": sum(
            value.numel() for value in state.values() if hasattr(value, "numel")
        ),
        "checkpoint_epoch": checkpoint.get("epoch"),
        "checkpoint_arguments": {
            name: getattr(checkpoint_args, name)
            for name in relevant_argument_names
            if checkpoint_args is not None and hasattr(checkpoint_args, name)
        },
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "trainable_parameter_count": sum(
            parameter.numel() for parameter in model.parameters() if parameter.requires_grad
        ),
    }
    return model, args, metadata
