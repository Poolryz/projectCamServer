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

    # Полоса по Y вокруг линии измерения (для построения устойчивой маски)
    MEASURE_BAND_HALF_HEIGHT = 40

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

    # --- NEW: стабильное субпиксельное измерение ---
    # Окно поиска края вокруг грубой границы HSV (в пикселях ROI)
    EDGE_SEARCH_HALF_WINDOW = 25

    # Сглаживание профиля яркости вдоль линии измерения
    PROFILE_GAUSS_KERNEL = 7   # должно быть нечётным
    PROFILE_GAUSS_SIGMA = 1.2

    # Отбраковка выбросов (если измерение "прыгает" слишком сильно)
    MAX_OUTLIER_DELTA_MM = 25.0

    # EMA-фильтр (0..1): больше -> быстрее реагирует, меньше -> стабильнее
    EMA_ALPHA = 0.25

    # Морфология для очистки маски (ядро NxN)
    MASK_MORPH_KERNEL = 5
