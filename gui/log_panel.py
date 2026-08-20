"""Thread-safe Tkinter log panel with convenient copy helpers."""
import tkinter as tk
from tkinter import ttk
from datetime import datetime


class LogPanel(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.text = tk.Text(self, height=16, wrap="none", state="disabled")
        self.text.pack(fill="both", expand=True, padx=5, pady=(5, 2))

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=5, pady=(2, 5))
        ttk.Button(buttons, text="COPY SUMMARY", command=self.copy_summary).pack(side="left")
        ttk.Button(buttons, text="COPY LAST 50", command=self.copy_last_50).pack(side="left", padx=5)
        ttk.Button(buttons, text="COPY ERRORS", command=self.copy_errors).pack(side="left")
        ttk.Button(buttons, text="COPY LOG", command=self.copy_log).pack(side="left", padx=5)
        ttk.Button(buttons, text="CLEAR LOG", command=self.clear).pack(side="left")

    def write(self, message: str, level: str = "INFO"):
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"{stamp} [{level}] {message}\n"
        self.text.configure(state="normal")
        self.text.insert("end", line)
        self.text.see("end")
        self.text.configure(state="disabled")

    def _lines(self):
        content = self.text.get("1.0", "end-1c")
        return content.splitlines()

    def _copy(self, content: str):
        self.clipboard_clear()
        self.clipboard_append(content.strip())
        self.update()

    def copy_log(self):
        self._copy("\n".join(self._lines()))

    def copy_last_50(self):
        lines = self._lines()
        self._copy("\n".join(lines[-50:]))

    def copy_errors(self):
        lines = self._lines()
        errors = [line for line in lines if "[ERROR]" in line or "FAILED" in line or "failed:" in line.lower()]
        self._copy("\n".join(errors) if errors else "No errors found.")

    def copy_summary(self):
        lines = self._lines()
        keywords = (
            "Application started.",
            "Python version:",
            "Connected ✓",
            "XAUUSD: AVAILABLE",
            "Historical data loaded",
            "Candidates:",
            "TRAIN/TEST split:",
            "[WALK-FORWARD] Started",
            "[WALK-FORWARD] Finished",
            "[MONTE CARLO] Started",
            "[MONTE CARLO] Finished",
            "[SENSITIVITY] Started",
            "[SENSITIVITY] Finished",
            "[REGIME] Started",
            "[REGIME] Finished",
            "Research finished.",
            "Ranked strategies:",
            "Best strategy:",
            "[EXPORT]",
        )
        summary = [line for line in lines if any(key in line for key in keywords)]
        if not summary:
            summary = ["No research summary is available yet."]
        header = [
            "============================================================",
            "XAU STRATEGY RESEARCH SUMMARY",
            "============================================================",
        ]
        self._copy("\n".join(header + summary))

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
