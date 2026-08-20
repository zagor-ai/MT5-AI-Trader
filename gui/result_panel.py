"""Final research result panel with one-click copy."""
import tkinter as tk
from tkinter import ttk


class ResultPanel(ttk.LabelFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, text="FINAL RESEARCH RESULT", **kwargs)
        self.value = "No research completed yet."
        self.text = tk.Text(self, height=8, wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True, padx=6, pady=(6, 4))
        ttk.Button(self, text="COPY FINAL RESULT", command=self.copy_result).pack(anchor="e", padx=6, pady=(0, 6))

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
        return ("=" * 56 + "\n"
                "XAU STRATEGY RESEARCH — FINAL RESULT\n"
                "=" * 56 + "\n"
                f"Strategy       : {name}\n"
                f"Direction      : {direction}\n"
                f"Final Ranking  : #1\n"
                f"Walk-Forward   : {cls._num(wf)}\n"
                f"Monte Carlo    : {cls._num(mc)}\n"
                f"Sensitivity    : {cls._num(sens)}\n"
                f"Market Regime  : {cls._num(regime)}\n"
                f"Validation     : {cls._num(validation)}\n"
                f"OOS PF         : {cls._num(pf)}\n"
                f"OOS Net R      : {cls._num(netr)}\n"
                f"WF Windows     : {positive if positive is not None else '—'} / {windows if windows is not None else '—'}\n"
                "=" * 56)
