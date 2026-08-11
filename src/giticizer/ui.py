from __future__ import annotations

import re
import threading
import tkinter as tk
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from queue import Empty, Queue
from time import monotonic
from tkinter import filedialog, messagebox, ttk
from typing import Any, cast

from giticizer.analysis.helptext import render_analysis_help
from giticizer.cli import ANALYSES
from giticizer.integrations.mapping import apply_group_mapping
from giticizer.models import Commit
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
        self.include_dirs = tk.StringVar(value="")
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
        self._commit_cache: dict[tuple[str, str, str, bool, tuple[str, ...]], list[Commit]] = {}
        self._parse_time_cache: dict[tuple[str, str, str, bool, tuple[str, ...]], float] = {}
        self._is_parsing = False
        self._parse_started_at = 0.0
        self._parse_eta_seconds: float | None = None
        self._parse_result_queue: Queue[tuple[str, object]] = Queue()
        self._table_rows_original: list[Row] = []
        self._table_columns: list[str] = []
        self._sort_column: str | None = None
        self._sort_mode = 0

        self._build()
        self._bind_log_inputs()
        self._sync_analysis_state()

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

        include_row = ttk.Frame(frame)
        include_row.pack(fill="x", pady=(6, 0))
        ttk.Label(include_row, text="Include Dirs (comma-separated)").pack(side="left")
        ttk.Entry(include_row, textvariable=self.include_dirs, width=50).pack(side="left", padx=6)

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
        self.parse_button = ttk.Button(buttons, text="Parse Log", command=self.parse_log)
        self.parse_button.pack(side="left")
        self.run_button = ttk.Button(buttons, text="Run Analysis", command=self.run_analysis)
        self.run_button.pack(side="left", padx=6)
        ttk.Button(buttons, text="Clear", command=self.clear).pack(side="left", padx=6)
        self.parse_progress = ttk.Progressbar(buttons, mode="indeterminate", length=150)
        self.parse_eta_text = tk.StringVar(value="")
        self.parse_eta_label = ttk.Label(buttons, textvariable=self.parse_eta_text)

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)

        table_page = ttk.Frame(notebook)
        notebook.add(table_page, text="Analysis Results")
        table_wrap = ttk.Frame(table_page)
        table_wrap.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_wrap, show="headings")
        self.table.pack(side="left", fill="both", expand=True)
        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.table.yview)
        yscroll.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=yscroll.set)

        cards_page = ttk.Frame(notebook)
        notebook.add(cards_page, text="Daily Refactoring Cards")
        self.cards_canvas = tk.Canvas(cards_page, highlightthickness=0)
        self.cards_canvas.pack(side="left", fill="both", expand=True)
        cards_scroll = ttk.Scrollbar(
            cards_page,
            orient="vertical",
            command=self.cards_canvas.yview,
        )
        cards_scroll.pack(side="right", fill="y")
        self.cards_canvas.configure(yscrollcommand=cards_scroll.set)
        self.cards_container = ttk.Frame(self.cards_canvas)
        self.cards_canvas.create_window((0, 0), window=self.cards_container, anchor="nw")
        self.cards_container.bind(
            "<Configure>",
            lambda _: self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all")),
        )
        self.cards_canvas.bind(
            "<Configure>",
            lambda event: self.cards_canvas.itemconfigure("all", width=event.width),
        )

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

    def _bind_log_inputs(self) -> None:
        for var in (self.repo, self.vcs_mode, self.after, self.include_dirs):
            var.trace_add("write", self._on_log_filters_changed)
        self.ignore_merges.trace_add("write", self._on_log_filters_changed)

    def _on_log_filters_changed(self, *_: object) -> None:
        self._sync_analysis_state()

    def _sync_analysis_state(self) -> None:
        if self._is_parsing:
            self.run_button.configure(state="disabled")
            return
        self.run_button.configure(
            state="normal" if self._current_log_key() in self._commit_cache else "disabled"
        )

    def clear(self) -> None:
        self.table.delete(*self.table.get_children())
        self.table["columns"] = ()
        self._table_rows_original = []
        self._table_columns = []
        self._sort_column = None
        self._sort_mode = 0
        for widget in self.cards_container.winfo_children():
            widget.destroy()
        self.status.set("Cleared")

    def parse_log(self) -> None:
        if self._is_parsing:
            return
        try:
            repo = Path(self.repo.get()).expanduser().resolve()
            if not (repo / ".git").exists():
                raise ValueError("Selected folder is not a git repository")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Parse Error", str(exc))
            self.status.set("Failed")
            return

        key = self._current_log_key(repo)
        if key in self._commit_cache:
            self.status.set("Log already parsed for current filters (cache hit)")
            self._sync_analysis_state()
            return

        self._is_parsing = True
        self._parse_started_at = monotonic()
        self._parse_eta_seconds = self._estimate_parse_seconds(key)
        self.parse_button.configure(state="disabled")
        self.run_button.configure(state="disabled")
        self.parse_progress.pack(side="left", padx=8)
        self.parse_eta_label.pack(side="left")
        self.parse_progress.start(12)
        self.status.set("Parsing git log...")
        self._update_parse_eta_text()

        mode = self.vcs_mode.get()
        after = self.after.get().strip() or None
        no_merges = self.ignore_merges.get()
        include_dirs = self._split_csv(self.include_dirs.get())
        worker = threading.Thread(
            target=self._parse_log_worker,
            args=(repo, key, mode, after, no_merges, include_dirs),
            daemon=True,
        )
        worker.start()
        self.root.after(100, self._poll_parse_result)
        self.root.after(250, self._tick_parse_eta)

    def _parse_log_worker(
        self,
        repo: Path,
        key: tuple[str, str, str, bool, tuple[str, ...]],
        mode: str,
        after: str | None,
        no_merges: bool,
        include_dirs: list[str],
    ) -> None:
        try:
            raw = read_git_log(
                repo,
                mode=mode,
                after=after,
                no_merges=no_merges,
                include_dirs=include_dirs,
                excludes=[],
            )
            parsed = parse_log(raw, mode=mode)
            self._parse_result_queue.put(("ok", (key, parsed)))
        except Exception as exc:  # noqa: BLE001
            self._parse_result_queue.put(("err", exc))

    def _poll_parse_result(self) -> None:
        if not self._is_parsing:
            return
        try:
            status, payload = self._parse_result_queue.get_nowait()
        except Empty:
            self.root.after(100, self._poll_parse_result)
            return

        if status == "ok":
            key, parsed = cast(
                tuple[tuple[str, str, str, bool, tuple[str, ...]], list[Commit]],
                payload,
            )
            self._finish_parse_success(key, parsed)
            return

        self._finish_parse_error(cast(Exception, payload))

    def _tick_parse_eta(self) -> None:
        if not self._is_parsing:
            return
        self._update_parse_eta_text()
        self.root.after(250, self._tick_parse_eta)

    def _update_parse_eta_text(self) -> None:
        elapsed = max(0.0, monotonic() - self._parse_started_at)
        if self._parse_eta_seconds is None:
            self.parse_eta_text.set(f"Elapsed {elapsed:.1f}s")
            return
        remaining = max(0.0, self._parse_eta_seconds - elapsed)
        self.parse_eta_text.set(f"Elapsed {elapsed:.1f}s | ETA {remaining:.1f}s")

    def _estimate_parse_seconds(
        self,
        key: tuple[str, str, str, bool, tuple[str, ...]],
    ) -> float | None:
        exact = self._parse_time_cache.get(key)
        if exact is not None:
            return exact
        repo_prefix = key[0]
        repo_samples = [
            seconds
            for cache_key, seconds in self._parse_time_cache.items()
            if cache_key[0] == repo_prefix
        ]
        if repo_samples:
            return sum(repo_samples) / len(repo_samples)
        if self._parse_time_cache:
            all_samples = list(self._parse_time_cache.values())
            return sum(all_samples) / len(all_samples)
        return None

    def _finish_parse_success(
        self,
        key: tuple[str, str, str, bool, tuple[str, ...]],
        parsed: list[Commit],
    ) -> None:
        self._commit_cache[key] = parsed
        self._parse_time_cache[key] = max(0.0, monotonic() - self._parse_started_at)
        self._is_parsing = False
        self.parse_progress.stop()
        self.parse_progress.pack_forget()
        self.parse_eta_text.set("")
        self.parse_eta_label.pack_forget()
        self.parse_button.configure(state="normal")
        self._sync_analysis_state()
        self.status.set(f"Parsed {len(parsed)} commits. Analysis enabled.")

    def _finish_parse_error(self, exc: Exception) -> None:
        self._is_parsing = False
        self.parse_progress.stop()
        self.parse_progress.pack_forget()
        self.parse_eta_text.set("")
        self.parse_eta_label.pack_forget()
        self.parse_button.configure(state="normal")
        self._sync_analysis_state()
        messagebox.showerror("Parse Error", str(exc))
        self.status.set("Failed")

    def run_analysis(self) -> None:
        try:
            repo = Path(self.repo.get()).expanduser().resolve()
            if not (repo / ".git").exists():
                raise ValueError("Selected folder is not a git repository")

            key = self._current_log_key(repo)
            cached = self._commit_cache.get(key)
            if cached is None:
                raise ValueError("Log is not parsed for current filters. Click 'Parse Log' first.")
            commits = list(cached)

            mapping = self.group_file.get().strip()
            if mapping:
                commits = apply_group_mapping(commits, Path(mapping))
            refactor_cards = self._build_refactoring_cards(commits)
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
            self.render_refactoring_cards(refactor_cards)
            self.status.set(
                f"{self.analysis.get()}: {len(rows[:limit])} rows shown, "
                f"{len(refactor_cards)} refactoring day cards (cache hit)"
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Analysis Error", str(exc))
            self.status.set("Failed")

    def render_rows(self, rows: list[Row]) -> None:
        self.table.delete(*self.table.get_children())
        if not rows:
            self.table["columns"] = ()
            self._table_rows_original = []
            self._table_columns = []
            self._sort_column = None
            self._sort_mode = 0
            return

        columns = list(rows[0].keys())
        self._table_rows_original = list(rows)
        self._table_columns = columns
        self._sort_column = None
        self._sort_mode = 0
        self.table["columns"] = columns
        for name in columns:
            self.table.heading(name, text=name, command=lambda col=name: self._on_sort_column(col))
            self.table.column(name, width=150, anchor="w")

        self._render_table_values(self._table_rows_original)

    def _render_table_values(self, rows: list[Row]) -> None:
        self.table.delete(*self.table.get_children())
        for row in rows:
            self.table.insert("", "end", values=[row.get(c, "") for c in self._table_columns])

    def _on_sort_column(self, column: str) -> None:
        if not self._table_rows_original:
            return
        if self._sort_column == column:
            self._sort_mode = (self._sort_mode + 1) % 3
        else:
            self._sort_column = column
            self._sort_mode = 1

        if self._sort_mode == 0:
            rows = list(self._table_rows_original)
        else:
            rows = sorted(
                self._table_rows_original,
                key=lambda row: self._sort_value(row.get(column)),
                reverse=self._sort_mode == 2,
            )

        self._refresh_sort_headers()
        self._render_table_values(rows)

    def _refresh_sort_headers(self) -> None:
        for name in self._table_columns:
            suffix = ""
            if name == self._sort_column:
                if self._sort_mode == 1:
                    suffix = " ▲"
                elif self._sort_mode == 2:
                    suffix = " ▼"
            self.table.heading(
                name,
                text=f"{name}{suffix}",
                command=lambda col=name: self._on_sort_column(col),
            )

    @staticmethod
    def _sort_value(value: object) -> tuple[int, object]:
        if value is None:
            return (3, "")
        if isinstance(value, bool):
            return (0, int(value))
        if isinstance(value, int | float):
            return (0, float(value))
        if isinstance(value, str):
            text = value.strip()
            try:
                return (0, float(text))
            except ValueError:
                return (1, text.lower())
        return (2, str(value).lower())

    def render_refactoring_cards(self, cards: list[Row]) -> None:
        for widget in self.cards_container.winfo_children():
            widget.destroy()
        if not cards:
            ttk.Label(
                self.cards_container,
                text="No refactoring-like activity found for current filters.",
            ).pack(anchor="w", pady=8, padx=8)
            return

        for card in cards:
            panel = ttk.LabelFrame(
                self.cards_container,
                text=f"{card['date']}  |  {card['refactor-commits']} refactor commits",
                padding=10,
            )
            panel.pack(fill="x", padx=8, pady=6)
            ttk.Label(panel, text=f"Authors: {card['authors']}").pack(anchor="w")
            ttk.Label(
                panel,
                text=f"Entities touched: {card['entities']}",
            ).pack(anchor="w", pady=(4, 0))
            ttk.Label(
                panel,
                text=f"Top entities: {card['top-entities']}",
            ).pack(anchor="w", pady=(4, 0))
            ttk.Label(panel, text=f"Example messages: {card['messages']}", wraplength=1080).pack(
                anchor="w",
                pady=(4, 0),
            )

    @staticmethod
    def _split_csv(raw: str) -> list[str]:
        return [part.strip() for part in raw.split(",") if part.strip()]

    def _current_log_key(
        self,
        repo: Path | None = None,
    ) -> tuple[str, str, str, bool, tuple[str, ...]]:
        resolved_repo = repo or Path(self.repo.get()).expanduser().resolve()
        return (
            resolved_repo.as_posix(),
            self.vcs_mode.get(),
            self.after.get().strip(),
            self.ignore_merges.get(),
            tuple(sorted(self._split_csv(self.include_dirs.get()))),
        )

    @staticmethod
    def _build_refactoring_cards(commits: list[Any]) -> list[Row]:
        matcher = re.compile(r"\b(refactor|cleanup|restructure|rename)\b", re.I)
        by_day: dict[str, list[Any]] = defaultdict(list)
        for commit in commits:
            if matcher.search(commit.message):
                by_day[commit.date.isoformat()].append(commit)

        cards: list[Row] = []
        for day in sorted(by_day.keys(), reverse=True):
            chunk = by_day[day]
            authors = sorted({c.author for c in chunk})
            touched = [f.path for c in chunk for f in c.files]
            top = Counter(touched).most_common(3)
            messages = [c.message for c in chunk if c.message][:3]
            cards.append(
                {
                    "date": day,
                    "refactor-commits": len(chunk),
                    "authors": ", ".join(authors) if authors else "n/a",
                    "entities": len(set(touched)),
                    "top-entities": ", ".join(f"{name} ({count})" for name, count in top)
                    if top
                    else "n/a",
                    "messages": " | ".join(messages) if messages else "n/a",
                }
            )
        return cards


def run_ui() -> None:
    root = tk.Tk()
    GiticizerUI(root)
    root.mainloop()
