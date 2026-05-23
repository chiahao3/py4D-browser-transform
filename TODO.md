# TODO

## RAM Checkpoints and Restore

- Add a menu option to save a RAM checkpoint of the current datacube.
- Include relevant viewer/plugin settings and datacube shape with each checkpoint.
- Add a restore menu option that opens a window listing saved RAM checkpoints.
- Allow users to restore a previous checkpoint into the viewer.
- Consider checkpoint naming, replacement, deletion, and memory-usage warnings for large datacubes.

## Datacube Slicing, Subsampling, and Binning

- Add operations to slice the datacube along supported axes.
- Add subsampling with step syntax such as `[::n]`.
- Add binning along supported axes.
- Build these operations on top of the RAM checkpoint/restore workflow so users can recover easily.
- Update calibration automatically after slicing, subsampling, and binning where possible.
- Add tests for transformed data shape, data values, and calibration updates.
