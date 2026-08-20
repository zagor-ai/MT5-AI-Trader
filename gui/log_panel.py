"""Thread-safe Tkinter log panel with copy and clear actions."""
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
        ttk.Button(buttons, text="COPY LOG", command=self.copy_log).pack(side="left")
        ttk.Button(buttons, text="CLEAR LOG", command=self.clear).pack(side="left", padx=5)

    def write(self, message: str, level: str = "INFO"):
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"{stamp} [{level}] {message}\n"
        self.text.configure(state="normal")
        self.text.insert("end", line)
        self.text.see("end")
        self.text.configure(state="disabled")

    def copy_log(self):
        content = self.text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
