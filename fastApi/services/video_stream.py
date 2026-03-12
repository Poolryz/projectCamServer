import cv2
import threading
import time

# Конфигурация RTSP
RTSP_URL = "rtsp://admin:120698da@192.168.2.36:554/Streaming/Channels/1"

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
