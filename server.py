import threading
import time
from typing import Optional

from config.config import Config
from videoProcessor.videoProcessor import ImprovedVideoProcessor
from fastApi.main import run_fastapi
from fastApi.services.processed_stream import ProcessedStream


def main():
    print("=" * 60)
    print("Система мониторинга ширины металла")
    print("=" * 60)

    # Запуск FastAPI в фоновом потоке
    api_thread = threading.Thread(
        target=run_fastapi, args=("0.0.0.0", 8000), daemon=True
    )
    api_thread.start()

    # Ждём инициализации FastAPI и получаем ссылку на processed_stream
    time.sleep(2)
    print("FastAPI сервер запущен")

    processed_stream: Optional[ProcessedStream] = None
    try:
        from fastApi.main import app as fastapi_app
        processed_stream = getattr(fastapi_app.state, "processed_stream", None)
    except Exception:
        pass

    video_processor = ImprovedVideoProcessor()

    try:
        while True:
            # (Пере)инициализация потока
            if not video_processor.initialize():
                print("Не удалось открыть RTSP поток, повтор через 5 сек...")
                time.sleep(5)
                continue

            # Основной цикл чтения кадров
            while True:
                ret, frame = video_processor.cap.read()
                if not ret:
                    print("Потеря RTSP сигнала, переподключение...")
                    video_processor.release()
                    time.sleep(2)
                    break  # выходим во внешний цикл для переподключения

                processed_frame, width_mm, meta = video_processor.process_frame(frame)

                if processed_stream is not None:
                    processed_stream.update(processed_frame, meta=meta)

                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nПрограмма остановлена пользователем (Ctrl+C)")
    except Exception as e:
        print(f"\nПроизошла ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        video_processor.release()
        print("Ресурсы освобождены. Программа завершена.")


if __name__ == "__main__":
    main()
