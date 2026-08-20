"""Progress widgets for candidate research."""
import tkinter as tk
from tkinter import ttk


class ProgressPanel(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.percent = tk.StringVar(value="Progress: 0%")
        self.candidates = tk.StringVar(value="Candidates: 0 / 0")
        ttk.Label(self, textvariable=self.percent).pack(side="left", padx=5)
        self.bar = ttk.Progressbar(self, orient="horizontal", mode="determinate", maximum=100)
        self.bar.pack(side="left", fill="x", expand=True, padx=10)
        ttk.Label(self, textvariable=self.candidates).pack(side="left", padx=5)

    def update_progress(self, current: int, total: int):
        total = max(0, int(total))
        current = max(0, min(int(current), total)) if total else 0
        pct = (100.0 * current / total) if total else 0.0
        self.bar["value"] = pct
        self.percent.set(f"Progress: {pct:.0f}%")
        self.candidates.set(f"Candidates: {current} / {total}")
