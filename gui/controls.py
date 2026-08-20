"""User controls for the research GUI."""
import tkinter as tk
from tkinter import ttk


class ControlsPanel(ttk.LabelFrame):
    def __init__(self, master, callbacks=None, **kwargs):
        super().__init__(master, text="RESEARCH CONTROLS", **kwargs)
        callbacks = callbacks or {}
        self.callbacks = callbacks

        ttk.Label(self, text="Timeframe:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.timeframe = tk.StringVar(value="M5")
        ttk.Combobox(self, textvariable=self.timeframe, values=("M1", "M5", "M15", "M30", "H1"), state="readonly", width=8).grid(row=0, column=1, padx=5)

        ttk.Label(self, text="Bars:").grid(row=0, column=2, padx=5, sticky="w")
        self.bars = tk.StringVar(value="50000")
        ttk.Entry(self, textvariable=self.bars, width=10).grid(row=0, column=3, padx=5)

        self.connect_btn = ttk.Button(self, text="CONNECT MT5", command=lambda: self._call("connect"))
        self.connect_btn.grid(row=1, column=0, padx=5, pady=8)
        ttk.Button(self, text="LOAD DATA", command=lambda: self._call("load_data")).grid(row=1, column=1, padx=5)
        ttk.Button(self, text="START RESEARCH", command=lambda: self._call("start")).grid(row=1, column=2, padx=5)
        ttk.Button(self, text="STOP", command=lambda: self._call("stop")).grid(row=1, column=3, padx=5)

    def _call(self, name):
        callback = self.callbacks.get(name)
        if callback:
            callback()
