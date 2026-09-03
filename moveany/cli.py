"""MoveAny command-line interface (Click).

Subcommands:
  copy          scan + copy missing/different files to dest (non-destructive)
  move          scan, copy missing/different, then delete from source
  verify        scan + compare contents, report verdict
  repair        re-copy damaged files from source to dest
  delete        manual-only delete phase (re-verifies each file)
  list-batches  show the batched copy/move plan without executing
  exclude       manage exclusion directory names (add/remove/list)
  history       show recent operations from the SQLite log (--json for JSON)
  config        inspect and manage persistent configuration (show / reset)
  gui           launch the Tkinter graphical user interface

Engine modules live in `moveany.modules` and are reused by the future GUI.
Everything here is orchestration only - no move logic lives in the CLI.
"""

import datetime
import json
import os

import click

from moveany.cfg import (
    effective_exclusions,
    load_state,
    save_state,
    KNOWN_BUILD_ARTIFACTS,
)
from moveany.cfg.storage import OperationLog
from moveany import __version__
from moveany.modules import (
    batcher,
    mover,
    paths,
    repair as repair_mod,
    reporting,
    verify as verify_mod,
)
from moveany.modules.app_icon import set_cli_icon


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="moveany")
def cli():
    """MoveAny - safely relocate folders with files over path-length limits."""
    # Set console/app icon and AppUserModelID when the CLI process starts
    try:
        set_cli_icon()
    except Exception:
        pass


def _resolve_exclusions(extra_excludes):
    """Effective exclusions = defaults + user overrides + --exclude extras."""
    exclude = set(effective_exclusions(load_state()))
    for name in extra_excludes or ():
        exclude.add(name)
    return tuple(sorted(exclude))


def _make_reporter(log_dir):
    log_dir = log_dir or ".moveany/logs"
    return reporting.Reporter(os.path.abspath(log_dir))


def _require_input_dir(ctx, source):
    if not source:
        raise click.UsageError(
            "Source directory is required. Use --source <dir> or pass it as an argument."
        )


@cli.command()
@click.argument("source", required=False)
@click.option("--source", "source_opt")
@click.option("--dest", required=True, help="Destination root directory.")
@click.option("--exclude", "extra_excludes", multiple=True,
              help="Extra directory names to exclude (repeatable).")
@click.option("--log-dir", default=None, help="Log output directory.")
@click.option("--dry-run", is_flag=True, help="Show what would be copied without copying.")
def copy(source, source_opt, dest, extra_excludes, log_dir, dry_run):
    """Scan source and copy missing/different files to dest (non-destructive)."""
    src = source_opt or source
    _require_input_dir(None, src)
    src, dest = paths.normalize(src), paths.normalize(dest)
    exclude = _resolve_exclusions(extra_excludes)
    log = OperationLog()
    rep = _make_reporter(log_dir)
    op_id = log.start("copy", src, dest)

    rep.info(f"MoveAny copy {__version__}  source={src}  dest={dest}")
    rep.info(f"exclude dirs: {', '.join(exclude) or '(none)'}")
    if src == dest:
        rep.error("source and dest are the same directory; aborting.")
        log.finish(op_id, "failed", json.dumps({"error": "same source/dest"}))
        rep.close(); log.close()
        raise click.Abort()

    try:
        comp = verify_mod.compare(src, dest, set(exclude), rep, skip_top_dirs=exclude)
        damaged = verify_mod.report_compare(comp, rep, label="copy")

        if dry_run:
            to_copy = sorted(set(comp["missing_on_dest"]) | set(comp["different"]))
            rep.info(f"DRY RUN: would copy {len(to_copy)} files.")
            for rel in to_copy:
                rep.session(f"[dry-run] copy {rel}")
            status = "ok"
            summary = {"dry_run": True, "to_copy": len(to_copy),
                       "identical": len(comp["identical"])}
        else:
            ready, summary = mover.copy_missing(comp, src, dest, rep)
            rep.info(f"copy phase done. ready={len(ready)} errors={summary['errors']}")
            status = "ok" if summary["errors"] == 0 else "errors"
            summary = summary

        log.finish(op_id, status, json.dumps(summary))
        click.echo(f"Done ({status}). See logs in {rep.log_dir}.")
    finally:
        rep.close()
        log.close()


@cli.command()
@click.argument("source", required=False)
@click.option("--source", "source_opt")
@click.option("--dest", required=True, help="Destination root directory.")
@click.option("--exclude", "extra_excludes", multiple=True,
              help="Extra directory names to exclude (repeatable).")
@click.option("--log-dir", default=None, help="Log output directory.")
@click.option("--dry-run", is_flag=True, help="Show what would be moved without moving.")
@click.option("--yes", is_flag=True, help="Skip the manual confirmation prompt.")
def move(source, source_opt, dest, extra_excludes, log_dir, dry_run, yes):
    """Move files from source to dest: copy missing/different, then delete from source.

    Non-destructive by default: copies first, then prompts to delete.
    Use --yes to skip the delete confirmation prompt.
    """
    src = source_opt or source
    _require_input_dir(None, src)
    src, dest = paths.normalize(src), paths.normalize(dest)
    exclude = _resolve_exclusions(extra_excludes)
    log = OperationLog()
    rep = _make_reporter(log_dir)
    op_id = log.start("move", src, dest)

    rep.info(f"MoveAny move {__version__}  source={src}  dest={dest}")
    rep.info(f"exclude dirs: {', '.join(exclude) or '(none)'}")
    if src == dest:
        rep.error("source and dest are the same directory; aborting.")
        log.finish(op_id, "failed", json.dumps({"error": "same source/dest"}))
        rep.close(); log.close()
        raise click.Abort()

    try:
        comp = verify_mod.compare(src, dest, set(exclude), rep, skip_top_dirs=exclude)
        damaged = verify_mod.report_compare(comp, rep, label="move pre-check")

        if dry_run:
            to_copy = sorted(set(comp["missing_on_dest"]) | set(comp["different"]))
            rep.info(f"DRY RUN: would copy {len(to_copy)} files.")
            for rel in to_copy:
                rep.session(f"[dry-run] copy {rel}")
            # Also show what would be deleted (identical files after copy)
            summary = {"dry_run": True, "to_copy": len(to_copy),
                       "identical": len(comp["identical"]),
                       "would_delete": len(comp["identical"])}
            status = "ok"
            log.finish(op_id, status, json.dumps(summary))
            click.echo(f"Dry run done. See logs in {rep.log_dir}.")
            return

        # Phase 1: Copy missing/different files
        ready, copy_summary = mover.copy_missing(comp, src, dest, rep)
        rep.info(f"copy phase done. ready={len(ready)} errors={copy_summary['errors']}")

        if not ready:
            rep.info("No files needed copying. Nothing to move.")
            log.finish(op_id, "ok", json.dumps({"copied": 0, "deleted": 0}))
            click.echo("No files to move.")
            return

        # Phase 2: Delete from source (if not dry-run)
        if not dry_run:
            total_size_desc = f"{len(ready)} verified files"
            click.echo(f"{total_size_desc} will be deleted from source: {src}")
            if not yes:
                if not click.confirm("Proceed with deletion?", abort=True):
                    log.finish(op_id, "aborted", json.dumps({"copied": len(ready), "deleted": 0}))
                    rep.close(); log.close()
                    click.echo("Aborted. Files remain in destination, source unchanged.")
                    return

            deleted, errors = mover.delete_phase(ready, src, dest, rep)
            mover.remove_empty_dirs(src, set(exclude), rep)
            status = "ok" if errors == 0 else "errors"
            log.finish(op_id, status, json.dumps({
                "copied": copy_summary["copied"],
                "already_identical": copy_summary["already_identical"],
                "deleted": deleted,
                "errors": errors,
            }))
            click.echo(f"Move done ({status}): {copy_summary['copied']} copied, {deleted} deleted, {errors} errors.")
        else:
            # dry-run already finished above
            status = "ok"
            log.finish(op_id, status, json.dumps(copy_summary))
            click.echo(f"Dry run done. See logs in {rep.log_dir}.")

    finally:
        rep.close()
        log.close()


@cli.command()
@click.argument("source", required=False)
@click.option("--source", "source_opt")
@click.option("--dest", required=True, help="Destination root directory.")
@click.option("--exclude", "extra_excludes", multiple=True,
              help="Extra directory names to exclude (repeatable).")
@click.option("--log-dir", default=None, help="Log output directory.")
@click.option("--dry-run", is_flag=True, help="Show what would be compared without scanning.")
def verify(source, source_opt, dest, extra_excludes, log_dir, dry_run):
    """Scan both trees and compare contents; report a verdict."""
    src = source_opt or source
    _require_input_dir(None, src)
    src, dest = paths.normalize(src), paths.normalize(dest)
    exclude = _resolve_exclusions(extra_excludes)
    log = OperationLog()
    rep = _make_reporter(log_dir)
    op_id = log.start("verify", src, dest)

    rep.info(f"MoveAny verify {__version__}  source={src}  dest={dest}")
    if src == dest:
        rep.error("source and dest are the same directory; aborting.")
        log.finish(op_id, "failed", json.dumps({"error": "same source/dest"}))
        rep.close(); log.close()
        raise click.Abort()

    try:
        if dry_run:
            rep.info(f"DRY RUN: would compare source and dest.")
            click.echo("Dry run: would show comparison results without scanning.")
            log.finish(op_id, "ok", json.dumps({"dry_run": True}))
            rep.close(); log.close()
            return

        comp = verify_mod.compare(src, dest, set(exclude), rep, skip_top_dirs=exclude)
        damaged = verify_mod.report_compare(comp, rep, label="verify")
        status = "ok" if damaged == 0 else "differences"
        log.finish(op_id, status, json.dumps({
            "identical": len(comp["identical"]),
            "missing": len(comp["missing_on_dest"]),
            "different": len(comp["different"]),
            "extra": len(comp["extra_on_dest"]),
        }))
        click.echo(f"Verify done ({status}). See logs in {rep.log_dir}.")
    finally:
        rep.close()
        log.close()


@cli.command()
@click.argument("source", required=False)
@click.option("--source", "source_opt")
@click.option("--dest", required=True, help="Destination root directory.")
@click.option("--exclude", "extra_excludes", multiple=True,
              help="Extra directory names to exclude (repeatable).")
@click.option("--log-dir", default=None, help="Log output directory.")
@click.option("--dry-run", is_flag=True, help="Show what would be repaired without repairing.")
def repair(source, source_opt, dest, extra_excludes, log_dir, dry_run):
    """Re-copy missing/different files from source to dest."""
    src = source_opt or source
    _require_input_dir(None, src)
    src, dest = paths.normalize(src), paths.normalize(dest)
    exclude = _resolve_exclusions(extra_excludes)
    log = OperationLog()
    rep = _make_reporter(log_dir)
    op_id = log.start("repair", src, dest)

    rep.info(f"MoveAny repair {__version__}  source={src}  dest={dest}")
    if src == dest:
        rep.error("source and dest are the same directory; aborting.")
        log.finish(op_id, "failed", json.dumps({"error": "same source/dest"}))
        rep.close(); log.close()
        raise click.Abort()

    try:
        if dry_run:
            comp = verify_mod.compare(src, dest, set(exclude), rep, skip_top_dirs=exclude)
            to_recover = sorted(set(comp["missing_on_dest"]) | set(comp["different"]))
            rep.info(f"DRY RUN: would recover {len(to_recover)} files.")
            for rel in to_recover:
                rep.session(f"[dry-run] copy {rel}")
            summary = {"dry_run": True, "to_recover": len(to_recover),
                       "missing": len(comp["missing_on_dest"]),
                       "different": len(comp["different"])}
            log.finish(op_id, "ok", json.dumps(summary))
            click.echo(f"Dry run done. See logs in {rep.log_dir}.")
            return

        comp = verify_mod.compare(src, dest, set(exclude), rep, skip_top_dirs=exclude)
        recovered, unrecoverable, rels = repair_mod.repair_missing(comp, src, dest, rep)
        status = "ok" if not unrecoverable else "unrecoverable"
        log.finish(op_id, status, json.dumps({
            "attempted": len(rels),
            "recovered": len(recovered),
            "unrecoverable": len(unrecoverable),
        }))
        click.echo(f"Repair done ({status}). See logs in {rep.log_dir}.")
    finally:
        rep.close()
        log.close()


@cli.command()
@click.argument("source", required=False)
@click.option("--source", "source_opt")
@click.option("--dest", required=True, help="Destination root directory.")
@click.option("--exclude", "extra_excludes", multiple=True,
              help="Extra directory names to exclude (repeatable).")
@click.option("--log-dir", default=None, help="Log output directory.")
@click.option("--yes", is_flag=True, help="Skip the manual confirmation prompt.")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without deleting.")
def delete(source, source_opt, dest, extra_excludes, log_dir, yes, dry_run):
    """DELETE phase. Re-verifies each file before removing from source.

    Manual-only: requires explicit --yes. Refuses to run if any source file is
    missing or differs from dest.
    """
    src = source_opt or source
    _require_input_dir(None, src)
    src, dest = paths.normalize(src), paths.normalize(dest)
    exclude = _resolve_exclusions(extra_excludes)
    log = OperationLog()
    rep = _make_reporter(log_dir)
    op_id = log.start("delete", src, dest)

    rep.info(f"MoveAny delete {__version__}  source={src}  dest={dest}")
    if src == dest:
        rep.error("source and dest are the same directory; aborting.")
        log.finish(op_id, "failed", json.dumps({"error": "same source/dest"}))
        rep.close(); log.close()
        raise click.Abort()

    try:
        comp = verify_mod.compare(src, dest, set(exclude), rep, skip_top_dirs=exclude)
        damaged = verify_mod.report_compare(comp, rep, label="delete")
        if comp["missing_on_dest"] or comp["different"]:
            rep.error("REFUSING delete: files are missing/different on dest.")
            log.finish(op_id, "refused")
            click.echo("Refused: repair required before delete.")
            return

        ready = comp["identical"]
        if dry_run:
            # Show what would be deleted (identical files)
            summary = {"dry_run": True, "deleted": len(ready),
                       "total": len(ready),
                       "missing_on_dest": len(comp["missing_on_dest"]),
                       "different": len(comp["different"])}
            log.finish(op_id, "ok", json.dumps(summary))
            click.echo(f"DRY RUN: would delete {len(ready)} files from source: {src}")
            rep.close(); log.close()
            return

        total_size_desc = f"{len(ready)} verified files"
        click.echo(f"{total_size_desc} will be deleted from source: {src}")
        if not yes:
            if not click.confirm("Proceed with deletion?", abort=True):
                return
        deleted, errors = mover.delete_phase(ready, src, dest, rep)
        mover.remove_empty_dirs(src, set(exclude), rep)
        status = "ok" if errors == 0 else "errors"
        log.finish(op_id, status, json.dumps({"deleted": deleted, "errors": errors}))
        click.echo(f"Delete done ({status}): {deleted} deleted, {errors} errors.")
    finally:
        rep.close()
        log.close()


@cli.command()
@click.argument("source", required=False)
@click.option("--source", "source_opt")
@click.option("--dest", required=True, help="Destination root directory.")
@click.option("--exclude", "extra_excludes", multiple=True,
              help="Extra directory names to exclude (repeatable).")
def list_batches(source, source_opt, dest, extra_excludes):
    """Show the batched copy/move plan without executing anything."""
    src = source_opt or source
    _require_input_dir(None, src)
    src, dest = paths.normalize(src), paths.normalize(dest)
    exclude = _resolve_exclusions(extra_excludes)
    log = OperationLog()
    op_id = log.start("list-batches", src, dest)

    batches = batcher.split_batches(src, dest, set(exclude))
    click.echo(f"Source: {src}")
    click.echo(f"Destination: {dest}")
    click.echo(f"Excluded dirs: {', '.join(exclude) or '(none)'}")
    click.echo(f"Batch count: {len(batches)}")
    click.echo("")
    for b in batches:
        tag = " [scaffold]" if b.get("scaffold") else ""
        click.echo(f"  {b['name']}  ({b['files']} files){tag}")
        if b.get("skip_subdirs"):
            click.echo(f"      (skips child repos: {', '.join(b['skip_subdirs'])})")
    log.finish(op_id, "ok", json.dumps({"batches": len(batches)}))
    log.close()


@cli.group(name="exclude")
def exclude():
    """Manage exclusion directory names."""


@exclude.command("list")
@click.option("--available", is_flag=True,
              help="Also show known-but-not-active build artifact names.")
def exclude_list(available):
    """Show the effective exclusion set and its source."""
    state = load_state()
    effective = effective_exclusions(state)
    click.echo("Effective exclusions:")
    for name in effective:
        click.echo(f"  - {name}")
    if state["added"]:
        click.echo("User-added:")
        for name in sorted(state["added"]):
            click.echo(f"  + {name}")
    if state["removed"]:
        click.echo("User-removed from defaults:")
        for name in sorted(state["removed"]):
            click.echo(f"  - {name}")
    if available:
        active = set(effective)
        click.echo("Known build artifacts (not active):")
        for name in sorted(set(KNOWN_BUILD_ARTIFACTS) - active):
            click.echo(f"  ? {name}")


@exclude.command("add")
@click.argument("names", nargs=-1, required=True)
def exclude_add(names):
    """Add directory names to the exclusion set (persisted)."""
    state = load_state()
    for name in names:
        state["added"].add(name)
        state["removed"].discard(name)
    save_state(state)
    click.echo("Added. Effective exclusions: "
               + ", ".join(sorted(effective_exclusions(state))))


@exclude.command("remove")
@click.argument("names", nargs=-1, required=True)
def exclude_remove(names):
    """Remove directory names from the exclusion set (persisted)."""
    state = load_state()
    for name in names:
        state["added"].discard(name)
        if name in DEFAULT_EXCLUDE_DIRS:
            state["removed"].add(name)
    save_state(state)
    click.echo("Removed. Effective exclusions: "
               + ", ".join(sorted(effective_exclusions(state))))


@exclude.command("reset")
def exclude_reset():
    """Reset user add/remove overrides back to defaults."""
    save_state({"added": set(), "removed": set()})
    click.echo("Reset to defaults.")


@cli.command()
@click.option("--op", default=None, help="Filter history by operation type.")
@click.option("--limit", default=20, show_default=True, help="Rows to show.")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Output as JSON array instead of a table.")
def history(op, limit, as_json):
    """Show recent operations from the SQLite log."""
    log = OperationLog()
    rows = log.recent(limit=limit, op=op)
    if as_json:
        records = []
        for row in rows:
            records.append({
                "id": row["id"],
                "op": row["op"],
                "status": row["status"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "summary": row["summary"],
            })
        click.echo(json.dumps(records, indent=2))
    else:
        for row in rows:
            when = datetime.datetime.fromtimestamp(row["started_at"]).isoformat(
                timespec="seconds")
            summary = row["summary"] or ""
            click.echo(f"#{row['id']:>4} {row['op']:<14} {row['status']:<12} "
                       f"{when}  {summary}")
    log.close()


# ---------------------------------------------------------------------------
# config subcommand group
# ---------------------------------------------------------------------------

@cli.group()
def config():
    """Inspect and manage MoveAny persistent configuration."""


@config.command("show")
def config_show():
    """Print current effective configuration (exclusions, state)."""
    state = load_state()
    exclusions = list(effective_exclusions(state))
    data = {
        "exclusions": exclusions,
        "state": {
            "added": sorted(state.get("added", set())),
            "removed": sorted(state.get("removed", set())),
        },
    }
    click.echo(json.dumps(data, indent=2))


@config.command("reset")
@click.confirmation_option(prompt="Reset all config overrides to defaults?")
def config_reset():
    """Reset all user exclusion overrides back to defaults."""
    save_state({"added": set(), "removed": set()})
    click.echo("Configuration reset to defaults.")


# ---------------------------------------------------------------------------
# gui subcommand
# ---------------------------------------------------------------------------

@cli.command()
def gui():
    """Launch the MoveAny graphical user interface (Tkinter)."""
    try:
        from moveany.gui import launch_gui
    except ImportError as exc:
        raise click.ClickException(
            f"GUI dependencies unavailable: {exc}. "
            "Ensure tkinter is installed (python3-tk on Linux)."
        ) from exc
    launch_gui()


if __name__ == "__main__":
    cli()
