import threading
import cv2
import numpy as np
import os
import requests
import time
import sys
from datetime import datetime
from typing import Optional, Tuple, Dict
from collections import deque
from config.config import Config
from controller.ESP8266 import ESP8266Controller
from videoProcessor.videoProcessor import ImprovedVideoProcessor
# Импортируем FastAPI модули
from fastApi.fastApi import (
    run_fastapi
)

# =================== ОСНОВНАЯ ПРОГРАММА ===================
def main():
    print("=" * 60)
    print("УЛУЧШЕННАЯ система мониторинга ширины металла")
    print("С точным определением границ и сглаживанием измерений")
    print("=" * 60)
  # Запуск FastAPI в отдельном потоке
    print("Запуск FastAPI сервера на http://localhost:8000")
    api_thread = threading.Thread(target=run_fastapi, args=("0.0.0.0", 8000), daemon=True)
    api_thread.start()
    
    # Небольшая задержка для инициализации FastAPI
    time.sleep(2)
    print("FastAPI сервер запущен")
    
    # Инициализация директории для сохранения
    #os.makedirs(Config.SAVE_DIR, exist_ok=True)

    # Инициализация контроллера ESP8266
    #esp_controller = ESP8266Controller()

    # Инициализация улучшенного видеопроцессора
    #video_processor = ImprovedVideoProcessor()

    # if not video_processor.initialize():
    #     print("Не удалось инициализировать видеопоток. Завершение работы.")
    #     return

    # print("\nСистема запущена. Нажмите:")
    # print("  'q' - выход из программы")
    # print("  's' - сохранение текущего кадра")
    # print("  'p' - пауза/продолжение отправки запросов")
    # print("  'r' - сброс статистики")
    # print("  '+'/'-' - изменение порога срабатывания")
    # print("-" * 60)

    # pause_requests = False
    # frame_count = 0
    # min_width_threshold = 134.0  # Начальный порог

    try:
         while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nОстановка FastAPI сервера...")
        print("Сервер остановлен")
    #         # Чтение кадра
    #         ret, frame = video_processor.cap.read()
    #         if not ret:
    #             print("Конец видеопотока или ошибка чтения")
    #             break

    #         frame_count += 1

    #         # Обработка кадра с улучшенным алгоритмом
    #         processed_frame, width_mm = video_processor.process_frame(frame)

    #         # Отправка запросов к ESP8266 с улучшенной логикой
    #         if not pause_requests and width_mm is not None:
    #             if esp_controller.should_send_request(width_mm, min_width_threshold):
    #                 esp_controller.send_toggle_request(width_mm)

    #         # Отображение статуса
    #         status_text = f"req: {'PAUSE' if pause_requests else 'ACTIVE'}"
    #         cv2.putText(processed_frame, status_text, (50, 140),
    #                    cv2.FONT_HERSHEY_SIMPLEX, 0.7,
    #                    (0, 255, 255) if not pause_requests else (0, 0, 255), 2)

    #         # Отображение порога
    #         cv2.putText(processed_frame, f"Threshold: {min_width_threshold:.1f}mm",
    #                    (50, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

    #         # Отображение счетчика запросов
    #         cv2.putText(processed_frame, f"Requests: {esp_controller.request_count}",
    #                    (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    #         # Отображение кадра
    #         cv2.imshow("Improved Metal Width Monitor", processed_frame)

    #         # Обработка клавиш
    #         key = cv2.waitKey(1) & 0xFF

    #         if key == ord('q'):  # Выход
    #             break
    #         elif key == ord('s'):  # Сохранение кадра
    #             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #             filename = os.path.join(Config.SAVE_DIR, f"frame_{timestamp}_width_{width_mm:.1f}.jpg")
    #             cv2.imwrite(filename, processed_frame)
    #             print(f"Кадр сохранен: {filename}")
    #         elif key == ord('p'):  # Пауза/продолжение запросов
    #             pause_requests = not pause_requests
    #             status = "ПАУЗА" if pause_requests else "АКТИВНЫ"
    #             print(f"Отправка запросов: {status}")
    #         elif key == ord('r'):  # Сброс статистики
    #             video_processor.measurement_stats = {
    #                 'total_measurements': 0,
    #                 'valid_measurements': 0,
    #                 'edges_detected': 0
    #             }
    #             print("Статистика сброшена")
    #         elif key == ord('+'):  # Увеличение порога
    #             min_width_threshold += 0.5
    #             print(f"Порог срабатывания: {min_width_threshold:.1f} мм")
    #         elif key == ord('-'):  # Уменьшение порога
    #             min_width_threshold = max(100, min_width_threshold - 0.5)
    #             print(f"Порог срабатывания: {min_width_threshold:.1f} мм")

    #         # Небольшая задержка
    #         time.sleep(0.01)
    
    # except KeyboardInterrupt:
    #     print("\nПрограмма остановлена пользователем (Ctrl+C)")
    # except Exception as e:
    #     print(f"\nПроизошла ошибка: {e}")
    #     import traceback
    #     traceback.print_exc()
    # finally:
    #     # Освобождение ресурсов
    #     video_processor.release()
    #     cv2.destroyAllWindows()

    #     # Вывод статистики
    #     print("\n" + "=" * 60)
    #     print("ИТОГОВАЯ СТАТИСТИКА РАБОТЫ:")
    #     print(f"  Обработано кадров: {frame_count}")
    #     print(f"  Отправлено запросов: {esp_controller.request_count}")
    #     print(f"  Последняя ширина срабатывания: {esp_controller.last_trigger_width:.1f} мм")
    #     print("=" * 60)
    #     print("Программа завершена.")

if __name__ == "__main__":
    main()
