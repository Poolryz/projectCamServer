from fastapi import WebSocket, WebSocketDisconnect, Request
import cv2
import base64
import time

async def websocket_video(websocket: WebSocket):
    """WebSocket обработчик для отправки кадров в base64"""
    await websocket.accept()
    print("WebSocket клиент подключен")
    
    try:
        # Получаем доступ к видеопотоку через app state
        video_stream = websocket.app.state.video_stream
        
        while True:
            # Ждем команду от клиента
            data = await websocket.receive_text()
            
            if data == "get_frame":
                frame = video_stream.get_frame()
                if frame is not None:
                    # Уменьшаем размер кадра если нужно
                    height, width = frame.shape[:2]
                    new_width, new_height = width, height
                    
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
                        "width": new_width,
                        "height": new_height
                    })
            elif data == "ping":
                await websocket.send_json({
                    "type": "pong", 
                    "timestamp": time.time()
                })
                
    except WebSocketDisconnect:
        print("WebSocket клиент отключен")
    except Exception as e:
        print(f"Ошибка WebSocket: {e}")
