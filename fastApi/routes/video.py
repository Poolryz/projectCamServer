from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse
import cv2
import numpy as np
import base64
import asyncio
import time

from ..websocket.video_handler import websocket_video

router = APIRouter()

@router.get("/feed")
async def video_feed(request: Request):
    """Endpoint для MJPEG потока"""
    video_stream = request.app.state.video_stream
    
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

@router.get("/frame")
async def get_frame(request: Request):
    """Получение одного кадра в base64"""
    video_stream = request.app.state.video_stream
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

@router.get("/status")
async def get_status(request: Request):
    """Проверка статуса видеопотока"""
    video_stream = request.app.state.video_stream
    frame = video_stream.get_frame()
    
    return {
        "is_running": video_stream.is_running,
        "has_frame": frame is not None,
        "timestamp": time.time()
    }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для отправки кадров"""
    await websocket_video(websocket)
