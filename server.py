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
from fastApi.services.processed_stream import ProcessedStream
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
    processed_stream: Optional[ProcessedStream] = None

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
            processed_frame, width_mm, meta = video_processor.process_frame(frame)

            # Пробрасываем кадр на FastAPI (для фронтенда)
            if processed_stream is None:
                # FastAPI запускается в этом же процессе, поэтому можем взять ссылку из app.state
                try:
                    from fastApi.main import app as fastapi_app  # локальный импорт чтобы избежать проблем импорта при старте
                    processed_stream = getattr(fastapi_app.state, "processed_stream", None)
                except Exception:
                    processed_stream = None

            if processed_stream is not None:
                # meta отправим в WebSocket вместе с кадром
                processed_stream.update(processed_frame, meta=meta)

            # Отображение порога
            cv2.putText(processed_frame, f"Threshold: {min_width_threshold:.1f}mm",
                       (50, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            # Отображение номера кадра
            cv2.putText(processed_frame, f"Frame: {frame_count}",
                       (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

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
        print("Ресурсы освобождены. Программа завершена.")

if __name__ == "__main__":
    main()
