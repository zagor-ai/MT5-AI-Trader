"""GUI status panel for Python, MT5, account, symbol and data state."""
import tkinter as tk
from tkinter import ttk


class StatusPanel(ttk.LabelFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, text="MT5 STATUS", **kwargs)
        self.vars = {}
        fields = [
            "Python", "MetaTrader5 Package", "MT5 Terminal", "Account",
            "Server", "Symbol", "Timeframe", "Historical Data",
            "Number of Bars", "Last Bar Time"
        ]
        for row, name in enumerate(fields):
            ttk.Label(self, text=f"{name}:").grid(row=row, column=0, sticky="w", padx=8, pady=2)
            var = tk.StringVar(value="—")
            self.vars[name] = var
            ttk.Label(self, textvariable=var).grid(row=row, column=1, sticky="w", padx=8, pady=2)

    def set(self, name: str, value: str):
        if name in self.vars:
            self.vars[name].set(str(value))
