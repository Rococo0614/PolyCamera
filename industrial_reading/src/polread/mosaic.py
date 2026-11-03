"""Simple auditable MPFA mosaicking and interpolation baselines."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np


# PDD/IGRI monochrome pattern:
#   90   45
#  135    0
MPFA_OFFSETS = {
    "i90": (0, 0),
    "i45": (0, 1),
    "i135": (1, 0),
    "i0": (1, 1),
}


def make_mpfa_mosaic(channels: Mapping[str, np.ndarray]) -> np.ndarray:
    arrays = {key: np.asarray(channels[key], dtype=np.float64) for key in MPFA_OFFSETS}
    shapes = {array.shape for array in arrays.values()}
    if len(shapes) != 1:
        raise ValueError(f"MPFA channel shapes differ: {sorted(shapes)}")
    shape = next(iter(shapes))
    if len(shape) != 2:
        raise ValueError(f"Expected monochrome HxW channels, got {shape}")
    mosaic = np.empty(shape, dtype=np.float64)
    for key, (row, column) in MPFA_OFFSETS.items():
        mosaic[row::2, column::2] = arrays[key][row::2, column::2]
    return mosaic


def _nearest_indices(length: int, offset: int) -> np.ndarray:
    coordinates = np.arange(length)
    nearest = 2 * np.floor((coordinates - offset + 1) / 2).astype(int) + offset
    valid = np.arange(offset, length, 2)
    if not valid.size:
        raise ValueError(f"Dimension {length} cannot contain parity offset {offset}")
    return np.clip(nearest, valid[0], valid[-1])


def demosaic_nearest(mosaic: np.ndarray) -> dict[str, np.ndarray]:
    """Nearest same-parity reconstruction for all four polarization channels."""

    array = np.asarray(mosaic, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError(f"Expected HxW mosaic, got {array.shape}")
    rows, columns = array.shape
    result: dict[str, np.ndarray] = {}
    for key, (row_offset, column_offset) in MPFA_OFFSETS.items():
        row_index = _nearest_indices(rows, row_offset)
        column_index = _nearest_indices(columns, column_offset)
        result[key] = array[np.ix_(row_index, column_index)]
    return result


def _normalized_convolution(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    kernel = np.array([[1.0, 2.0, 1.0], [2.0, 4.0, 2.0], [1.0, 2.0, 1.0]])
    padded_values = np.pad(values, 1, mode="edge")
    padded_mask = np.pad(mask, 1, mode="edge")
    numerator = np.zeros_like(values, dtype=np.float64)
    denominator = np.zeros_like(values, dtype=np.float64)
    for row in range(3):
        for column in range(3):
            weight = kernel[row, column]
            numerator += weight * padded_values[row : row + values.shape[0], column : column + values.shape[1]]
            denominator += weight * padded_mask[row : row + values.shape[0], column : column + values.shape[1]]
    return numerator / np.maximum(denominator, 1e-12)


def demosaic_bilinear(mosaic: np.ndarray) -> dict[str, np.ndarray]:
    """Normalized 3x3 bilinear interpolation from each MPFA parity class."""

    array = np.asarray(mosaic, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError(f"Expected HxW mosaic, got {array.shape}")
    result: dict[str, np.ndarray] = {}
    for key, (row_offset, column_offset) in MPFA_OFFSETS.items():
        mask = np.zeros_like(array, dtype=np.float64)
        mask[row_offset::2, column_offset::2] = 1.0
        sparse = array * mask
        result[key] = _normalized_convolution(sparse, mask)
    return result
