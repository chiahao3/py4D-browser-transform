# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-07-21
### Fixed
- Fix diffraction-origin adjustment after slicing/subsampling/binning: the origin is stored in Q-axis pixel coordinates, but the previous formula subtracted a physical-unit offset and never divided by the bin/subsample factor, leaving the origin badly wrong after any transform that touched the Q axes.
- Preserve the datacube's original EMD root name (e.g. `datacube_root`) through RAM checkpoint copies and datacube transforms. `py4DSTEM.DataCube.copy()` renames the root to `py4DSTEM_root`, which broke calibration reload when a transformed/checkpointed datacube was later exported as `py4DSTEM HDF5` and reopened in py4D-browser.

## [0.1.0] - 2026-05-23
### Added
- Add `Slice / Subsample / Bin` to the `Transform` submenu for applying validated per-axis slicing, stride-based subsampling, and binning to 4D datacubes.
- Add RAM checkpoint support for saving, restoring, replacing, renaming, and deleting in-memory datacube snapshots before destructive transforms.
- Add memory-size estimates and confirmation prompts for large RAM checkpoints.
- Add calibration updates for datacube slicing, subsampling, and binning, including pixel-size scaling for symmetric axis spacing and diffraction-origin adjustment for Q-axis slices.

### Changed
- Split the transform plugin into focused checkpoint, datacube operation, dialog, and menu orchestration modules.
- Reset stored axis permutation and diffraction flip state when restoring a RAM checkpoint.

### Fixed
- Keep datacube transforms and checkpoint restores isolated from the original datacube by working on independent copies.

### Tests
- Add coverage for checkpoint creation, restoration, replacement, renaming, deletion, memory accounting, and copy isolation.
- Add coverage for datacube slicing, subsampling, binning, calibration updates, invalid input handling, and menu-driven datacube updates.

## [0.0.2.post1] - 2026-05-07
### Changed
- Require Python 3.11 or newer.

## [0.0.2] - 2026-05-06
### Changed
- Require `py4d-browser >= 1.5.0`.
- Use py4D-browser's preferred `set_datacube` workflow after axis permutation and diffraction flip transforms so browser state refreshes through the host application's datacube update path.

### Tests
- Add coverage ensuring axis permutation and diffraction flip actions update the browser via `set_datacube`.

## [0.0.1] - 2025-08-26
### Added
- Add `Set Diffraction Flips` to the `Transform` submenu
- Add `Set Axis Permutation` to the `Transform` submenu
