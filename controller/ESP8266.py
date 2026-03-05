from datetime import datetime
import time
from typing import Dict

import requests
from config.config import Config

# =================== КЛАСС ДЛЯ РАБОТЫ С ESP8266 ===================
class ESP8266Controller:
    def __init__(self, esp_ip: str = Config.ESP_IP, request_interval: int = Config.REQUEST_INTERVAL):
        self.esp_ip = esp_ip
        self.base_url = f"http://{esp_ip}"
        self.toggle_url = f"{self.base_url}/toggle"
        self.request_interval = request_interval
        self.last_request_time = 0
        self.request_count = 0
        self.last_trigger_width = 0

    def send_toggle_request(self, width_mm: float = None) -> Dict:
        """Отправляет запрос на переключение LED и возвращает результат"""
        self.request_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")

        try:
            print(f"[{timestamp}] Запрос #{self.request_count}: Отправка на {self.toggle_url}")
            if width_mm:
                print(f"  Причина: Ширина {width_mm:.1f} мм")
                self.last_trigger_width = width_mm

            start_time = time.time()
            response = requests.get(self.toggle_url, timeout=3)
            elapsed_time = (time.time() - start_time) * 1000

            if response.status_code in [200, 303]:
                result = {
                    'success': True,
                    'status': 'LED toggled successfully',
                    'status_code': response.status_code,
                    'response_time': elapsed_time,
                    'message': response.text[:50] if response.text else ''
                }
            else:
                result = {
                    'success': False,
                    'status': f'HTTP error: {response.status_code}',
                    'status_code': response.status_code,
                    'response_time': elapsed_time
                }

        except Exception as e:
            result = {
                'success': False,
                'status': 'Request failed',
                'error': str(e)
            }

        self.print_result(result)
        self.last_request_time = time.time()
        return result

    def should_send_request(self, current_width: float, min_width: float = 134) -> bool:
        """Проверяет, нужно ли отправлять запрос"""
        # Проверка интервала времени
        if time.time() - self.last_request_time < self.request_interval:
            return False

        # Проверка порога ширины
        if current_width >= min_width:
            return False

        # Проверка, что ширина существенно изменилась с последнего срабатывания
        if abs(current_width - self.last_trigger_width) < Config.MIN_WIDTH_CHANGE:
            return False

        return True

    def print_result(self, result: Dict):
        """Выводит результат запроса в консоль"""
        if result['success']:
            print(f"  ✓ {result['status']}")
            if 'response_time' in result:
                print(f"  Время ответа: {result['response_time']:.1f} мс")
            if 'message' in result and result['message']:
                print(f"  Ответ: {result['message']}")
        else:
            print(f"  ✗ {result['status']}")
            if 'error' in result:
                print(f"  Причина: {result['error']}")
        print("-" * 50)
