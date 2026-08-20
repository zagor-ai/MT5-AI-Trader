"""Thread-safe log sink shared by GUI and research workers."""

from datetime import datetime
import threading


class ResearchLogger:
    def __init__(self):
        self._lock = threading.Lock()
        self._lines: list[str] = []
        self._listeners = []

    def subscribe(self, callback):
        self._listeners.append(callback)

    def log(self, message: str):
        line = f"{datetime.now():%H:%M:%S} {message}"
        with self._lock:
            self._lines.append(line)
        for callback in tuple(self._listeners):
            try:
                callback(line)
            except Exception:
                pass

    def clear(self):
        with self._lock:
            self._lines.clear()

    def text(self) -> str:
        with self._lock:
            return "\n".join(self._lines)
