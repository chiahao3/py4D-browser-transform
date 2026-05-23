"""PyQt dialogs used by the transform plugin."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .checkpoints import format_bytes
from .datacube_ops import AXIS_LABELS, estimate_transformed_shape


SLICE_SUBSAMPLE_BIN_LABEL = "Slice / Subsample / Bin"
DEFAULT_PERMUTATION = [0, 1, 2, 3]
DEFAULT_FLIP_SETTINGS = {
    "flipud": False,
    "fliplr": False,
    "transpose": False,
}


# Checkpoint dialogs


class SaveCheckpointDialog(QDialog):
    def __init__(self, parent, default_name, shape, dtype, estimated_bytes):
        super().__init__(parent)
        self.setWindowTitle("Save RAM Checkpoint")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Shape: {tuple(shape)}"))
        layout.addWidget(QLabel(f"Dtype: {dtype}"))
        layout.addWidget(QLabel(f"Estimated memory: {format_bytes(estimated_bytes)}"))
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
                    f"{format_bytes(checkpoint.estimated_bytes)}"
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


# Transform dialogs


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
        self._populate_list(DEFAULT_PERMUTATION)

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
