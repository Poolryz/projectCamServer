from __future__ import annotations

import asyncio
import base64
import time
from typing import Optional, Tuple

import cv2
from fastapi import WebSocket, WebSocketDisconnect


# ──────────────────────────────────────────────────────────────────────────────
#  Монитор ширины металла
# ──────────────────────────────────────────────────────────────────────────────
class WidthMonitor:
    """
    Конечный автомат для контроля ширины металла.

    Состояния
    ---------
    idle       — ждём стабильных показаний, чтобы спросить у клиента подтверждение.
    confirming — запрос отправлен, ждём ответа клиента.
    monitoring — границы установлены, контролируем отклонения.

    Протокол (сервер → клиент)
    --------------------------
    width_confirm_request  — «Сейчас ширина <N> мм?»
    width_alert            — металл вышел за пределы
    width_back_in_bounds   — металл вернулся в норму
    width_monitor_state    — текущее состояние монитора (отправляется при изменении)

    Протокол (клиент → сервер)
    --------------------------
    confirm_width   { confirmed: bool, expected_mm?: float }
    set_width       { expected_mm: float }   — ручная установка без подтверждения
    reset_monitor   {}                        — сбросить в idle
    """

    TOLERANCE_MM: float = 2.0
    CONFIRM_STABLE_FRAMES: int = 20   # сколько подряд стабильных кадров перед запросом
    CONFIRM_TIMEOUT_S: float = 15.0   # таймаут ожидания ответа клиента
    ALERT_DEBOUNCE_FRAMES: int = 5    # подряд кадров за границами перед тревогой
    ALERT_COOLDOWN_S: float = 3.0     # минимум секунд между повторными тревогами

    def __init__(self) -> None:
        self.state: str = "idle"
        self.expected_mm: Optional[float] = None
        self.bounds: Optional[Tuple[float, float]] = None

        self._pending_mm: Optional[float] = None   # округлённое значение на подтверждении
        self._confirm_sent_at: float = 0.0

        self._last_alert_at: float = 0.0
        self._last_alert_direction: Optional[str] = None
        self._oob_streak: int = 0
        self._was_in_bounds: Optional[bool] = None

        self._stable_candidate: Optional[float] = None
        self._stable_count: int = 0

    # ── публичный интерфейс ────────────────────────────────────────────────────

    def process(self, width_mm: float, now: float) -> Optional[dict]:
        """Обработка нового измерения. Возвращает сообщение для клиента или None."""
        if self.state == "idle":
            return self._track_stability(width_mm, now)
        if self.state == "confirming":
            return self._check_confirm_timeout(now)
        if self.state == "monitoring":
            return self._check_bounds(width_mm, now)
        return None

    def on_confirm(self, confirmed: bool, expected_mm: Optional[float] = None) -> Optional[dict]:
        """Клиент ответил на запрос подтверждения."""
        if self.state != "confirming":
            return None
        if confirmed:
            target = float(expected_mm) if expected_mm is not None else self._pending_mm
            self._activate_monitoring(target)
            return self._state_msg()
        # Отклонено — сброс
        self._reset_idle()
        return self._state_msg()

    def on_set_width(self, expected_mm: float) -> dict:
        """Клиент вручную задал ожидаемую ширину."""
        self._activate_monitoring(float(expected_mm))
        return self._state_msg()

    def on_reset(self) -> dict:
        """Клиент запросил сброс в idle."""
        self._reset_idle()
        return self._state_msg()

    def state_dict(self) -> dict:
        return {
            "state": self.state,
            "expected_mm": self.expected_mm,
            "bounds": list(self.bounds) if self.bounds else None,
            "pending_mm": self._pending_mm,
        }

    # ── внутренние методы ──────────────────────────────────────────────────────

    @staticmethod
    def _round_to_10(mm: float) -> float:
        return round(mm / 10) * 10

    def _state_msg(self) -> dict:
        return {"type": "width_monitor_state", **self.state_dict()}

    def _reset_idle(self) -> None:
        self.state = "idle"
        self._stable_count = 0
        self._stable_candidate = None
        self._pending_mm = None

    def _activate_monitoring(self, expected_mm: float) -> None:
        self.expected_mm = expected_mm
        self.bounds = (expected_mm - self.TOLERANCE_MM,
                       expected_mm + self.TOLERANCE_MM)
        self.state = "monitoring"
        self._oob_streak = 0
        self._was_in_bounds = None
        self._last_alert_direction = None
        self._stable_count = 0
        self._pending_mm = None

    def _track_stability(self, width_mm: float, now: float) -> Optional[dict]:
        rounded = self._round_to_10(width_mm)
        if self._stable_candidate == rounded:
            self._stable_count += 1
        else:
            self._stable_candidate = rounded
            self._stable_count = 1

        if self._stable_count >= self.CONFIRM_STABLE_FRAMES:
            self.state = "confirming"
            self._pending_mm = rounded
            self._confirm_sent_at = now
            self._stable_count = 0
            return {
                "type": "width_confirm_request",
                "measured_mm": round(width_mm, 1),
                "suggested_mm": rounded,
            }
        return None

    def _check_confirm_timeout(self, now: float) -> Optional[dict]:
        if now - self._confirm_sent_at > self.CONFIRM_TIMEOUT_S:
            self._reset_idle()
        return None

    def _check_bounds(self, width_mm: float, now: float) -> Optional[dict]:
        lo, hi = self.bounds  # type: ignore[misc]
        in_bounds = lo <= width_mm <= hi

        if in_bounds:
            self._oob_streak = 0
            if self._was_in_bounds is False:
                self._was_in_bounds = True
                self._last_alert_direction = None
                return {
                    "type": "width_back_in_bounds",
                    "width_mm": round(width_mm, 1),
                    "expected_mm": self.expected_mm,
                    "bounds": [lo, hi],
                }
            self._was_in_bounds = True
            return None

        # Металл за пределами
        self._oob_streak += 1
        direction = "wider" if width_mm > hi else "narrower"
        enough_streak = self._oob_streak >= self.ALERT_DEBOUNCE_FRAMES
        enough_cooldown = now - self._last_alert_at >= self.ALERT_COOLDOWN_S

        if enough_streak and enough_cooldown:
            self._last_alert_at = now
            self._last_alert_direction = direction
            self._was_in_bounds = False
            return {
                "type": "width_alert",
                "width_mm": round(width_mm, 1),
                "expected_mm": self.expected_mm,
                "bounds": [lo, hi],
                "direction": direction,
            }
        return None


# ──────────────────────────────────────────────────────────────────────────────
#  WebSocket-обработчик
# ──────────────────────────────────────────────────────────────────────────────
async def websocket_processed(websocket: WebSocket) -> None:
    """Двунаправленный WebSocket: сервер шлёт кадры + события ширины,
    клиент шлёт подтверждения и команды управления."""
    await websocket.accept()
    print("WebSocket клиент подключён")

    stream = websocket.app.state.processed_stream
    monitor = WidthMonitor()

    # Отправляем начальное состояние монитора
    await websocket.send_json({"type": "width_monitor_state", **monitor.state_dict()})

    async def send_loop() -> None:
        while True:
            frame, meta = stream.get_latest()
            now = time.time()

            if frame is not None:
                h, w = frame.shape[:2]
                if w > 960:
                    scale = 960 / w
                    frame = cv2.resize(frame, (960, int(h * scale)))
                _, buffer = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                )
                frame_b64 = base64.b64encode(buffer).decode("utf-8")
                await websocket.send_json(
                    {"type": "frame", "data": frame_b64, "meta": meta, "timestamp": now}
                )
            else:
                await websocket.send_json({"type": "no_frame", "timestamp": now})

            # Проверяем ширину через монитор
            if isinstance(meta, dict) and meta.get("ok") is True:
                width_mm = meta.get("width_mm")
                if width_mm is not None:
                    msg = monitor.process(float(width_mm), now)
                    if msg:
                        await websocket.send_json(msg)

            await asyncio.sleep(1 / 25)

    async def receive_loop() -> None:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            reply: Optional[dict] = None

            if msg_type == "confirm_width":
                reply = monitor.on_confirm(
                    confirmed=bool(data.get("confirmed", False)),
                    expected_mm=data.get("expected_mm"),
                )
            elif msg_type == "set_width":
                expected_mm = data.get("expected_mm")
                if expected_mm is not None:
                    reply = monitor.on_set_width(float(expected_mm))
            elif msg_type == "reset_monitor":
                reply = monitor.on_reset()

            if reply:
                await websocket.send_json(reply)

    send_task = asyncio.create_task(send_loop())
    receive_task = asyncio.create_task(receive_loop())

    try:
        done, pending = await asyncio.wait(
            {send_task, receive_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Проверяем, не было ли исключений в завершившейся задаче
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, (WebSocketDisconnect, RuntimeError)):
                print(f"WebSocket задача упала: {exc}")
    finally:
        send_task.cancel()
        receive_task.cancel()
        await asyncio.gather(send_task, receive_task, return_exceptions=True)
        print("WebSocket клиент отключён")
