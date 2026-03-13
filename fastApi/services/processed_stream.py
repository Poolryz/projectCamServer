import threading
from typing import Optional, Any, Dict, Tuple

import numpy as np


class ProcessedStream:
    """
    Thread-safe storage for the latest processed frame produced elsewhere (e.g. server.py).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._meta: Dict[str, Any] = {}

    def update(self, frame: np.ndarray, meta: Optional[Dict[str, Any]] = None) -> None:
        if frame is None:
            return
        with self._lock:
            self._frame = frame.copy()
            if meta is not None:
                incoming = dict(meta)
                # Если измерение невалидно, не затираем последнее валидное значение,
                # а сохраняем причину в last_error.
                if incoming.get("ok") is False and self._meta.get("ok") is True:
                    self._meta["last_error"] = incoming
                else:
                    self._meta = incoming

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def get_meta(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._meta)

    def get_latest(self) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
            meta = dict(self._meta)
        return frame, meta

