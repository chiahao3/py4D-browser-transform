"""Pure datacube slicing, subsampling, binning, and calibration helpers."""

from .checkpoints import copy_datacube


AXIS_LABELS = ("Ry", "Rx", "Qy", "Qx")


def _parse_slice(text):
    text = text.strip()
    if text in ("", ":"):
        return slice(None)
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    if ":" not in text:
        index = int(text)
        return slice(index, index + 1, 1)
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid slice syntax: {text!r}")

    values = []
    for part in parts:
        values.append(None if part.strip() == "" else int(part))
    values.extend([None] * (3 - len(values)))
    result = slice(values[0], values[1], values[2])
    if result.step is not None and result.step <= 0:
        raise ValueError("Slice steps must be positive")
    return result


def _bin_axis(data, axis, factor):
    if factor <= 1:
        return data
    length = data.shape[axis]
    usable = length - (length % factor)
    if usable <= 0:
        raise ValueError(
            f"Axis {AXIS_LABELS[axis]} with length {length} is too small for bin {factor}"
        )
    if usable != length:
        data = data[
            tuple(
                slice(0, usable) if i == axis else slice(None)
                for i in range(data.ndim)
            )
        ]
    shape = list(data.shape)
    shape[axis : axis + 1] = [usable // factor, factor]
    return data.reshape(shape).sum(axis=axis + 1)


def _set_calibration_value(calibration, setter_name, value):
    if value is None:
        return
    setter = getattr(calibration, setter_name, None)
    if setter is not None:
        setter(value)


def _update_transform_calibration(datacube, starts, spacing_factors):
    calibration = getattr(datacube, "calibration", None)
    if calibration is None:
        return

    real_factors = (spacing_factors[0], spacing_factors[1])
    if real_factors[0] == real_factors[1] and real_factors[0] != 1:
        pixel_size = calibration.get_R_pixel_size()
        _set_calibration_value(
            calibration, "set_R_pixel_size", pixel_size * real_factors[0]
        )

    q_factors = (spacing_factors[2], spacing_factors[3])
    old_q_pixel_size = calibration.get_Q_pixel_size()
    if q_factors[0] == q_factors[1] and q_factors[0] != 1:
        _set_calibration_value(
            calibration, "set_Q_pixel_size", old_q_pixel_size * q_factors[0]
        )

    origin = calibration.get_origin() if hasattr(calibration, "get_origin") else None
    if origin is not None and old_q_pixel_size is not None:
        qx0, qy0 = origin
        if qx0 is not None and qy0 is not None:
            calibration.set_origin(
                (
                    qx0 - starts[2] * old_q_pixel_size,
                    qy0 - starts[3] * old_q_pixel_size,
                )
            )


def apply_datacube_operations(datacube, operations):
    """Apply validated slice/subsample/bin operations to a copied datacube."""
    if len(operations) != 4:
        raise ValueError("Expected one operation for each of the four datacube axes")

    slices = []
    starts = []
    spacing_factors = []
    bins = []
    shape = datacube.data.shape
    if len(shape) != 4:
        raise ValueError(f"Expected a 4D datacube, got shape {shape}")

    for axis, operation in enumerate(operations):
        axis_slice = _parse_slice(operation.get("slice", ":"))
        start, stop, step = axis_slice.indices(shape[axis])
        if stop <= start:
            raise ValueError(f"Axis {AXIS_LABELS[axis]} slice selects no data")
        bin_factor = int(operation.get("bin", 1))
        if bin_factor < 1:
            raise ValueError(f"Axis {AXIS_LABELS[axis]} bin factor must be positive")
        slices.append(slice(start, stop, step))
        starts.append(start)
        spacing_factors.append(step * bin_factor)
        bins.append(bin_factor)

    transformed = copy_datacube(datacube)
    transformed.data = transformed.data[tuple(slices)].copy()
    for axis, bin_factor in enumerate(bins):
        transformed.data = _bin_axis(transformed.data, axis, bin_factor)

    _update_transform_calibration(transformed, starts, spacing_factors)
    if hasattr(transformed, "calibrate"):
        transformed.calibrate()
    return transformed


def estimate_transformed_shape(shape, operations):
    transformed_shape = list(shape)
    for axis, operation in enumerate(operations):
        axis_slice = _parse_slice(operation.get("slice", ":"))
        start, stop, step = axis_slice.indices(transformed_shape[axis])
        if stop <= start:
            raise ValueError(f"Axis {AXIS_LABELS[axis]} slice selects no data")
        transformed_shape[axis] = len(range(start, stop, step))
        bin_factor = int(operation.get("bin", 1))
        if bin_factor < 1:
            raise ValueError(f"Axis {AXIS_LABELS[axis]} bin factor must be positive")
        if bin_factor > 1:
            usable = transformed_shape[axis] - (transformed_shape[axis] % bin_factor)
            if usable <= 0:
                raise ValueError(
                    f"Axis {AXIS_LABELS[axis]} with length {transformed_shape[axis]} is too small for bin {bin_factor}"
                )
            transformed_shape[axis] = usable // bin_factor
    return tuple(transformed_shape)
