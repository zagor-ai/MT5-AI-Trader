"""Compact GUI status panel for Python, MT5, account, symbol and data state."""
import tkinter as tk
from tkinter import ttk


class StatusPanel(ttk.LabelFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, text="MT5 STATUS", **kwargs)
        self.vars = {}
        fields = [
            "Python", "MetaTrader5 Package", "MT5 Terminal", "Account", "Server",
            "Symbol", "Timeframe", "Historical Data", "Number of Bars", "Last Bar Time",
        ]
        for index, name in enumerate(fields):
            row, col = divmod(index, 5)
            cell = ttk.Frame(self)
            cell.grid(row=row, column=col, sticky="ew", padx=5, pady=3)
            ttk.Label(cell, text=f"{name}:").pack(side="left")
            var = tk.StringVar(value="—")
            self.vars[name] = var
            ttk.Label(cell, textvariable=var).pack(side="left", padx=(4, 0))
        for col in range(5):
            self.columnconfigure(col, weight=1)

    def set(self, name: str, value: str):
        if name in self.vars:
            self.vars[name].set(str(value))
