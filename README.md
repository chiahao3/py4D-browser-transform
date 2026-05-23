# py4D-browser-transform

`py4D-browser-transform` is a plugin for [py4D-browser](https://github.com/sezelt/py4D-browser) that adds in-memory datacube transformation tools. It currently supports axis permutation, diffraction flips/transposes, RAM checkpoints and restore, and datacube slicing, subsampling, and binning.

## Installation
You can install `py4D-browser-transform` with pip or conda:

```bash
pip install py4d-browser-transform
```

> 💡 **Note:** 
> - If you install into a fresh Python environment, `py4D-browser` and `py4DSTEM` will be automatically installed as dependencies so you don't need to install them first.
> - If you already have `py4D-browser` installed, you can install this plugin into the same Python environment.

A step-by-step guide including creating a fresh Python environment via conda would look like this:
```bash
conda create -n py4dgui python=3.12
conda activate py4dgui
python -m pip install --upgrade pip
python -m pip cache purge
pip install py4d-browser-transform
```

## Usage
Simply run the following command to start the browser once you activated the corresponding Python environment:

```bash
py4dgui
```

After installing this plugin, you should see the "Transform" submenu appear under the **"Plugins"** menu.  
From here, you can:

- **Set Axis Permutation**: reorder the four datacube axes when the loaded dataset is not in the expected order.
- **Set Diffraction Flips**: flip the diffraction pattern up/down, left/right, or transpose its X/Y axes.
- **Save RAM Checkpoint**: store a RAM-only snapshot of the current in-memory datacube.
- **Restore RAM Checkpoint**: restore a previous RAM checkpoint, rename checkpoints, replace checkpoints, or delete checkpoints.
- **Slice / Subsample / Bin**: slice, subsample with Python-style step syntax such as `::2`, and bin along the displayed axes `Ry`, `Rx`, `Qy`, and `Qx`.

![Demo of py4D-browser-transform](assets/demo.gif)

These operations directly modify the loaded in-memory datacube, but do not affect the raw file stored on disk. You can export the transformed datacube to disk using **File > Export Datacube**.

### RAM checkpoints

RAM checkpoints are session-local snapshots of the datacube data at the moment they are saved. They are intended as recovery points before destructive in-memory transformations such as slicing, subsampling, and binning.

Checkpoint restore loads the saved datacube snapshot and resets the flip/permutation markers back to their default clean state. In other words, a checkpoint represents "the datacube exactly as it looked then", not a reversible history of every flip or permutation action that produced it.

Large checkpoints can require substantial memory. The plugin warns before saving a checkpoint larger than 1 GiB, or when total stored checkpoint data would exceed 4 GiB.

### Slicing, subsampling, and binning

The **Slice / Subsample / Bin** dialog provides one row for each axis:

- `Ry`
- `Rx`
- `Qy`
- `Qx`

Use slice text like `:`, `10:100`, or `::4` to select or subsample data. Use the bin control to sum neighboring pixels along an axis. The dialog previews the output shape before applying the transform.

Calibration pixel sizes are updated when both axes in real space or both axes in diffraction space change by the same spacing factor. When the change cannot be represented safely by py4DSTEM's shared real-space or diffraction-space pixel size, calibration is preserved.

> **Note:**
> The order of flipping and permutation matters. If you mix these operations, reversing them manually requires applying the opposite operations in the opposite order. RAM checkpoints provide a simpler way to return to a known datacube state.

## License

GNU GPLv3

**py4D-browser-transform** is open source software distributed under a GPLv3 license.
It is free to use, alter, or build on, provided that any work derived from **py4D-browser-transform** is also kept free and open.
