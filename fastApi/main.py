from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time

from .routes import video, pages
from .services.video_stream import VideoStream, RTSP_URL
from .services.processed_stream import ProcessedStream

# Создаем экземпляр FastAPI
app = FastAPI(title="RTSP Stream Server")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализируем видеопоток
video_stream = VideoStream(RTSP_URL)
processed_stream = ProcessedStream()

# Подключаем маршруты
app.include_router(pages.router, tags=["pages"])
app.include_router(video.router, prefix="/video", tags=["video"])

# Добавляем видеопоток в состояние приложения
app.state.video_stream = video_stream
app.state.processed_stream = processed_stream

@app.on_event("startup")
async def startup_event():
    """Запуск видеопотока при старте сервера"""
    success = video_stream.start()
    if not success:
        print("ВНИМАНИЕ: Не удалось запустить видеопоток")
    else:
        print("Видеопоток успешно запущен")

@app.on_event("shutdown")
async def shutdown_event():
    """Остановка видеопотока при завершении"""
    video_stream.stop()
    print("Видеопоток остановлен")

@app.get("/health")
async def health_check():
    """Проверка здоровья сервера"""
    return {
        "status": "healthy",
        "video_stream": video_stream.is_running,
        "timestamp": time.time()
    }

# Функция для запуска сервера
def run_fastapi(host="0.0.0.0", port=8000):
    """Запуск FastAPI сервера"""
    print(f"Запуск FastAPI сервера на http://{host}:{port}")
    print(f"RTSP URL: {RTSP_URL}")
    print(f"Тестовая страница: http://localhost:{port}/")
    print(f"MJPEG поток: http://localhost:{port}/video/feed")
    print(f"WebSocket: ws://localhost:{port}/video/ws")
    print(f"Статус: http://localhost:{port}/video/status")
    
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    run_fastapi()
