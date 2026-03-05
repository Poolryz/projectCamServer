from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import threading
import time
from datetime import datetime
import cv2
import numpy as np
import base64

# Создаем экземпляр FastAPI
app = FastAPI(title="Metal Width Monitor API", description="API для мониторинга ширины металла")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные переменные для хранения состояния
system_state = {
    "is_running": False,
    "current_width": None,
    "threshold": 134.0,
    "request_count": 0,
    "last_trigger_width": 0,
    "pause_requests": False,
    "frame_count": 0,
    "timestamp": None,
    "latest_frame": None
}

# Модели данных для API
class ThresholdUpdate(BaseModel):
    threshold: float

class PauseUpdate(BaseModel):
    pause: bool

class SystemStatus(BaseModel):
    is_running: bool
    current_width: Optional[float]
    threshold: float
    request_count: int
    last_trigger_width: float
    pause_requests: bool
    frame_count: int
    timestamp: Optional[str]

# API эндпоинты
@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Metal Width Monitor API",
        "version": "1.0.0",
        "endpoints": [
            "/status - текущий статус системы",
            "/threshold - управление порогом",
            "/pause - пауза/продолжение запросов",
            "/stats - статистика",
            "/frame - текущий кадр"
        ]
    }

@app.get("/status", response_model=SystemStatus, tags=["Status"])
async def get_status():
    """Получить текущий статус системы"""
    return SystemStatus(
        is_running=system_state["is_running"],
        current_width=system_state["current_width"],
        threshold=system_state["threshold"],
        request_count=system_state["request_count"],
        last_trigger_width=system_state["last_trigger_width"],
        pause_requests=system_state["pause_requests"],
        frame_count=system_state["frame_count"],
        timestamp=system_state["timestamp"]
    )

@app.post("/threshold", tags=["Control"])
async def set_threshold(threshold_data: ThresholdUpdate):
    """Установить порог срабатывания"""
    if threshold_data.threshold < 100:
        raise HTTPException(status_code=400, detail="Threshold must be >= 100")
    
    system_state["threshold"] = threshold_data.threshold
    return {
        "message": "Threshold updated successfully",
        "threshold": system_state["threshold"]
    }

@app.post("/pause", tags=["Control"])
async def set_pause(pause_data: PauseUpdate):
    """Установить паузу запросов"""
    system_state["pause_requests"] = pause_data.pause
    return {
        "message": f"Requests {'paused' if pause_data.pause else 'resumed'}",
        "pause": system_state["pause_requests"]
    }

@app.get("/stats", tags=["Statistics"])
async def get_stats():
    """Получить подробную статистику"""
    return {
        "measurements": {
            "total_frames": system_state["frame_count"],
            "current_width": system_state["current_width"],
            "last_measurement": system_state["timestamp"]
        },
        "requests": {
            "total_sent": system_state["request_count"],
            "last_trigger_width": system_state["last_trigger_width"],
            "paused": system_state["pause_requests"]
        },
        "settings": {
            "threshold": system_state["threshold"]
        }
    }

@app.get("/frame", tags=["Video"])
async def get_frame():
    """Получить текущий кадр в base64"""
    if system_state["latest_frame"] is None:
        raise HTTPException(status_code=404, detail="No frame available")
    
    return {
        "frame": system_state["latest_frame"],
        "timestamp": system_state["timestamp"],
        "width": system_state["current_width"]
    }

@app.post("/reset", tags=["Control"])
async def reset_stats():
    """Сбросить статистику"""
    system_state["frame_count"] = 0
    system_state["request_count"] = 0
    system_state["last_trigger_width"] = 0
    return {"message": "Statistics reset successfully"}

# Функция для запуска FastAPI в отдельном потоке
def run_fastapi(host="0.0.0.0", port=8000):
    """Запуск FastAPI сервера"""
    uvicorn.run(app, host=host, port=port, log_level="info")

# Функция для обновления состояния системы
def update_system_state(**kwargs):
    """Обновление глобального состояния системы"""
    for key, value in kwargs.items():
        if key in system_state:
            system_state[key] = value
    
    system_state["timestamp"] = datetime.now().isoformat()

# Функция для кодирования кадра в base64
def encode_frame_to_base64(frame):
    """Конвертировать OpenCV кадр в base64 строку"""
    if frame is None:
        return None
    
    _, buffer = cv2.imencode('.jpg', frame)
    return base64.b64encode(buffer).decode('utf-8')