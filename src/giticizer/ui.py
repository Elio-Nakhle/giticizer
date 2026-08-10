from __future__ import annotations

import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from giticizer.analysis.helptext import render_analysis_help
from giticizer.cli import ANALYSES
from giticizer.integrations.mapping import apply_group_mapping
from giticizer.vcs.git_reader import read_git_log
from giticizer.vcs.parsers import aggregate_daily, parse_log

Row = dict[str, Any]


class GiticizerUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Giticizer")
        self.root.geometry("1200x760")

        self.repo = tk.StringVar(value=str(Path.cwd()))
        self.analysis = tk.StringVar(value="summary")
        self.vcs_mode = tk.StringVar(value="git2")
        self.after = tk.StringVar(value="")
        self.rows = tk.StringVar(value="200")
        self.group_file = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready")

        self.temporal = tk.BooleanVar(value=False)
        self.ignore_merges = tk.BooleanVar(value=False)
        self.verbose = tk.BooleanVar(value=False)

        self.min_revs = tk.StringVar(value="5")
        self.min_shared_revs = tk.StringVar(value="5")
        self.min_coupling = tk.StringVar(value="30")
        self.max_coupling = tk.StringVar(value="100")
        self.max_changeset_size = tk.StringVar(value="30")
        self.expression = tk.StringVar(value="")

        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=8)
        frame.pack(fill="both", expand=True)

        top = ttk.Frame(frame)
        top.pack(fill="x")

        ttk.Label(top, text="Repository").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.repo, width=78).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(top, text="Select Folder", command=self.select_repo).grid(row=0, column=2)

        ttk.Label(top, text="Analysis").grid(row=1, column=0, sticky="w", pady=(6, 0))
        combo = ttk.Combobox(
            top,
            textvariable=self.analysis,
            state="readonly",
            values=sorted(ANALYSES.keys()),
            width=26,
        )
        combo.grid(row=1, column=1, sticky="w", padx=6, pady=(6, 0))
        combo.bind("<<ComboboxSelected>>", self._on_analysis_change)

        ttk.Label(top, text="VCS").grid(row=1, column=2, sticky="e", pady=(6, 0))
        ttk.Combobox(
            top,
            textvariable=self.vcs_mode,
            state="readonly",
            values=["git", "git2"],
            width=8,
        ).grid(row=1, column=3, sticky="w", padx=(6, 0), pady=(6, 0))

        opts = ttk.Frame(frame)
        opts.pack(fill="x", pady=8)

        self._labeled_entry(opts, "After", self.after, 0)
        self._labeled_entry(opts, "Rows", self.rows, 1)
        self._labeled_entry(opts, "Min Revs", self.min_revs, 2)
        self._labeled_entry(opts, "Min Shared", self.min_shared_revs, 3)
        self._labeled_entry(opts, "Min Coupling", self.min_coupling, 4)
        self._labeled_entry(opts, "Max Coupling", self.max_coupling, 5)
        self._labeled_entry(opts, "Max ChangeSet", self.max_changeset_size, 6)

        flags = ttk.Frame(frame)
        flags.pack(fill="x")
        ttk.Checkbutton(flags, text="Temporal Daily", variable=self.temporal).pack(side="left")
        ttk.Checkbutton(flags, text="Ignore Merges", variable=self.ignore_merges).pack(
            side="left", padx=8
        )
        ttk.Checkbutton(flags, text="Verbose", variable=self.verbose).pack(side="left", padx=8)

        map_row = ttk.Frame(frame)
        map_row.pack(fill="x", pady=8)
        ttk.Label(map_row, text="Mapping File").pack(side="left")
        ttk.Entry(map_row, textvariable=self.group_file, width=70).pack(side="left", padx=6)
        ttk.Button(map_row, text="Select Mapping", command=self.select_mapping).pack(side="left")

        msg_row = ttk.Frame(frame)
        msg_row.pack(fill="x")
        ttk.Label(msg_row, text="Message Regex").pack(side="left")
        ttk.Entry(msg_row, textvariable=self.expression, width=40).pack(side="left", padx=6)

        explain = ttk.LabelFrame(frame, text="Analysis Meaning & Usefulness", padding=8)
        explain.pack(fill="x", pady=(8, 0))
        self.analysis_help = tk.StringVar(value=render_analysis_help(self.analysis.get()))
        ttk.Label(
            explain,
            textvariable=self.analysis_help,
            justify="left",
            anchor="w",
            wraplength=1120,
        ).pack(fill="x")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Run Analysis", command=self.run_analysis).pack(side="left")
        ttk.Button(buttons, text="Clear", command=self.clear).pack(side="left", padx=6)

        table_wrap = ttk.Frame(frame)
        table_wrap.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_wrap, show="headings")
        self.table.pack(side="left", fill="both", expand=True)
        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.table.yview)
        yscroll.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=yscroll.set)

        ttk.Label(frame, textvariable=self.status, anchor="w").pack(fill="x", pady=(6, 0))
        top.columnconfigure(1, weight=1)

    @staticmethod
    def _labeled_entry(parent: ttk.Frame, label: str, var: tk.StringVar, column: int) -> None:
        box = ttk.Frame(parent)
        box.grid(row=0, column=column, padx=4, sticky="w")
        ttk.Label(box, text=label).pack(anchor="w")
        ttk.Entry(box, textvariable=var, width=10).pack(anchor="w")

    def select_repo(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.repo.get() or str(Path.cwd()))
        if chosen:
            self.repo.set(chosen)

    def select_mapping(self) -> None:
        chosen = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if chosen:
            self.group_file.set(chosen)

    def _on_analysis_change(self, _: object) -> None:
        self.analysis_help.set(render_analysis_help(self.analysis.get()))

    def clear(self) -> None:
        self.table.delete(*self.table.get_children())
        self.table["columns"] = ()
        self.status.set("Cleared")

    def run_analysis(self) -> None:
        try:
            repo = Path(self.repo.get()).expanduser().resolve()
            if not (repo / ".git").exists():
                raise ValueError("Selected folder is not a git repository")

            raw = read_git_log(
                repo,
                mode=self.vcs_mode.get(),
                after=self.after.get().strip() or None,
                no_merges=self.ignore_merges.get(),
                include_dirs=[],
                excludes=[],
            )
            commits = parse_log(raw, mode=self.vcs_mode.get())

            mapping = self.group_file.get().strip()
            if mapping:
                commits = apply_group_mapping(commits, Path(mapping))
            if self.temporal.get():
                commits = aggregate_daily(commits)

            fn = ANALYSES[self.analysis.get()]
            kwargs: dict[str, Any] = {
                "min_revs": int(self.min_revs.get() or "5"),
                "min_shared_revs": int(self.min_shared_revs.get() or "5"),
                "min_coupling": int(self.min_coupling.get() or "30"),
                "max_coupling": int(self.max_coupling.get() or "100"),
                "max_changeset_size": int(self.max_changeset_size.get() or "30"),
                "expression": self.expression.get().strip() or None,
                "age_time_now": date.today(),
                "verbose": self.verbose.get(),
            }
            accepted = fn.__code__.co_varnames[: fn.__code__.co_argcount]
            rows = fn(commits, **{k: v for k, v in kwargs.items() if k in accepted})
            limit = int(self.rows.get() or "200")
            self.render_rows(rows[:limit])
            self.status.set(f"{self.analysis.get()}: {len(rows[:limit])} rows shown")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Analysis Error", str(exc))
            self.status.set("Failed")

    def render_rows(self, rows: list[Row]) -> None:
        self.table.delete(*self.table.get_children())
        if not rows:
            self.table["columns"] = ()
            return

        columns = list(rows[0].keys())
        self.table["columns"] = columns
        for name in columns:
            self.table.heading(name, text=name)
            self.table.column(name, width=150, anchor="w")

        for row in rows:
            self.table.insert("", "end", values=[row.get(c, "") for c in columns])


def run_ui() -> None:
    root = tk.Tk()
    GiticizerUI(root)
    root.mainloop()
