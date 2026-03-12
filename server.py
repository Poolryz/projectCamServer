import threading
import cv2
import numpy as np
import os
import time
import sys
from datetime import datetime
from typing import Optional, Tuple, Dict
from collections import deque
from config.config import Config
from videoProcessor.videoProcessor import ImprovedVideoProcessor
# Импортируем FastAPI модули
from fastApi.main import run_fastapi
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
    
    # Инициализация улучшенного видеопроцессора
    video_processor = ImprovedVideoProcessor()

    if not video_processor.initialize():
        print("Не удалось инициализировать видеопоток. Завершение работы.")
        return

    frame_count = 0
    min_width_threshold = 134.0  # Начальный порог

    try:
        while True:
            # Чтение кадра
            ret, frame = video_processor.cap.read()
            if not ret:
                print("Конец видеопотока или ошибка чтения")
                break

            frame_count += 1

            # Обработка кадра с улучшенным алгоритмом
            processed_frame, width_mm = video_processor.process_frame(frame)

            # Отображение порога
            cv2.putText(processed_frame, f"Threshold: {min_width_threshold:.1f}mm",
                       (50, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            # Отображение номера кадра
            cv2.putText(processed_frame, f"Frame: {frame_count}",
                       (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Отображение кадра
            cv2.imshow("Improved Metal Width Monitor", processed_frame)

            # Обработка клавиш
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):  # Выход
                break
            elif key == ord('s'):  # Сохранение кадра
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Создаем директорию если её нет
                os.makedirs(Config.SAVE_DIR, exist_ok=True)
                filename = os.path.join(Config.SAVE_DIR, f"frame_{timestamp}_width_{width_mm:.1f}.jpg")
                cv2.imwrite(filename, processed_frame)
                print(f"Кадр сохранен: {filename}")
            elif key == ord('r'):  # Сброс статистики
                if hasattr(video_processor, 'measurement_stats'):
                    video_processor.measurement_stats = {
                        'total_measurements': 0,
                        'valid_measurements': 0,
                        'edges_detected': 0
                    }
                print("Статистика сброшена")
            elif key == ord('+'):  # Увеличение порога
                min_width_threshold += 0.5
                print(f"Порог срабатывания: {min_width_threshold:.1f} мм")
            elif key == ord('-'):  # Уменьшение порога
                min_width_threshold = max(100, min_width_threshold - 0.5)
                print(f"Порог срабатывания: {min_width_threshold:.1f} мм")

            # Небольшая задержка для уменьшения нагрузки на процессор
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем (Ctrl+C)")
    except Exception as e:
        print(f"\nПроизошла ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Освобождение ресурсов
        video_processor.release()
        cv2.destroyAllWindows()
        print("Ресурсы освобождены. Программа завершена.")

if __name__ == "__main__":
    main()
