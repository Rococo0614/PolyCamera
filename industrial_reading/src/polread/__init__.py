"""Auditable utilities for offline polarization-reading proxy experiments."""

from .instrument import (
    estimate_affine_instrument,
    ideal_linear_instrument,
    solve_stokes,
)
from .polarization import (
    linear_stokes,
    representation_images,
    virtual_analyzer,
)
from .text_metrics import TextNormalization, evaluate_text, normalize_text

__all__ = [
    "TextNormalization",
    "estimate_affine_instrument",
    "evaluate_text",
    "ideal_linear_instrument",
    "linear_stokes",
    "normalize_text",
    "representation_images",
    "solve_stokes",
    "virtual_analyzer",
]
