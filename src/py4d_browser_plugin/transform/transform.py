from dataclasses import dataclass
from datetime import datetime
from itertools import count

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


CHECKPOINT_WARNING_BYTES = 1024**3
CHECKPOINT_TOTAL_WARNING_BYTES = 4 * 1024**3
AXIS_LABELS = ("Ry", "Rx", "Qy", "Qx")
SLICE_SUBSAMPLE_BIN_LABEL = "Slice / Subsample / Bin"
DEFAULT_PERMUTATION = [0, 1, 2, 3]
DEFAULT_FLIP_SETTINGS = {
    "flipud": False,
    "fliplr": False,
    "transpose": False,
}


@dataclass
class DatacubeCheckpoint:
    checkpoint_id: int
    name: str
    created_at: datetime
    shape: tuple
    dtype: str
    estimated_bytes: int
    datacube: object
    metadata: dict
    window_title: str


def _copy_datacube(datacube):
    if hasattr(datacube, "copy"):
        return datacube.copy()
    copied = type(datacube)(datacube.data.copy())
    if hasattr(datacube, "calibration"):
        copied.calibration = datacube.calibration.copy()
    return copied


def _datacube_nbytes(datacube):
    return int(getattr(datacube.data, "nbytes", 0))


def _format_bytes(nbytes):
    value = float(nbytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024


def _checkpoint_metadata(datacube):
    return {
        "shape": tuple(datacube.data.shape),
        "dtype": str(datacube.data.dtype),
        "estimated_bytes": _datacube_nbytes(datacube),
    }


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
        data = data[tuple(slice(0, usable) if i == axis else slice(None) for i in range(data.ndim))]
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

    transformed = _copy_datacube(datacube)
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


class TransformPlugin(QWidget):
    plugin_id = "chiahao3.transform"
    uses_plugin_menu = True
    display_name = "Transform"

    def __init__(self, parent, plugin_menu, **kwargs):
        super().__init__()
        self.parent = parent
        self.current_permutation = list(DEFAULT_PERMUTATION)
        self.flip_settings = dict(DEFAULT_FLIP_SETTINGS)
        self.checkpoints = []
        self._checkpoint_ids = count(1)

        self.transform_menu = plugin_menu
        self.set_axis_permutation_action = QAction("Set Axis Permutation", self)
        self.set_axis_permutation_action.triggered.connect(self.set_axis_permutation)
        self.transform_menu.addAction(self.set_axis_permutation_action)

        self.set_diffraction_flips_action = QAction("Set Diffraction Flips", self)
        self.set_diffraction_flips_action.triggered.connect(self.set_diffraction_flips)
        self.transform_menu.addAction(self.set_diffraction_flips_action)

        self.transform_datacube_action = QAction(SLICE_SUBSAMPLE_BIN_LABEL, self)
        self.transform_datacube_action.triggered.connect(self.transform_datacube)
        self.transform_menu.addAction(self.transform_datacube_action)

        self.save_checkpoint_action = QAction("Save RAM Checkpoint", self)
        self.save_checkpoint_action.triggered.connect(self.save_ram_checkpoint)
        self.transform_menu.addAction(self.save_checkpoint_action)

        self.restore_checkpoint_action = QAction("Restore RAM Checkpoint", self)
        self.restore_checkpoint_action.triggered.connect(self.restore_ram_checkpoint)
        self.transform_menu.addAction(self.restore_checkpoint_action)

    def _set_transformed_datacube(self):
        parent = self.parent
        parent.set_datacube(parent.datacube, parent.windowTitle())

    def _default_checkpoint_name(self):
        return f"Checkpoint {len(self.checkpoints) + 1}"

    def _find_checkpoint(self, checkpoint_id):
        for checkpoint in self.checkpoints:
            if checkpoint.checkpoint_id == checkpoint_id:
                return checkpoint
        raise KeyError(f"Unknown checkpoint id: {checkpoint_id}")

    def total_checkpoint_bytes(self):
        return sum(checkpoint.estimated_bytes for checkpoint in self.checkpoints)

    def create_checkpoint(self, name=None):
        datacube = self.parent.datacube
        checkpoint_datacube = _copy_datacube(datacube)
        metadata = _checkpoint_metadata(datacube)
        checkpoint = DatacubeCheckpoint(
            checkpoint_id=next(self._checkpoint_ids),
            name=name or self._default_checkpoint_name(),
            created_at=datetime.now(),
            shape=metadata["shape"],
            dtype=metadata["dtype"],
            estimated_bytes=metadata["estimated_bytes"],
            datacube=checkpoint_datacube,
            metadata=metadata,
            window_title=self.parent.windowTitle(),
        )
        self.checkpoints.append(checkpoint)
        return checkpoint

    def replace_checkpoint(self, checkpoint_id):
        old_checkpoint = self._find_checkpoint(checkpoint_id)
        new_checkpoint = self.create_checkpoint(old_checkpoint.name)
        new_checkpoint.checkpoint_id = checkpoint_id
        index = self.checkpoints.index(old_checkpoint)
        self.checkpoints[index] = new_checkpoint
        self.checkpoints.pop()
        return new_checkpoint

    def rename_checkpoint(self, checkpoint_id, name):
        checkpoint = self._find_checkpoint(checkpoint_id)
        checkpoint.name = name
        return checkpoint

    def delete_checkpoint(self, checkpoint_id):
        checkpoint = self._find_checkpoint(checkpoint_id)
        self.checkpoints.remove(checkpoint)

    def restore_checkpoint(self, checkpoint_id):
        checkpoint = self._find_checkpoint(checkpoint_id)
        restored_datacube = _copy_datacube(checkpoint.datacube)
        self.current_permutation = list(DEFAULT_PERMUTATION)
        self.flip_settings = dict(DEFAULT_FLIP_SETTINGS)
        self.parent.set_datacube(restored_datacube, checkpoint.window_title)
        return restored_datacube

    def _confirm_checkpoint_save(self, checkpoint_bytes):
        projected_total = self.total_checkpoint_bytes() + checkpoint_bytes
        if (
            checkpoint_bytes < CHECKPOINT_WARNING_BYTES
            and projected_total < CHECKPOINT_TOTAL_WARNING_BYTES
        ):
            return True
        message = (
            "This RAM checkpoint will copy "
            f"{_format_bytes(checkpoint_bytes)} into memory.\n"
            f"Stored checkpoints after saving: {_format_bytes(projected_total)}."
        )
        return (
            QMessageBox.question(
                self,
                "Save RAM Checkpoint",
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        )

    def save_ram_checkpoint(self):
        if self.parent.datacube is None:
            QMessageBox.warning(self, "Save RAM Checkpoint", "No datacube is loaded.")
            return None
        dialog = SaveCheckpointDialog(
            self,
            self._default_checkpoint_name(),
            self.parent.datacube.data.shape,
            self.parent.datacube.data.dtype,
            _datacube_nbytes(self.parent.datacube),
        )
        if dialog.exec_() != QDialog.Accepted:
            return None
        if not self._confirm_checkpoint_save(_datacube_nbytes(self.parent.datacube)):
            return None
        return self.create_checkpoint(dialog.get_name())

    def restore_ram_checkpoint(self):
        if not self.checkpoints:
            QMessageBox.information(
                self, "Restore RAM Checkpoint", "No RAM checkpoints have been saved."
            )
            return None
        dialog = RestoreCheckpointDialog(self, self.checkpoints)
        result = dialog.exec_()
        action, checkpoint_id, name = dialog.get_action()
        if action == "delete" and checkpoint_id is not None:
            self.delete_checkpoint(checkpoint_id)
            return None
        if action == "rename" and checkpoint_id is not None:
            self.rename_checkpoint(checkpoint_id, name)
            return None
        if action == "replace" and checkpoint_id is not None:
            if self._confirm_checkpoint_save(_datacube_nbytes(self.parent.datacube)):
                return self.replace_checkpoint(checkpoint_id)
            return None
        if result == QDialog.Accepted and action == "restore" and checkpoint_id is not None:
            return self.restore_checkpoint(checkpoint_id)
        return None

    def transform_datacube(self):
        if self.parent.datacube is None:
            QMessageBox.warning(self, SLICE_SUBSAMPLE_BIN_LABEL, "No datacube is loaded.")
            return None
        if not self.checkpoints:
            prompt = (
                "Create a RAM checkpoint before transforming this datacube?\n"
                "Transforms replace the current in-memory datacube."
            )
            if (
                QMessageBox.question(
                    self,
                    SLICE_SUBSAMPLE_BIN_LABEL,
                    prompt,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                != QMessageBox.Yes
            ):
                return None
            if not self._confirm_checkpoint_save(_datacube_nbytes(self.parent.datacube)):
                return None
            self.create_checkpoint()

        dialog = TransformDatacubeDialog(self, self.parent.datacube.data.shape)
        if dialog.exec_() != QDialog.Accepted:
            return None
        try:
            transformed = apply_datacube_operations(
                self.parent.datacube, dialog.get_operations()
            )
        except ValueError as exc:
            QMessageBox.warning(self, SLICE_SUBSAMPLE_BIN_LABEL, str(exc))
            return None
        self.parent.set_datacube(transformed, self.parent.windowTitle())
        return transformed

    def set_axis_permutation(self):
        parent = self.parent
        dialog = AxisPermutationDialog(self, self.current_permutation)
        if dialog.exec_() == QDialog.Accepted:
            new_permutation = dialog.get_values()
            print(f"Axis permutation set to: {new_permutation}")

            inverse_permutation = np.argsort(self.current_permutation)
            parent.datacube.data = np.transpose(parent.datacube.data, inverse_permutation)
            parent.datacube.data = np.transpose(parent.datacube.data, new_permutation)
            self.current_permutation = new_permutation

            self._set_transformed_datacube()

    def set_diffraction_flips(self):
        parent = self.parent
        dialog = DiffractionFlipsDialog(self, self.flip_settings)
        if dialog.exec_() == QDialog.Accepted:
            new_flip_settings = dialog.get_values()
            print(f"Diffraction flips set to: {new_flip_settings}")

            if new_flip_settings != self.flip_settings:
                if self.flip_settings["transpose"]:
                    parent.datacube.data = np.transpose(parent.datacube.data, (0, 1, 3, 2))
                if self.flip_settings["fliplr"]:
                    parent.datacube.data = np.flip(parent.datacube.data, axis=3)
                if self.flip_settings["flipud"]:
                    parent.datacube.data = np.flip(parent.datacube.data, axis=2)

                if new_flip_settings["flipud"]:
                    parent.datacube.data = np.flip(parent.datacube.data, axis=2)
                if new_flip_settings["fliplr"]:
                    parent.datacube.data = np.flip(parent.datacube.data, axis=3)
                if new_flip_settings["transpose"]:
                    parent.datacube.data = np.transpose(parent.datacube.data, (0, 1, 3, 2))

                self.flip_settings = new_flip_settings
                self._set_transformed_datacube()


class SaveCheckpointDialog(QDialog):
    def __init__(self, parent, default_name, shape, dtype, estimated_bytes):
        super().__init__(parent)
        self.setWindowTitle("Save RAM Checkpoint")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Shape: {tuple(shape)}"))
        layout.addWidget(QLabel(f"Dtype: {dtype}"))
        layout.addWidget(QLabel(f"Estimated memory: {_format_bytes(estimated_bytes)}"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit(default_name)
        row.addWidget(self.name_input)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        buttons.addWidget(save_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def get_name(self):
        return self.name_input.text().strip() or "Checkpoint"


class RestoreCheckpointDialog(QDialog):
    def __init__(self, parent, checkpoints):
        super().__init__(parent)
        self.setWindowTitle("Restore RAM Checkpoint")
        self._action = None
        self._checkpoint_id = None
        self._name = None

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for checkpoint in checkpoints:
            item = QListWidgetItem(
                (
                    f"{checkpoint.name} | "
                    f"{checkpoint.created_at:%Y-%m-%d %H:%M:%S} | "
                    f"{checkpoint.shape} | {checkpoint.dtype} | "
                    f"{_format_bytes(checkpoint.estimated_bytes)}"
                )
            )
            item.setData(Qt.UserRole, checkpoint.checkpoint_id)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)

        rename_row = QHBoxLayout()
        rename_row.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit("")
        rename_row.addWidget(self.name_input)
        layout.addLayout(rename_row)

        buttons = QHBoxLayout()
        for label, action, handler in (
            ("Restore", "restore", self._accept_action),
            ("Replace", "replace", self._done_action),
            ("Rename", "rename", self._done_action),
            ("Delete", "delete", self._done_action),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, a=action, h=handler: h(a))
            buttons.addWidget(button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def _selected_checkpoint_id(self):
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _store_action(self, action):
        self._action = action
        self._checkpoint_id = self._selected_checkpoint_id()
        self._name = self.name_input.text().strip()

    def _accept_action(self, action):
        self._store_action(action)
        self.accept()

    def _done_action(self, action):
        self._store_action(action)
        self.done(2)

    def get_action(self):
        return self._action, self._checkpoint_id, self._name


class TransformDatacubeDialog(QDialog):
    def __init__(self, parent, shape):
        super().__init__(parent)
        self.setWindowTitle(SLICE_SUBSAMPLE_BIN_LABEL)
        self.shape = tuple(shape)
        self.slice_inputs = []
        self.bin_inputs = []

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.addWidget(QLabel("Axis"), 0, 0)
        grid.addWidget(QLabel("Slice"), 0, 1)
        grid.addWidget(QLabel("Bin"), 0, 2)
        for axis, label in enumerate(AXIS_LABELS):
            grid.addWidget(QLabel(f"{label} ({self.shape[axis]})"), axis + 1, 0)
            slice_input = QLineEdit(":")
            slice_input.textChanged.connect(self.update_preview)
            self.slice_inputs.append(slice_input)
            grid.addWidget(slice_input, axis + 1, 1)
            bin_input = QSpinBox()
            bin_input.setRange(1, max(1, self.shape[axis]))
            bin_input.setValue(1)
            bin_input.valueChanged.connect(self.update_preview)
            self.bin_inputs.append(bin_input)
            grid.addWidget(bin_input, axis + 1, 2)
        layout.addLayout(grid)

        self.preview_label = QLabel("")
        layout.addWidget(self.preview_label)

        buttons = QHBoxLayout()
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.accept)
        buttons.addWidget(apply_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        self.update_preview()

    def get_operations(self):
        return [
            {"slice": self.slice_inputs[axis].text(), "bin": self.bin_inputs[axis].value()}
            for axis in range(4)
        ]

    def update_preview(self, *_args):
        try:
            transformed_shape = estimate_transformed_shape(self.shape, self.get_operations())
        except Exception as exc:
            self.preview_label.setText(f"Invalid transform: {exc}")
            return
        self.preview_label.setText(f"Output shape: {transformed_shape}")


class AxisPermutationDialog(QDialog):
    def __init__(self, parent=None, current_permutation=None):
        super().__init__(parent)

        self.setWindowTitle("Set Axis Permutation")
        self.resize(300, 200)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Drag and drop to reorder axes:"))

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)

        self.axis_labels = ["Axis 0", "Axis 1", "Axis 2", "Axis 3"]
        self._populate_list(current_permutation)
        layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_to_default)
        button_layout.addWidget(self.reset_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def _populate_list(self, permutation):
        self.list_widget.clear()
        for idx in permutation:
            item = QListWidgetItem(self.axis_labels[idx])
            item.setData(Qt.UserRole, idx)
            self.list_widget.addItem(item)

    def reset_to_default(self):
        self._populate_list([0, 1, 2, 3])

    def get_values(self):
        values = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            values.append(item.data(Qt.UserRole))
        return values


class DiffractionFlipsDialog(QDialog):
    def __init__(self, parent=None, current_flips=None):
        super().__init__(parent)

        self.setWindowTitle("Set Diffraction Flips")
        self.resize(300, 200)

        layout = QVBoxLayout(self)

        self.default_flips = dict(DEFAULT_FLIP_SETTINGS)
        self.current_flips = current_flips or self.default_flips.copy()

        flipud_layout = QHBoxLayout()
        flipud_layout.addWidget(QLabel("Flip Up-Down:"))
        self.flipud_checkbox = QCheckBox()
        self.flipud_checkbox.setChecked(bool(self.current_flips.get("flipud", False)))
        flipud_layout.addWidget(self.flipud_checkbox)
        layout.addLayout(flipud_layout)

        fliplr_layout = QHBoxLayout()
        fliplr_layout.addWidget(QLabel("Flip Left-Right:"))
        self.fliplr_checkbox = QCheckBox()
        self.fliplr_checkbox.setChecked(bool(self.current_flips.get("fliplr", False)))
        fliplr_layout.addWidget(self.fliplr_checkbox)
        layout.addLayout(fliplr_layout)

        transpose_layout = QHBoxLayout()
        transpose_layout.addWidget(QLabel("Transpose X/Y:"))
        self.transpose_checkbox = QCheckBox()
        self.transpose_checkbox.setChecked(bool(self.current_flips.get("transpose", False)))
        transpose_layout.addWidget(self.transpose_checkbox)
        layout.addLayout(transpose_layout)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_to_default)
        button_layout.addWidget(self.reset_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def reset_to_default(self):
        self.flipud_checkbox.setChecked(self.default_flips["flipud"])
        self.fliplr_checkbox.setChecked(self.default_flips["fliplr"])
        self.transpose_checkbox.setChecked(self.default_flips["transpose"])

    def get_values(self):
        return {
            "flipud": self.flipud_checkbox.isChecked(),
            "fliplr": self.fliplr_checkbox.isChecked(),
            "transpose": self.transpose_checkbox.isChecked(),
        }
