# MoveAny API Reference

## Engine Modules (`moveany.modules`)

All engine functions are importable from the `moveany.modules` package.

### `batcher`

- **`batcher.split_into_batches(source, dest, exclusions, skip_top_dirs=None)`** - Split source tree into per-project batches
- **`batcher.get_batch_plan(source, dest, exclusions)`** - Get the batch plan as a dictionary

### `files`

- **`files_identical(path1, path2)`** - Check if two files are identical (size + SHA-256)
- **`files_copy_missing(compare_result, src, dest, reporter)`** - Copy missing/different files from compare result

### `mover`

- **`mover.copy_missing(compare_result, src, dest, reporter)`** - Copy missing/different files
- **`mover.delete_phase(ready, src, dest, reporter)`** - Delete files from source (after copy)
- **`mover.remove_empty_dirs(src, exclude_set, reporter)`** - Remove empty directories from source

### `paths`

- **`paths.normalize(path)`** - Normalize a path (Windows UNC, symlink resolution)
- **`paths.safe_delete(path)`** - Safe delete with move-to-trash behavior

### `repair`

- **`repair.repair_missing(compare_result, src_norm, dst_norm, reporter)`** - Re-copy missing/damaged files

### `reporting`

- **`Reporter(cls)`** - Base reporter class (subclass for CLI or GUI output)
- **`TextReporter(log_dir, log_callback)`** - Reporter extension for Tkinter Text widgets

### `safety`

- **`safety.safety_check(source, dest, exclusions)`** - Perform safety checks before destructive operations

### `verify`

- **`verify.compare(source, dest, exclusions, reporter, skip_top_dirs=None)`** - Compare two directory trees
- **`verify.report_compare(compare_result, reporter, label="compare")`** - Report comparison verdict

## CLI (`moveany.cli`)

The CLI is a Click group with the following commands:

- `copy` - Scan + copy missing/different files to dest (non-destructive)
- `move` - Scan, copy, then delete from source
- `verify` - Scan + compare contents; report verdict
- `repair` - Re-copy damaged files from source to dest
- `delete` - Manual-only delete phase (re-verifies each file)
- `list-batches` - Show the batched copy/move plan without executing
- `exclude` - Manage exclusion directory names (add/remove/list)
- `history` - Show recent operations from the SQLite log (--json for JSON)
- `config` - Inspect and manage persistent configuration (show / reset)
- `gui` - Launch the Tkinter graphical user interface

## GUI (`moveany.gui`)

- **`launch_gui()`** - Entry point to launch the MoveAny GUI application
- **`MoveAnyGUI`** - Tkinter-based desktop application class

## Package Configuration

- **`pyproject.toml`** - Project configuration, dependencies, entry points
- **`moveany/__init__.py`** - Package initialization, version string
- **`moveany.cli:cli`** - Click entry point (`moveany` command)