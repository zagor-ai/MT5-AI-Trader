"""Compact final research result panel with one-click copy."""
import tkinter as tk
from tkinter import ttk


class ResultPanel(ttk.LabelFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, text="FINAL RESEARCH RESULT", **kwargs)
        self.value = "No research completed yet."
        body = ttk.Frame(self)
        body.pack(fill="x", padx=6, pady=3)
        self.text = tk.Text(body, height=3, wrap="none", state="disabled")
        self.text.pack(side="left", fill="x", expand=True)
        ttk.Button(body, text="COPY FINAL RESULT", command=self.copy_result).pack(side="right", padx=(8, 0), anchor="n")

    def set_result(self, result: dict):
        self.value = self._format(result)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.value)
        self.text.configure(state="disabled")

    def copy_result(self):
        self.clipboard_clear()
        self.clipboard_append(self.value)
        self.update()

    @staticmethod
    def _num(value, digits=2):
        try:
            return f"{float(value):.{digits}f}"
        except (TypeError, ValueError):
            return "—"

    @classmethod
    def _format(cls, item):
        candidate = item.get("candidate")
        name = getattr(candidate, "name", None) or item.get("strategy_name", "N/A")
        direction = getattr(candidate, "direction", None) or "—"
        wf = item.get("walk_forward_score")
        mc = item.get("monte_carlo_robustness")
        sens = item.get("sensitivity_robustness")
        regime = item.get("regime_robustness")
        validation = item.get("validation_score")
        pf = item.get("oos_pf_mean", item.get("profit_factor"))
        netr = item.get("oos_net_r_sum", item.get("net_r"))
        windows = item.get("window_count")
        positive = item.get("positive_windows")
        return (
            f"Strategy: {name} | Direction: {direction} | WF: {cls._num(wf)} | MC: {cls._num(mc)} | "
            f"Sensitivity: {cls._num(sens)} | Regime: {cls._num(regime)}\n"
            f"Validation: {cls._num(validation)} | OOS PF: {cls._num(pf)} | OOS Net R: {cls._num(netr)} | "
            f"WF Windows: {positive if positive is not None else '—'}/{windows if windows is not None else '—'}\n"
            "Use COPY FINAL RESULT to send the complete result."
        )
