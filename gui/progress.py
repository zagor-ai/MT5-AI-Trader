"""Phase-aware progress widgets for the research pipeline."""
import tkinter as tk
from tkinter import ttk


class ProgressPanel(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.phase = tk.StringVar(value="PHASE: IDLE")
        self.percent = tk.StringVar(value="Progress: 0%")
        self.detail = tk.StringVar(value="Candidates: 0 / 0")
        ttk.Label(self, textvariable=self.phase, width=24).pack(side="left", padx=5)
        self.bar = ttk.Progressbar(self, orient="horizontal", mode="determinate", maximum=100)
        self.bar.pack(side="left", fill="x", expand=True, padx=10)
        ttk.Label(self, textvariable=self.percent, width=15).pack(side="left", padx=5)
        ttk.Label(self, textvariable=self.detail, width=28).pack(side="left", padx=5)

    def set_phase(self, phase: str):
        self.phase.set(f"PHASE: {phase.upper()}")

    def update_progress(self, current: int, total: int, detail: str | None = None):
        total = max(0, int(total))
        current = max(0, min(int(current), total)) if total else 0
        pct = (100.0 * current / total) if total else 0.0
        self.bar["value"] = pct
        self.percent.set(f"Progress: {pct:.0f}%")
        self.detail.set(detail or f"Candidates: {current} / {total}")

    def reset(self):
        self.set_phase("IDLE")
        self.update_progress(0, 0, "Candidates: 0 / 0")
