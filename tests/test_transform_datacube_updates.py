import importlib
import sys
import types

import numpy as np


def _install_pyqt_stubs(monkeypatch):
    pyqt5 = types.ModuleType("PyQt5")
    widgets = types.ModuleType("PyQt5.QtWidgets")
    core = types.ModuleType("PyQt5.QtCore")

    class _Signal:
        def connect(self, _callback):
            pass

    class QAction:
        def __init__(self, *_args, **_kwargs):
            self.triggered = _Signal()

    class QWidget:
        pass

    class QDialog:
        Accepted = 1

        def __init__(self, *_args, **_kwargs):
            pass

    class _Widget:
        def __init__(self, *_args, **_kwargs):
            pass

    class _Qt:
        MoveAction = object()
        UserRole = object()

    widgets.QAction = QAction
    widgets.QCheckBox = _Widget
    widgets.QDialog = QDialog
    widgets.QHBoxLayout = _Widget
    widgets.QLabel = _Widget
    widgets.QListWidget = _Widget
    widgets.QListWidgetItem = _Widget
    widgets.QPushButton = _Widget
    widgets.QVBoxLayout = _Widget
    widgets.QWidget = QWidget
    core.Qt = _Qt

    monkeypatch.setitem(sys.modules, "PyQt5", pyqt5)
    monkeypatch.setitem(sys.modules, "PyQt5.QtWidgets", widgets)
    monkeypatch.setitem(sys.modules, "PyQt5.QtCore", core)


def _load_transform_module(monkeypatch):
    _install_pyqt_stubs(monkeypatch)
    return importlib.import_module("py4d_browser_plugin.transform.transform")


class _Datacube:
    def __init__(self, data):
        self.data = data


class _Parent:
    def __init__(self, data):
        self.datacube = _Datacube(data)
        self.set_datacube_calls = []

    def windowTitle(self):
        return "existing title"

    def set_datacube(self, datacube, window_title):
        self.set_datacube_calls.append((datacube, window_title))

    def update_scalebars(self):
        raise AssertionError("manual refresh should go through set_datacube")

    def update_diffraction_space_view(self, reset=False):
        raise AssertionError("manual refresh should go through set_datacube")

    def update_real_space_view(self, reset=False):
        raise AssertionError("manual refresh should go through set_datacube")


class _Dialog:
    def __init__(self, values, accepted):
        self._values = values
        self._accepted = accepted

    def exec_(self):
        return self._accepted

    def get_values(self):
        return self._values


def test_axis_permutation_uses_set_datacube(monkeypatch):
    module = _load_transform_module(monkeypatch)
    data = np.arange(2 * 3 * 4 * 5).reshape(2, 3, 4, 5)
    parent = _Parent(data.copy())
    plugin = object.__new__(module.TransformPlugin)
    plugin.parent = parent
    plugin.current_permutation = [0, 1, 2, 3]

    new_permutation = [0, 2, 1, 3]
    monkeypatch.setattr(
        module,
        "AxisPermutationDialog",
        lambda *_args: _Dialog(new_permutation, module.QDialog.Accepted),
    )

    plugin.set_axis_permutation()

    np.testing.assert_array_equal(parent.datacube.data, np.transpose(data, new_permutation))
    assert plugin.current_permutation == new_permutation
    assert parent.set_datacube_calls == [(parent.datacube, "existing title")]


def test_diffraction_flips_uses_set_datacube(monkeypatch):
    module = _load_transform_module(monkeypatch)
    data = np.arange(2 * 3 * 4 * 5).reshape(2, 3, 4, 5)
    parent = _Parent(data.copy())
    plugin = object.__new__(module.TransformPlugin)
    plugin.parent = parent
    plugin.flip_settings = {"flipud": False, "fliplr": False, "transpose": False}

    new_flips = {"flipud": True, "fliplr": True, "transpose": True}
    monkeypatch.setattr(
        module,
        "DiffractionFlipsDialog",
        lambda *_args: _Dialog(new_flips, module.QDialog.Accepted),
    )

    plugin.set_diffraction_flips()

    expected = np.transpose(np.flip(np.flip(data, axis=2), axis=3), (0, 1, 3, 2))
    np.testing.assert_array_equal(parent.datacube.data, expected)
    assert plugin.flip_settings == new_flips
    assert parent.set_datacube_calls == [(parent.datacube, "existing title")]
