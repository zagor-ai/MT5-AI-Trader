"""Main GUI composition for XAU Strategy Researcher Pro."""
import platform
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from gui.controls import ControlsPanel
from gui.log_panel import LogPanel
from gui.progress import ProgressPanel
from gui.status_panel import StatusPanel
from services.mt5_connector import MT5Connector


class MainWindow(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.connector = MT5Connector("XAUUSD")
        self.stop_event = threading.Event()
        self._build()
        self.after(100, self.initial_diagnostics)

    def _build(self):
        self.status = StatusPanel(self)
        self.status.pack(fill="x", padx=8, pady=8)
        self.controls = ControlsPanel(self, callbacks={
            "connect": self.connect_mt5,
            "load_data": self.load_data,
            "start": self.start_research,
            "stop": self.stop_research,
        })
        self.controls.pack(fill="x", padx=8, pady=(0, 8))
        self.progress = ProgressPanel(self)
        self.progress.pack(fill="x", padx=8, pady=(0, 8))
        self.log = LogPanel(self)
        self.log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def write(self, message, level="INFO"):
        self.after(0, lambda: self.log.write(message, level))

    def initial_diagnostics(self):
        self.write("Application started.")
        self.write(f"Python version: {platform.python_version()}")
        try:
            import MetaTrader5  # noqa: F401
            self.status.set("Python", platform.python_version())
            self.status.set("MetaTrader5 Package", "OK ✓")
            self.write("MetaTrader5 package: OK ✓")
        except ImportError:
            self.status.set("MetaTrader5 Package", "MISSING ✗")
            self.write("MetaTrader5 package: MISSING ✗", "ERROR")
            return
        self.connect_mt5(initial=True)

    def connect_mt5(self, initial=False):
        def worker():
            self.write("Initializing terminal...", "MT5")
            d = self.connector.diagnostics()
            if not d.connected:
                self.status.set("MT5 Terminal", "Not Connected ✗")
                self.write(f"MT5: NOT CONNECTED — {d.error}", "ERROR")
                return
            self.status.set("MT5 Terminal", "Connected ✓")
            self.status.set("Account", d.account or "—")
            self.status.set("Server", d.server or "—")
            self.status.set("Symbol", "XAUUSD AVAILABLE ✓" if d.symbol_available else "XAUUSD NOT AVAILABLE ✗")
            self.write("Connected ✓", "MT5")
            self.write(f"Terminal: {d.terminal or 'MetaTrader 5'}", "MT5")
            self.write(f"Build: {d.build}", "MT5")
            self.write(f"Account: {d.account}", "MT5")
            self.write(f"Server: {d.server}", "MT5")
            if d.symbol_available:
                self.write("XAUUSD: AVAILABLE ✓", "MT5")
                self.write(f"Digits: {d.digits}", "MT5")
                self.write(f"Point: {d.point}", "MT5")
                self.write(f"Bid={d.bid} Ask={d.ask}", "MT5")
        threading.Thread(target=worker, daemon=True).start()

    def load_data(self):
        timeframe = self.controls.timeframe.get()
        try:
            bars = int(self.controls.bars.get())
        except ValueError:
            self.write("Bars must be a valid integer.", "ERROR")
            return
        self.status.set("Timeframe", timeframe)
        self.write("=======================================", "DATA")
        self.write(f"LOAD DATA started: XAUUSD {timeframe}, bars={bars}", "DATA")

        def worker():
            try:
                rates = self.connector.load_rates(timeframe, bars)
                count = len(rates)
                if count == 0:
                    raise RuntimeError("MT5 returned zero bars.")
                last_time = int(rates[-1]["time"])
                import datetime as dt
                last_dt = dt.datetime.fromtimestamp(last_time).strftime("%Y-%m-%d %H:%M:%S")
                self.status.set("Historical Data", "Loaded ✓")
                self.status.set("Number of Bars", str(count))
                self.status.set("Last Bar Time", last_dt)
                self.write(f"Historical data loaded ✓ — {count} bars", "DATA")
                self.write(f"Last bar: {last_dt}", "DATA")
            except Exception as exc:
                self.status.set("Historical Data", "FAILED ✗")
                self.write(f"LOAD FAILED ✗: {exc}", "ERROR")
                try:
                    import MetaTrader5 as mt5
                    self.write(f"Last MT5 error: {mt5.last_error()}", "ERROR")
                except Exception:
                    pass
        threading.Thread(target=worker, daemon=True).start()

    def start_research(self):
        if self.stop_event.is_set():
            self.stop_event.clear()
        self.write("Research engine start requested.", "RESEARCH")
        self.write("Research execution hook is ready; engine integration comes next.", "RESEARCH")

    def stop_research(self):
        self.stop_event.set()
        self.write("STOP requested. Current research worker will stop at its next checkpoint.", "RESEARCH")


def run_app():
    root = tk.Tk()
    root.title("XAU Strategy Researcher Pro v2.1.1")
    root.geometry("1050x760")
    root.minsize(850, 620)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    MainWindow(root).pack(fill="both", expand=True)
    root.mainloop()
