"""Compact final research result panel with one-click copy."""
import tkinter as tk
from tkinter import ttk


class ResultPanel(ttk.LabelFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, text="FINAL RESEARCH RESULT", **kwargs)
        self.value = "No research completed yet."
        self.vars = {}
        fields = ["Strategy", "Direction", "Score", "OOS PF", "OOS Net R", "WF", "Monte Carlo", "Sensitivity", "Regime", "Validation"]
        for i, name in enumerate(fields):
            row, col = divmod(i, 5)
            cell = ttk.Frame(self)
            cell.grid(row=row, column=col, sticky="ew", padx=5, pady=2)
            ttk.Label(cell, text=f"{name}:").pack(side="left")
            var = tk.StringVar(value="—")
            self.vars[name] = var
            ttk.Label(cell, textvariable=var).pack(side="left", padx=(3, 0))
        for col in range(5):
            self.columnconfigure(col, weight=1)
        ttk.Button(self, text="COPY FINAL RESULT", command=self.copy_result).grid(row=0, column=5, rowspan=2, padx=7, pady=3, sticky="nsew")
        self.columnconfigure(5, weight=0)

    def set_result(self, result: dict):
        candidate = result.get("candidate")
        name = getattr(candidate, "name", None) or result.get("strategy_name", "N/A")
        direction = getattr(candidate, "direction", None) or "—"
        values = {
            "Strategy": name,
            "Direction": direction,
            "Score": self._num(result.get("walk_forward_score", result.get("validation_score"))),
            "OOS PF": self._num(result.get("oos_pf_mean", result.get("profit_factor"))),
            "OOS Net R": self._num(result.get("oos_net_r_sum", result.get("net_r"))),
            "WF": f"{result.get('positive_windows', '—')}/{result.get('window_count', '—')}",
            "Monte Carlo": self._num(result.get("monte_carlo_robustness")),
            "Sensitivity": self._num(result.get("sensitivity_robustness")),
            "Regime": self._num(result.get("regime_robustness")),
            "Validation": self._num(result.get("validation_score")),
        }
        for key, value in values.items():
            self.vars[key].set(str(value))
        self.value = self._format(values)

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

    @staticmethod
    def _format(values):
        return (
            "XAU FINAL RESULT\n"
            f"Strategy={values['Strategy']} | Direction={values['Direction']} | Score={values['Score']} | "
            f"OOS PF={values['OOS PF']} | OOS Net R={values['OOS Net R']} | WF={values['WF']}\n"
            f"Monte Carlo={values['Monte Carlo']} | Sensitivity={values['Sensitivity']} | "
            f"Regime={values['Regime']} | Validation={values['Validation']}"
        )
