"""Main GUI composition for XAU Strategy Researcher Pro."""
import platform
import threading
import tkinter as tk
from tkinter import ttk
from gui.controls import ControlsPanel
from gui.log_panel import LogPanel
from gui.progress import ProgressPanel
from gui.status_panel import StatusPanel
from gui.result_panel import ResultPanel
from services.mt5_connector import MT5Connector
from core.research_engine import ResearchEngine, ResearchConfig

class MainWindow(ttk.Frame):
    def __init__(self, master):
        super().__init__(master); self.master = master; self.connector = MT5Connector("XAUUSD"); self.engine = ResearchEngine(ResearchConfig(max_candidates=300)); self.stop_event = threading.Event(); self.loaded_data = None; self.research_thread = None; self._build(); self.after(100, self.initial_diagnostics)
    def _build(self):
        self.status = StatusPanel(self); self.status.pack(fill="x", padx=8, pady=8); self.controls = ControlsPanel(self, callbacks={"connect": self.connect_mt5, "load_data": self.load_data, "start": self.start_research, "stop": self.stop_research}); self.controls.pack(fill="x", padx=8, pady=(0, 8)); self.progress = ProgressPanel(self); self.progress.pack(fill="x", padx=8, pady=(0, 8)); self.result_panel = ResultPanel(self); self.result_panel.pack(fill="x", padx=8, pady=(0, 8)); self.log = LogPanel(self); self.log.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    def write(self, message, level="INFO"): self.after(0, lambda: self.log.write(message, level))
    def initial_diagnostics(self):
        self.write("Application started."); self.write(f"Python version: {platform.python_version()}")
        try:
            import MetaTrader5; self.status.set("Python", platform.python_version()); self.status.set("MetaTrader5 Package", "OK ✓"); self.write("MetaTrader5 package: OK ✓")
        except ImportError: self.status.set("MetaTrader5 Package", "MISSING ✗"); self.write("MetaTrader5 package: MISSING ✗", "ERROR"); return
        self.connect_mt5(initial=True)
    def connect_mt5(self, initial=False):
        def worker():
            self.write("Initializing terminal...", "MT5"); d = self.connector.diagnostics()
            if not d.connected: self.status.set("MT5 Terminal", "Not Connected ✗"); self.write(f"MT5: NOT CONNECTED — {d.error}", "ERROR"); return
            self.status.set("MT5 Terminal", "Connected ✓"); self.status.set("Account", d.account or "—"); self.status.set("Server", d.server or "—"); self.status.set("Symbol", "XAUUSD AVAILABLE ✓" if d.symbol_available else "XAUUSD NOT AVAILABLE ✗"); self.write("Connected ✓", "MT5"); self.write(f"Terminal: {d.terminal or 'MetaTrader 5'}", "MT5"); self.write(f"Build: {d.build}", "MT5"); self.write(f"Account: {d.account}", "MT5"); self.write(f"Server: {d.server}", "MT5")
            if d.symbol_available: self.write("XAUUSD: AVAILABLE ✓", "MT5"); self.write(f"Digits: {d.digits}", "MT5"); self.write(f"Point: {d.point}", "MT5"); self.write(f"Bid={d.bid} Ask={d.ask}", "MT5")
        threading.Thread(target=worker, daemon=True).start()
    def load_data(self):
        timeframe = self.controls.timeframe.get()
        try: bars = int(self.controls.bars.get())
        except ValueError: self.write("Bars must be a valid integer.", "ERROR"); return
        self.status.set("Timeframe", timeframe); self.status.set("Historical Data", "Loading..."); self.progress.set_phase("DATA"); self.progress.update_progress(0, 1, "Loading historical data..."); self.write("=======================================", "DATA"); self.write(f"LOAD DATA started: XAUUSD {timeframe}, bars={bars}", "DATA")
        def worker():
            try:
                import pandas as pd; rates = self.connector.load_rates(timeframe, bars)
                if len(rates) == 0: raise RuntimeError("MT5 returned zero bars.")
                frame = pd.DataFrame(rates); frame["time"] = pd.to_datetime(frame["time"], unit="s"); frame = frame.set_index("time").sort_index(); last_dt = frame.index[-1].strftime("%Y-%m-%d %H:%M:%S"); self.loaded_data = frame; self.status.set("Historical Data", "Loaded ✓"); self.status.set("Number of Bars", str(len(frame))); self.status.set("Last Bar Time", last_dt); self.after(0, lambda: self.progress.update_progress(1, 1, f"Bars loaded: {len(frame)}")); self.write(f"Historical data loaded ✓ — {len(frame)} bars", "DATA"); self.write(f"Last bar: {last_dt}", "DATA")
            except Exception as exc:
                self.loaded_data = None; self.status.set("Historical Data", "FAILED ✗"); self.write(f"LOAD FAILED ✗: {exc}", "ERROR")
                try:
                    import MetaTrader5 as mt5; self.write(f"Last MT5 error: {mt5.last_error()}", "ERROR")
                except Exception: pass
        threading.Thread(target=worker, daemon=True).start()
    def start_research(self):
        if self.loaded_data is None: self.write("Research blocked: load historical data first.", "ERROR"); return
        if self.research_thread and self.research_thread.is_alive(): self.write("Research is already running.", "RESEARCH"); return
        self.stop_event.clear(); total = self.engine.config.max_candidates; self.progress.set_phase("RESEARCH"); self.progress.update_progress(0, total); self.write("=======================================", "RESEARCH"); self.write("Started", "RESEARCH"); self.write(f"Candidates: {total}", "RESEARCH")
        def progress(current, count): self.after(0, lambda: self.progress.update_progress(current, count, f"Candidates: {current} / {count}"))
        def wf_progress(strategy, strategy_total, window, window_total):
            completed = ((strategy - 1) * window_total + window); total_steps = max(strategy_total * window_total, 1); self.after(0, lambda: (self.progress.set_phase("WALK-FORWARD"), self.progress.update_progress(completed, total_steps, f"Strategy: {strategy} / {strategy_total} | Window: {window} / {window_total}")))
        def log(message):
            msg = str(message)
            if msg.startswith("[WALK-FORWARD]"): self.after(0, lambda: self.progress.set_phase("WALK-FORWARD"))
            elif msg.startswith("[RESULT]"): self.after(0, lambda: self.progress.set_phase("RANKING"))
            elif msg.startswith("Candidate"): self.after(0, lambda: self.progress.set_phase("TRAIN / TEST"))
            self.write(msg, "TEST" if msg.startswith("Candidate") else "RESEARCH")
        def worker():
            try:
                ranked = self.engine.run_research(self.loaded_data, stop_event=self.stop_event, progress_callback=progress, log_callback=log, walk_forward_progress_callback=wf_progress)
                if self.stop_event.is_set(): self.write("Research stopped by user.", "RESEARCH"); self.after(0, lambda: self.progress.set_phase("STOPPED"))
                else:
                    self.write("Research finished.", "RESEARCH"); self.write(f"Ranked strategies: {len(ranked)}", "RESULT")
                    if self.engine.last_exports:
                        for kind, path in self.engine.last_exports.items(): self.write(f"[EXPORT] {kind.upper()}: {path}", "RESULT")
                    self.after(0, lambda: self.progress.set_phase("FINISHED"))
                    if ranked:
                        best = ranked[0]; self.after(0, lambda item=best: self.result_panel.set_result(item)); name = getattr(best.get("candidate"), "name", None) or best.get("strategy_name", "N/A"); score = best.get("walk_forward_score", best.get("validation_score", 0)); pf = best.get("oos_pf_mean", best.get("profit_factor", 0)); netr = best.get("oos_net_r_sum", best.get("net_r", 0)); self.write(f"Best strategy: {name} | Score={score:.2f} | AvgPF={pf:.2f} | OOS NetR={netr:.2f}", "RESULT")
                    self.after(0, lambda: self.progress.update_progress(100, 100, f"Final strategies: {len(ranked)}"))
            except Exception as exc: self.write(f"Research failed: {exc}", "ERROR"); self.after(0, lambda: self.progress.set_phase("ERROR"))
            finally: self.research_thread = None
        self.research_thread = threading.Thread(target=worker, daemon=True); self.research_thread.start()
    def stop_research(self):
        if not self.research_thread or not self.research_thread.is_alive(): self.write("No research is currently running.", "RESEARCH"); return
        self.stop_event.set(); self.write("STOP requested. Worker will stop at the next checkpoint.", "RESEARCH")

def run_app():
    root = tk.Tk(); root.title("XAU Strategy Researcher Pro v2.1.1"); root.geometry("1050x760"); root.minsize(850, 620)
    try: ttk.Style(root).theme_use("clam")
    except tk.TclError: pass
    MainWindow(root).pack(fill="both", expand=True); root.mainloop()
