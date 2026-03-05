import numpy as np

# =================== КОНФИГУРАЦИЯ ===================
class Config:
    # Настройки для ESP8266
    ESP_IP = "192.168.2.72"
    REQUEST_INTERVAL = 5  # Интервал в секундах между запросами

    # Настройки для видео
    VIDEO_PATH = "rtsp://admin:120698da@192.168.2.36:554/Streaming/Channels/1"
    SAVE_DIR = r"C:\Users\РН\Desktop\test 4\defects"

    # Настройки для обработки изображения - УЛУЧШЕННЫЕ
    LOWER_METAL = np.array([0, 0, 45])
    UPPER_METAL = np.array([0, 0, 100])
    REAL_WIDTH_MM = 222.8
    EXPECTED_WIDTH_PX = 1011

    # Границы измерения
    MEASURE_LEFT = 250

    # НОВЫЕ ПАРАМЕТРЫ ДЛЯ УЛУЧШЕНИЯ ТОЧНОСТИ
    # Параметры для медианного фильтра (шумоподавление)
    MEDIAN_BLUR_KERNEL = 3

    # Параметры для CLAHE (улучшение контраста)
    CLAHE_CLIP_LIMIT = 4.0
    CLAHE_GRID_SIZE = (8, 8)

    # Параметры для Canny Edge Detection
    CANNY_THRESHOLD1 = 35
    CANNY_THRESHOLD2 = 40

    # Параметры для сглаживания измерений
    WIDTH_HISTORY_SIZE = 10  # Количество кадров для усреднения
    MIN_WIDTH_CHANGE = 0.4   # Минимальное изменение ширины для срабатывания (мм)

    # Допуски для определения границ
    EDGE_THRESHOLD = 0.8     # Порог для определения края (относительный)
