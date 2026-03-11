from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from typing import Optional, Dict, Any
import uvicorn
import threading
import time
from datetime import datetime
import cv2
import numpy as np
import base64
import asyncio  # Добавьте этот импорт

# Создаем экземпляр FastAPI
app = FastAPI()

# Настройка CORS - исправляем origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Убрали слеш в конце
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Хранилище для видеопотока
class VideoStream:
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.cap = None
        self.is_running = False
        self.current_frame = None
        self.lock = threading.Lock()
        
    def start(self):
        """Запуск захвата видео"""
        try:
            self.cap = cv2.VideoCapture(self.rtsp_url)
            if not self.cap.isOpened():
                print(f"Не удалось открыть RTSP поток: {self.rtsp_url}")
                return False
                
            self.is_running = True
            print(f"RTSP поток успешно открыт: {self.rtsp_url}")
            
            # Запускаем поток для непрерывного чтения кадров
            self.thread = threading.Thread(target=self._update_frame, daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            print(f"Ошибка при запуске видеопотока: {e}")
            return False
        
    def _update_frame(self):
        """Непрерывное обновление кадра в фоновом потоке"""
        retry_count = 0
        max_retries = 5
        
        while self.is_running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    print("Переподключение к RTSP потоку...")
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    retry_count = 0
                    
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.current_frame = frame
                    retry_count = 0
                else:
                    retry_count += 1
                    print(f"Ошибка чтения кадра, попытка {retry_count}/{max_retries}")
                    
                    if retry_count >= max_retries:
                        print("Переподключение к RTSP потоку...")
                        self.cap.release()
                        self.cap = cv2.VideoCapture(self.rtsp_url)
                        retry_count = 0
                        
            except Exception as e:
                print(f"Ошибка в _update_frame: {e}")
                retry_count += 1
                
            time.sleep(0.03)  # ~30 FPS
            
    def get_frame(self):
        """Получение текущего кадра"""
        with self.lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
            return None
            
    def stop(self):
        """Остановка захвата"""
        self.is_running = False
        if self.cap:
            self.cap.release()
            print("Видеопоток остановлен")

# Инициализируем видеопоток с вашим RTSP URL
RTSP_URL = "rtsp://admin:120698da@192.168.2.36:554/Streaming/Channels/1"  # Ваш RTSP адрес
video_stream = VideoStream(RTSP_URL)

@app.on_event("startup")
async def startup_event():
    """Запуск видеопотока при старте сервера"""
    success = video_stream.start()
    if not success:
        print("ВНИМАНИЕ: Не удалось запустить видеопоток")

@app.on_event("shutdown")
async def shutdown_event():
    """Остановка видеопотока при завершении"""
    video_stream.stop()

@app.get("/")
async def get():
    """Тестовая страница"""
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>RTSP Stream Test</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                .container { max-width: 800px; margin: 0 auto; }
                img { width: 100%; border: 2px solid #333; border-radius: 8px; }
                .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
                .connected { background-color: #d4edda; color: #155724; }
                .disconnected { background-color: #f8d7da; color: #721c24; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>RTSP Stream Test</h1>
                <div id="status" class="status disconnected">Проверка подключения...</div>
                <img id="video" src="/video_feed" width="640" height="480">
                <div style="margin-top: 20px;">
                    <h3>Доступные эндпоинты:</h3>
                    <ul>
                        <li><a href="/video_feed">/video_feed</a> - MJPEG поток</li>
                        <li><a href="/frame">/frame</a> - Получить один кадр (JSON)</li>
                        <li>ws://localhost:8000/ws/video - WebSocket поток</li>
                    </ul>
                </div>
            </div>
            <script>
                const img = document.getElementById('video');
                const statusDiv = document.getElementById('status');
                
                img.onload = function() {
                    statusDiv.className = 'status connected';
                    statusDiv.textContent = '✓ Подключено к видеопотоку';
                };
                
                img.onerror = function() {
                    statusDiv.className = 'status disconnected';
                    statusDiv.textContent = '✗ Ошибка подключения к видеопотоку';
                };
                
                // Проверка каждые 5 секунд
                setInterval(() => {
                    fetch('/frame')
                        .then(response => response.json())
                        .then(data => {
                            if (data.frame) {
                                statusDiv.className = 'status connected';
                                statusDiv.textContent = '✓ Сервер работает, видеопоток активен';
                            }
                        })
                        .catch(error => {
                            statusDiv.className = 'status disconnected';
                            statusDiv.textContent = '✗ Сервер недоступен';
                        });
                }, 5000);
            </script>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/video_feed")
async def video_feed():
    """Endpoint для MJPEG потока (простой способ)"""
    async def generate():
        while True:
            frame = video_stream.get_frame()
            if frame is not None:
                # Кодируем кадр в JPEG с уменьшенным качеством для экономии трафика
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
                ret, buffer = cv2.imencode('.jpg', frame, encode_params)
                if ret:
                    # Отправляем как MJPEG
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           buffer.tobytes() + b'\r\n')
            await asyncio.sleep(0.03)  # ~30 FPS
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket):
    """WebSocket endpoint для отправки кадров в base64"""
    await websocket.accept()
    print("WebSocket клиент подключен")
    
    try:
        while True:
            # Ждем команду от клиента
            data = await websocket.receive_text()
            
            if data == "get_frame":
                frame = video_stream.get_frame()
                if frame is not None:
                    # Уменьшаем размер кадра если нужно
                    height, width = frame.shape[:2]
                    if width > 640:
                        scale = 640 / width
                        new_width = 640
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    
                    # Кодируем в base64 с уменьшенным качеством
                    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
                    _, buffer = cv2.imencode('.jpg', frame, encode_params)
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')
                    
                    await websocket.send_json({
                        "type": "frame",
                        "data": frame_base64,
                        "timestamp": time.time(),
                        "width": new_width if 'new_width' in locals() else width,
                        "height": new_height if 'new_height' in locals() else height
                    })
            elif data == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
                
    except WebSocketDisconnect:
        print("WebSocket клиент отключен")
    except Exception as e:
        print(f"Ошибка WebSocket: {e}")

@app.get("/frame")
async def get_frame():
    """Получение одного кадра в base64"""
    frame = video_stream.get_frame()
    if frame is not None:
        # Уменьшаем качество для экономии трафика
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
        _, buffer = cv2.imencode('.jpg', frame, encode_params)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            "success": True,
            "frame": frame_base64,
            "timestamp": time.time(),
            "shape": frame.shape
        }
    
    return {
        "success": False,
        "error": "No frame available",
        "timestamp": time.time()
    }

@app.get("/status")
async def get_status():
    """Проверка статуса видеопотока"""
    frame = video_stream.get_frame()
    return {
        "is_running": video_stream.is_running,
        "has_frame": frame is not None,
        "timestamp": time.time()
    }

# Функция для запуска сервера
def run_fastapi(host="0.0.0.0", port=8000):
    """Запуск FastAPI сервера"""
    print(f"Запуск FastAPI сервера на http://{host}:{port}")
    print(f"RTSP URL: {RTSP_URL}")
    print(f"Тестовая страница: http://localhost:{port}/")
    print(f"MJPEG поток: http://localhost:{port}/video_feed")
    print(f"WebSocket: ws://localhost:{port}/ws/video")
    print(f"Статус: http://localhost:{port}/status")
    
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    run_fastapi()
