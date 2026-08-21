"""Phase-aware progress widgets for the research pipeline."""
import tkinter as tk
from tkinter import ttk


class ProgressPanel(ttk.LabelFrame):
    """Compact pipeline progress with a clear current stage and sub-progress."""

    PHASES = ("DATA", "TRAIN / TEST", "WALK-FORWARD", "MONTE CARLO", "SENSITIVITY", "REGIME", "RANKING", "FINISHED")

    def __init__(self, master, **kwargs):
        super().__init__(master, text="RESEARCH PROGRESS", **kwargs)
        self.phase = tk.StringVar(value="PHASE: IDLE")
        self.percent = tk.StringVar(value="0%")
        self.detail = tk.StringVar(value="Ready")

        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=(4, 2))
        ttk.Label(top, textvariable=self.phase, width=22).pack(side="left")
        self.bar = ttk.Progressbar(top, orient="horizontal", mode="determinate", maximum=100)
        self.bar.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Label(top, textvariable=self.percent, width=6, anchor="e").pack(side="right")

        stages = ttk.Frame(self)
        stages.pack(fill="x", padx=6, pady=(2, 3))
        self.stage_labels = {}
        for phase in self.PHASES:
            label = ttk.Label(stages, text=phase, anchor="center")
            label.pack(side="left", fill="x", expand=True, padx=1)
            self.stage_labels[phase] = label

        ttk.Label(self, textvariable=self.detail, anchor="w").pack(fill="x", padx=8, pady=(0, 4))
        self._active_phase = None

    def set_phase(self, phase: str):
        phase = str(phase).upper()
        self._active_phase = phase
        self.phase.set(f"PHASE: {phase}")
        order = {name: i for i, name in enumerate(self.PHASES)}
        active_index = order.get(phase, -1)
        for name, label in self.stage_labels.items():
            if name == phase:
                label.configure(font=("TkDefaultFont", 9, "bold"))
            elif order.get(name, 99) < active_index:
                label.configure(font=("TkDefaultFont", 9, "normal"))
            else:
                label.configure(font=("TkDefaultFont", 9, "normal"))

    def update_progress(self, current: int, total: int, detail: str | None = None):
        total = max(0, int(total))
        current = max(0, min(int(current), total)) if total else 0
        pct = (100.0 * current / total) if total else 0.0
        self.bar["value"] = pct
        self.percent.set(f"{pct:.0f}%")
        self.detail.set(detail or f"Progress: {current} / {total}")

    def reset(self):
        self.set_phase("IDLE")
        self.update_progress(0, 0, "Ready")
