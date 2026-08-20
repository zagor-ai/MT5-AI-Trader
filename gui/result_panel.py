"""Compact final research result panel with one-click copy."""
import tkinter as tk
from tkinter import ttk


class ResultPanel(ttk.LabelFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, text="FINAL RESEARCH RESULT", **kwargs)
        self.value = "No research completed yet."
        body = ttk.Frame(self)
        body.pack(fill="x", padx=6, pady=3)
        self.text = tk.Label(body, text="No research completed yet.", anchor="w", justify="left")
        self.text.pack(side="left", fill="x", expand=True)
        ttk.Button(body, text="COPY FINAL RESULT", command=self.copy_result).pack(side="right", padx=(8, 0))

    def set_result(self, result: dict):
        self.value = self._format(result)
        self.text.configure(text=self.value)

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
        wf_windows = item.get("window_count")
        wf_positive = item.get("positive_windows")
        return (
            f"{name}  |  {direction}  |  WF {cls._num(wf)}  |  MC {cls._num(mc)}  |  "
            f"Sensitivity {cls._num(sens)}  |  Regime {cls._num(regime)}  |  "
            f"Validation {cls._num(validation)}  |  OOS PF {cls._num(pf)}  |  OOS Net R {cls._num(netr)}  |  "
            f"WF {wf_positive if wf_positive is not None else '—'}/{wf_windows if wf_windows is not None else '—'}"
        )
