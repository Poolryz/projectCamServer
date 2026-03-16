from fastapi import APIRouter, WebSocket

from ..websocket.video_handler import websocket_processed

router = APIRouter()


@router.websocket("/ws")
async def processed_websocket_endpoint(websocket: WebSocket):
    """WebSocket: сервер отправляет обработанные кадры и данные измерений."""
    await websocket_processed(websocket)
