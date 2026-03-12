from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def get_home():
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
                img { width: 100%%; border: 2px solid #333; border-radius: 8px; }
                .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
                .connected { background-color: #d4edda; color: #155724; }
                .disconnected { background-color: #f8d7da; color: #721c24; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>RTSP Stream Test</h1>
                <div id="status" class="status disconnected">Проверка подключения...</div>
                <img id="video" src="/video/feed" width="640" height="480">
                <div style="margin-top: 20px;">
                    <h3>Доступные эндпоинты:</h3>
                    <ul>
                        <li><a href="/video/feed">/video/feed</a> - MJPEG поток</li>
                        <li><a href="/video/frame">/video/frame</a> - Получить один кадр (JSON)</li>
                        <li><a href="/video/status">/video/status</a> - Статус видеопотока</li>
                        <li><a href="/health">/health</a> - Проверка здоровья</li>
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
                    fetch('/video/frame')
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

@router.get("/test")
async def test_page():
    """Простая тестовая страница"""
    return {"message": "FastAPI server is running"}
