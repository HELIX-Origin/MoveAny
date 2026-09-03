# MoveAny

> Safely relocate folders with files over Windows `MAX_PATH` limits — or any files, any platform.

MoveAny is a cross-platform Python CLI (and desktop GUI) for **moving directories safely** with full
verification, staged deletion, and SQLite operation history. No file is deleted until it has been
independently verified at the destination.

---

## Install

Requires **Python 3.10+**. Tkinter is needed for the GUI (standard on Windows and macOS; on Linux
install `python3-tk`).

```bash
pip install -e .            # editable install (recommended for development)
pip install -e ".[dev]"     # include pytest + ruff for development
```

Or run without installing:

```bash
python -m moveany --help
```

---

## Commands

```
moveany copy           Scan + copy missing/different files to dest (non-destructive)
moveany move           Scan, copy, then delete from source in one workflow
moveany verify         Scan + compare contents; report a pass/fail verdict
moveany repair         Re-copy missing/damaged files from source to dest
moveany delete         Manual-only delete phase; re-verifies every file
moveany list-batches   Preview the batched plan without executing anything
moveany exclude        Manage excluded directory names (add / remove / list / reset)
moveany history        Show recent operations from the SQLite log
moveany config         Inspect and manage persistent configuration
moveany gui            Launch the Tkinter graphical user interface
```

### Copy & verify

```bash
# Preview what would be copied (no changes made)
moveany list-batches --source D:\Projects --dest E:\Backup

# Copy missing/different files (never deletes anything)
moveany copy --source D:\Projects --dest E:\Backup

# Verify both trees are content-identical
moveany verify --source D:\Projects --dest E:\Backup

# Dry-run any command to see what would happen
moveany copy --source D:\Projects --dest E:\Backup --dry-run
```

### Repair

```bash
# Re-copy missing or damaged files after an interrupted copy
moveany repair --source D:\Projects --dest E:\Backup
```

### Delete

```bash
# Delete source files — requires --yes, refuses if anything differs
moveany delete --source D:\Projects --dest E:\Backup --yes
```

### Full move workflow

```bash
moveany move --source D:\Projects --dest E:\Backup --yes
```

### History

```bash
# Table view (default)
moveany history --limit 20

# Filter by operation type
moveany history --op copy --limit 10

# JSON output (useful for scripting/pipelines)
moveany history --limit 5 --json
```

### Configuration

```bash
# Show current effective config as JSON
moveany config show

# Reset all exclusion overrides to defaults
moveany config reset --yes
```

### GUI

```bash
# Launch the graphical user interface
moveany gui
```

The GUI walks you through the same staged workflow (Pick → Batch → Copy → Verify → Repair → Move →
Delete) with real-time log output and confirmation dialogs before any destructive action.

---

## Exclusions

Directories like `node_modules`, `_build`, and `releases` are excluded by default (build-on-demand
artifacts). **`.git` is intentionally _not_ excluded** — repository history must be copied.

```bash
moveany exclude list                     # show effective exclusion set
moveany exclude list --available         # also show all known build artifacts
moveany exclude add dist                 # persist an addition
moveany exclude remove node_modules      # persist a removal
moveany exclude reset                    # reset to defaults
```

---

## Safety model

| Guarantee | How |
|---|---|
| **Copy first** | The copy phase is non-destructive and never deletes. |
| **Staged deletion** | Every file is copied to a staging area and SHA-256-verified before the source is removed. |
| **Manual delete only** | `delete` and `move` require `--yes` and re-verify each file just before deletion. |
| **Abort on mismatch** | Delete phase refuses to run if any source file is missing or differs from the destination. |
| **Full audit log** | Per-category log files + SQLite operation history (queryable with `moveany history`). |

---

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Lint
ruff check moveany/ tests/
```

Tests cover: safety/staged-deletion, batcher determinism, path normalization, and full CLI
integration (copy → verify → repair → delete cycle) using `click.testing.CliRunner` on disposable
temporary directories.

---

## Project layout

```
moveany/
  cli.py          CLI entry point (orchestration only — no engine logic here)
  config.py       CLI-level config
  gui.py          Tkinter GUI application
  cfg/            Config submodules (exclusions, state, SQLite storage)
  modules/        Engine modules — reusable by the GUI
    batcher.py    Split source tree into per-project batches
    files.py      Copy, SHA-256 compare, size verify
    mover.py      Copy + delete orchestration
    paths.py      Path normalization, UNC, symlink resolution
    repair.py     Re-copy missing/damaged files
    reporting.py  Structured log reporter
    safety.py     Staged deletion with copy-before-delete guarantee
    verify.py     Content comparison engine
  __main__.py     Enables `python -m moveany`

tests/
  test_safety.py  Staged deletion unit tests
  test_batcher.py Batcher determinism + exclusion tests
  test_paths.py   Path normalization tests
  test_cli.py     CLI integration tests (CliRunner)

.github/workflows/ci.yml   GitHub Actions CI (Windows, Ubuntu, macOS × Python 3.10-3.12)
```

The engine logic in `modules/` is deliberately decoupled from the CLI, using plain `source`/`dest`
parameters so the GUI can import it directly without any CLI dependency.
