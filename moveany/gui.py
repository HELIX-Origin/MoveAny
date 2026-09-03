"""Minimal Tkinter-based desktop interface for MoveAny.

Follows the stepped workflow design:
- Source and Destination directory pickers
- Configurable exclusions
- Stepped operation selection (copy, move, verify, repair, delete, list-batches)
- Execution area with live text output
- Manual confirmation required for deletion
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

from moveany import __version__
from moveany.cfg import (
    effective_exclusions,
    load_state,
    save_state,
    DEFAULT_EXCLUDE_DIRS,
)
from moveany.cfg.storage import OperationLog
from moveany.modules import (
    batcher,
    mover,
    paths,
    repair as repair_mod,
    reporting,
    verify as verify_mod,
)
from moveany.modules.app_icon import set_window_icon


class TextReporter(reporting.Reporter):
    """Reporter extension that echoes output to a Tkinter Text widget."""

    def __init__(self, log_dir, log_callback):
        super().__init__(log_dir)
        self.log_callback = log_callback

    def write(self, name, line):
        super().write(name, line)

    def session(self, line):
        super().session(line)
        self.log_callback(f"[SESSION] {line}")

    def info(self, line):
        super().info(line)
        self.log_callback(f"[INFO] {line}")

    def error(self, line):
        super().error(line)
        self.log_callback(f"[ERROR] {line}")


class MoveAnyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"MoveAny GUI v{__version__}")
        self.geometry("860x680")
        self.minsize(700, 500)

        self._setup_style()
        self._build_ui()
        # Set application window and taskbar icon
        try:
            set_window_icon(self)
        except Exception:
            pass

    def _setup_style(self):
        style = ttk.Style(self)
        # Use a clean standard theme
        available_themes = style.theme_names()
        if "clam" in available_themes:
            style.theme_use("clam")

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding="12")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        title_lbl = ttk.Label(
            header_frame,
            text=f"MoveAny - Safe Folder Relocator v{__version__}",
            font=("Helvetica", 14, "bold"),
        )
        title_lbl.pack(side=tk.LEFT)

        # 2. Source / Destination Pickers
        paths_frame = ttk.LabelFrame(main_frame, text=" Paths ", padding="10")
        paths_frame.pack(fill=tk.X, pady=(0, 10))

        # Source
        ttk.Label(paths_frame, text="Source:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.src_var = tk.StringVar()
        self.src_entry = ttk.Entry(paths_frame, textvariable=self.src_var, width=65)
        self.src_entry.grid(row=0, column=1, padx=6, pady=4, sticky=tk.EW)
        self.src_btn = ttk.Button(paths_frame, text="Browse...", command=self._browse_src)
        self.src_btn.grid(row=0, column=2, padx=4, pady=4)

        # Destination
        ttk.Label(paths_frame, text="Destination:").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.dst_var = tk.StringVar()
        self.dst_entry = ttk.Entry(paths_frame, textvariable=self.dst_var, width=65)
        self.dst_entry.grid(row=1, column=1, padx=6, pady=4, sticky=tk.EW)
        self.dst_btn = ttk.Button(paths_frame, text="Browse...", command=self._browse_dst)
        self.dst_btn.grid(row=1, column=2, padx=4, pady=4)

        paths_frame.columnconfigure(1, weight=1)

        # 3. Settings / Exclusions
        cfg_frame = ttk.LabelFrame(main_frame, text=" Exclusions & Options ", padding="10")
        cfg_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(cfg_frame, text="Excluded Dirs:").grid(row=0, column=0, sticky=tk.W, pady=4)
        state = load_state()
        initial_excludes = ", ".join(effective_exclusions(state))
        self.exclude_var = tk.StringVar(value=initial_excludes)
        self.exclude_entry = ttk.Entry(cfg_frame, textvariable=self.exclude_var, width=50)
        self.exclude_entry.grid(row=0, column=1, padx=6, pady=4, sticky=tk.EW)

        self.dry_run_var = tk.BooleanVar(value=False)
        self.dry_run_check = ttk.Checkbutton(cfg_frame, text="Dry Run (simulate)", variable=self.dry_run_var)
        self.dry_run_check.grid(row=0, column=2, padx=6, pady=4)

        cfg_frame.columnconfigure(1, weight=1)

        # 4. Operation Workflow Selector
        op_frame = ttk.LabelFrame(main_frame, text=" Stepped Workflow ", padding="10")
        op_frame.pack(fill=tk.X, pady=(0, 10))

        self.op_var = tk.StringVar(value="copy")
        ops = [
            ("List Batches", "list-batches"),
            ("1. Copy (non-destructive)", "copy"),
            ("2. Verify", "verify"),
            ("3. Repair", "repair"),
            ("4. Move (Copy + Confirm Delete)", "move"),
            ("5. Delete Source (Manual Confirm)", "delete"),
        ]

        col = 0
        row = 0
        for label, val in ops:
            rb = ttk.Radiobutton(op_frame, text=label, value=val, variable=self.op_var)
            rb.grid(row=row, column=col, sticky=tk.W, padx=10, pady=4)
            col += 1
            if col > 2:
                col = 0
                row += 1

        # Run Button
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        self.run_btn = ttk.Button(action_frame, text="Run Selected Operation", command=self._run_op)
        self.run_btn.pack(side=tk.LEFT, padx=4)

        self.history_btn = ttk.Button(action_frame, text="View History", command=self._view_history)
        self.history_btn.pack(side=tk.LEFT, padx=4)

        self.clear_btn = ttk.Button(action_frame, text="Clear Log", command=self._clear_log)
        self.clear_btn.pack(side=tk.RIGHT, padx=4)

        # 5. Output / Progress Log Area
        log_frame = ttk.LabelFrame(main_frame, text=" Activity Log ", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def _browse_src(self):
        selected = filedialog.askdirectory(title="Select Source Directory")
        if selected:
            self.src_var.set(selected)

    def _browse_dst(self):
        selected = filedialog.askdirectory(title="Select Destination Directory")
        if selected:
            self.dst_var.set(selected)

    def append_log(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def _view_history(self):
        log = OperationLog()
        records = log.recent(limit=15)
        log.close()
        self.append_log("=== Recent SQLite History ===")
        if not records:
            self.append_log("(No history records found)")
            return
        for r in records:
            self.append_log(f"#{r['id']} {r['op']} [{r['status']}] src={r['src_root']} dest={r['dest_root']}")

    def _parse_excludes(self):
        val = self.exclude_var.get().strip()
        if not val:
            return set()
        return {x.strip() for x in val.split(",") if x.strip()}

    def _run_op(self):
        src = self.src_var.get().strip()
        dst = self.dst_var.get().strip()
        op = self.op_var.get()
        dry_run = self.dry_run_var.get()

        if not src or not os.path.exists(src):
            messagebox.showerror("Error", "Please select a valid Source directory.")
            return

        if op != "list-batches" and not dst:
            messagebox.showerror("Error", "Please select a valid Destination directory.")
            return

        if dst and os.path.abspath(src) == os.path.abspath(dst):
            messagebox.showerror("Error", "Source and Destination cannot be the same directory.")
            return

        if op in ("delete", "move") and not dry_run:
            msg = "This operation will permanently delete files from the source directory after verifying their destination copy.\n\nProceed with deletion?"
            if not messagebox.askyesno("Confirm Deletion", msg):
                self.append_log("[ABORT] Deletion cancelled by user.")
                return

        self.run_btn.config(state=tk.DISABLED)
        thread = threading.Thread(target=self._execute_thread, args=(op, src, dst, dry_run))
        thread.daemon = True
        thread.start()

    def _execute_thread(self, op, src, dst, dry_run):
        try:
            exclude = self._parse_excludes()
            src_norm = paths.normalize(src)
            dst_norm = paths.normalize(dst) if dst else ""

            if op == "list-batches":
                batches = batcher.split_batches(src_norm, dst_norm, exclude)
                self.after(0, self.append_log, f"=== BATCH PLAN ({len(batches)} batches) ===")
                for b in batches:
                    tag = " [scaffold]" if b.get("scaffold") else ""
                    self.after(0, self.append_log, f"  {b['name']} ({b['files']} files){tag}")
                return

            log_dir = ".moveany/logs"
            rep = TextReporter(os.path.abspath(log_dir), lambda msg: self.after(0, self.append_log, msg))
            log = OperationLog()
            op_id = log.start(op, src_norm, dst_norm)

            try:
                comp = verify_mod.compare(src_norm, dst_norm, exclude, rep, skip_top_dirs=exclude)

                if op == "verify":
                    damaged = verify_mod.report_compare(comp, rep, label="verify")
                    status = "ok" if damaged == 0 else "differences"
                    log.finish(op_id, status, json.dumps({
                        "identical": len(comp["identical"]),
                        "missing": len(comp["missing_on_dest"]),
                        "different": len(comp["different"]),
                    }))

                elif op == "copy":
                    if dry_run:
                        to_copy = len(set(comp["missing_on_dest"]) | set(comp["different"]))
                        self.after(0, self.append_log, f"DRY RUN: would copy {to_copy} files.")
                        log.finish(op_id, "ok", json.dumps({"dry_run": True, "to_copy": to_copy}))
                    else:
                        ready, summary = mover.copy_missing(comp, src_norm, dst_norm, rep)
                        status = "ok" if summary["errors"] == 0 else "errors"
                        log.finish(op_id, status, json.dumps(summary))

                elif op == "repair":
                    recovered, unrec, rels = repair_mod.repair_missing(comp, src_norm, dst_norm, rep)
                    status = "ok" if not unrec else "unrecoverable"
                    log.finish(op_id, status, json.dumps({"recovered": len(recovered), "unrecoverable": len(unrec)}))

                elif op == "move":
                    if dry_run:
                        to_copy = len(set(comp["missing_on_dest"]) | set(comp["different"]))
                        self.after(0, self.append_log, f"DRY RUN: would copy {to_copy} and delete identical files.")
                        log.finish(op_id, "ok", json.dumps({"dry_run": True}))
                    else:
                        ready, copy_summary = mover.copy_missing(comp, src_norm, dst_norm, rep)
                        if ready:
                            deleted, errors = mover.delete_phase(ready, src_norm, dst_norm, rep)
                            mover.remove_empty_dirs(src_norm, exclude, rep)
                            status = "ok" if errors == 0 else "errors"
                            log.finish(op_id, status, json.dumps({"copied": copy_summary["copied"], "deleted": deleted}))
                        else:
                            log.finish(op_id, "ok", json.dumps({"copied": 0, "deleted": 0}))

                elif op == "delete":
                    if comp["missing_on_dest"] or comp["different"]:
                        self.after(0, self.append_log, "REFUSING delete: source files missing/different on dest!")
                        log.finish(op_id, "refused")
                    else:
                        ready = comp["identical"]
                        if dry_run:
                            self.after(0, self.append_log, f"DRY RUN: would delete {len(ready)} files.")
                            log.finish(op_id, "ok", json.dumps({"dry_run": True, "ready": len(ready)}))
                        else:
                            deleted, errors = mover.delete_phase(ready, src_norm, dst_norm, rep)
                            mover.remove_empty_dirs(src_norm, exclude, rep)
                            status = "ok" if errors == 0 else "errors"
                            log.finish(op_id, status, json.dumps({"deleted": deleted, "errors": errors}))
            finally:
                rep.close()
                log.close()

            self.after(0, self.append_log, f"\n=== OPERATION '{op.upper()}' COMPLETE ===")
        except Exception as ex:
            self.after(0, self.append_log, f"\n[CRITICAL ERROR] {ex}")
        finally:
            self.after(0, lambda: self.run_btn.config(state=tk.NORMAL))


def launch_gui():
    """Entry point to launch the MoveAny GUI application."""
    app = MoveAnyGUI()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
