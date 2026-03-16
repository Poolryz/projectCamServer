from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .routes import video, pages
from .services.processed_stream import ProcessedStream

app = FastAPI(title="Metal Width Monitor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

processed_stream = ProcessedStream()
app.state.processed_stream = processed_stream

app.include_router(pages.router, tags=["pages"])
app.include_router(video.router, prefix="/video", tags=["video"])


def run_fastapi(host: str = "0.0.0.0", port: int = 8000):
    from config.config import Config
    print(f"Запуск FastAPI сервера на http://{host}:{port}")
    print(f"RTSP URL: {Config.VIDEO_PATH}")
    print(f"Тестовая страница: http://localhost:{port}/")
    print(f"WebSocket: ws://localhost:{port}/video/ws")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_fastapi()
