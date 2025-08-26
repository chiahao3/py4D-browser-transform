
import numpy as np
from PyQt5.QtWidgets import (
    QAction,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget
)


from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton
)
from PyQt5.QtCore import Qt

class TransformPlugin(QWidget):

    # required for py4DGUI to recognize this as a plugin.
    plugin_id = "chiahao3.transform"

    # optional flags

    # Plugins may add a top-level menu on their own, or can opt to have
    # a submenu located under Plugins>[display_name], which is created before
    # initialization and its QMenu object passed as `plugin_menu`
    uses_plugin_menu = (
        True  # Put it under Plugins feels cleaner although it's one more level
    )
    display_name = "Transform"

    def __init__(self, parent, plugin_menu, **kwargs):
        super().__init__()
        self.parent = parent
        self.current_permutation = [0, 1, 2, 3]  # Default axis order (Nslow, Nfast, Ky, Kx)
        self.flip_settings = {
            "flipud": False,
            "fliplr": False,
            "transpose": False,
        }       

        # Add Transform menu
        self.transform_menu = plugin_menu

        # Add "Set Axis Permutation" option
        self.set_axis_permutation_action = QAction("Set Axis Permutation", self)
        self.set_axis_permutation_action.triggered.connect(self.set_axis_permutation)
        self.transform_menu.addAction(self.set_axis_permutation_action)

        # Add "Set Diffraction Flips" option
        self.set_diffraction_flips_action = QAction("Set Diffraction Flips", self)
        self.set_diffraction_flips_action.triggered.connect(self.set_diffraction_flips)
        self.transform_menu.addAction(self.set_diffraction_flips_action)
    
    def set_axis_permutation(self):
        parent = self.parent
        dialog = AxisPermutationDialog(self, self.current_permutation)
        if dialog.exec_() == QDialog.Accepted:
            new_permutation = dialog.get_values()
            print(f"Axis permutation set to: {new_permutation}")

            # Reverse the current permutation
            inverse_permutation = np.argsort(self.current_permutation) # For example [0,2,3,1] should be reversed with [0,3,1,2]
            parent.datacube.data = np.transpose(parent.datacube.data, inverse_permutation)

            # Apply the new permutation
            parent.datacube.data = np.transpose(parent.datacube.data, new_permutation)
            self.current_permutation = new_permutation

            # Update views
            parent.update_scalebars()
            parent.update_diffraction_space_view(reset=True)
            parent.update_real_space_view(reset=True)

    def set_diffraction_flips(self):
        parent = self.parent
        dialog = DiffractionFlipsDialog(self, self.flip_settings)  # Pass current flip settings
        if dialog.exec_() == QDialog.Accepted:
            new_flip_settings = dialog.get_values()
            print(f"Diffraction flips set to: {new_flip_settings}")
            
            # Note: There's a .T transpose at every final display of datacube in update_views
            # So we need to adjust accordingly for the flipping axes
            
            #  Apply if the flip settings are different (Nslow, Nfast, Ky, Kx)
            if new_flip_settings != self.flip_settings:
                # Revert current flips in reverse order if they're non-zero
                if self.flip_settings["transpose"]:
                    parent.datacube.data = np.transpose(parent.datacube.data, (0, 1, 3, 2))
                if self.flip_settings["fliplr"]:
                    parent.datacube.data = np.flip(parent.datacube.data, axis=3)
                if self.flip_settings["flipud"]:
                    parent.datacube.data = np.flip(parent.datacube.data, axis=2)
            
                # Apply the new flips       
                if new_flip_settings["flipud"]:
                    parent.datacube.data = np.flip(parent.datacube.data, axis=2)
                if new_flip_settings["fliplr"]:
                    parent.datacube.data = np.flip(parent.datacube.data, axis=3)
                if new_flip_settings["transpose"]:
                    parent.datacube.data = np.transpose(parent.datacube.data, (0, 1, 3, 2))

                # Update attributes and views
                self.flip_settings = new_flip_settings
                parent.update_scalebars()
                parent.update_diffraction_space_view(reset=True)
                parent.update_real_space_view(reset=True)

class AxisPermutationDialog(QDialog):
    def __init__(self, parent=None, current_permutation=None):
        super().__init__(parent)

        self.setWindowTitle("Set Axis Permutation")
        self.resize(300, 200)

        layout = QVBoxLayout(self)

        # Instruction
        layout.addWidget(QLabel("Drag and drop to reorder axes:"))

        # Draggable list for axes
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)

        # Axis labels
        self.axis_labels = ["Axis 0", "Axis 1", "Axis 2", "Axis 3"]

        self._populate_list(current_permutation)
        layout.addWidget(self.list_widget)

        # Buttons
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
        """Helper to fill the list widget with given permutation."""
        self.list_widget.clear()
        for idx in permutation:
            item = QListWidgetItem(self.axis_labels[idx])
            item.setData(Qt.UserRole, idx)
            self.list_widget.addItem(item)

    def reset_to_default(self):
        """Reset to [0,1,2,3]"""
        self._populate_list([0, 1, 2, 3])

    def get_values(self):
        """Return axis permutation as a list of ints."""
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

        # Default (identity) flips
        self.default_flips = {"flipud": False, "fliplr": False, "transpose": False}
        self.current_flips = current_flips or self.default_flips.copy()

        # Flipud input
        flipud_layout = QHBoxLayout()
        flipud_layout.addWidget(QLabel("Flip Up-Down:"))
        self.flipud_checkbox = QCheckBox()
        self.flipud_checkbox.setChecked(bool(self.current_flips.get("flipud", False)))
        flipud_layout.addWidget(self.flipud_checkbox)
        layout.addLayout(flipud_layout)

        # Fliplr input
        fliplr_layout = QHBoxLayout()
        fliplr_layout.addWidget(QLabel("Flip Left-Right:"))
        self.fliplr_checkbox = QCheckBox()
        self.fliplr_checkbox.setChecked(bool(self.current_flips.get("fliplr", False)))
        fliplr_layout.addWidget(self.fliplr_checkbox)
        layout.addLayout(fliplr_layout)

        # Transpose input
        transpose_layout = QHBoxLayout()
        transpose_layout.addWidget(QLabel("Transpose X/Y:"))
        self.transpose_checkbox = QCheckBox()
        self.transpose_checkbox.setChecked(bool(self.current_flips.get("transpose", False)))
        transpose_layout.addWidget(self.transpose_checkbox)
        layout.addLayout(transpose_layout)

        # Buttons
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
        """Reset all flips to default (no flips, no transpose)."""
        self.flipud_checkbox.setChecked(self.default_flips["flipud"])
        self.fliplr_checkbox.setChecked(self.default_flips["fliplr"])
        self.transpose_checkbox.setChecked(self.default_flips["transpose"])

    def get_values(self):
        return {
            "flipud": self.flipud_checkbox.isChecked(),
            "fliplr": self.fliplr_checkbox.isChecked(),
            "transpose": self.transpose_checkbox.isChecked(),
        }