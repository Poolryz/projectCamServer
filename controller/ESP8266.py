from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import time
from typing import Dict, Optional

import requests
from config.config import Config

# Один фоновый поток для всех HTTP-запросов к ESP — не блокирует event loop
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="esp_http")


# =================== КЛАСС ДЛЯ РАБОТЫ С ESP8266 ===================
class ESP8266Controller:
    """
    Управляет лампой на ESP8266 через HTTP.

    Ключевые свойства
    -----------------
    - Использует явные эндпоинты /led/on и /led/off вместо /toggle,
      поэтому лампа никогда не «дёргается».
    - Запрос уходит в пул потоков (run_in_executor) — event loop не блокируется
      и видео не подвисает.
    - Повторный запрос отправляется только при смене состояния (OFF→ON или ON→OFF).
    - Пока летит один запрос, дубликаты игнорируются.
    """

    def __init__(self, esp_ip: str = Config.ESP_IP) -> None:
        self.base_url = f"http://{esp_ip}"
        self._url_on  = f"{self.base_url}/led/on"
        self._url_off = f"{self.base_url}/led/off"

        self._led_on: bool = False      # последнее подтверждённое состояние
        self._pending: bool = False     # идёт ли прямо сейчас HTTP-запрос
        self._request_count: int = 0

    # ── публичный async-интерфейс ─────────────────────────────────────────────

    async def alert_on(self) -> None:
        """Включить лампу — вызывать при выходе ширины за допуск."""
        await self._set_led(True)

    async def alert_off(self) -> None:
        """Выключить лампу — вызывать когда ширина вернулась в норму."""
        await self._set_led(False)

    # ── внутренняя логика ─────────────────────────────────────────────────────

    async def _set_led(self, on: bool) -> None:
        if self._led_on == on:
            return          # уже в нужном состоянии — ничего не делаем
        if self._pending:
            return          # запрос уже летит — не дублируем

        self._pending = True
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(_executor, self._send_request, on)
            if result["success"]:
                self._led_on = on
        finally:
            self._pending = False

    def _send_request(self, on: bool) -> Dict:
        """Синхронный HTTP-запрос; выполняется в пуле потоков."""
        self._request_count += 1
        url = self._url_on if on else self._url_off
        action = "ON" if on else "OFF"
        timestamp = datetime.now().strftime("%H:%M:%S")

        print(f"[{timestamp}] ESP #{self._request_count}: LED {action} → {url}")
        try:
            t0 = time.time()
            response = requests.get(url, timeout=3)
            elapsed_ms = (time.time() - t0) * 1000

            if response.status_code in [200, 303]:
                print(f"  ✓ LED {action}  ({elapsed_ms:.0f} мс)")
                return {"success": True, "elapsed_ms": elapsed_ms}
            else:
                print(f"  ✗ HTTP {response.status_code}")
                return {"success": False, "status_code": response.status_code}

        except Exception as exc:
            print(f"  ✗ Ошибка: {exc}")
            return {"success": False, "error": str(exc)}
