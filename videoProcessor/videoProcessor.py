from collections import deque
from typing import Optional, Tuple

import cv2
import numpy as np
from config.config import Config

# =================== КЛАСС ДЛЯ УЛУЧШЕННОЙ ОБРАБОТКИ ВИДЕО ===================
class ImprovedVideoProcessor:
    def __init__(self, video_path: str = Config.VIDEO_PATH):
        self.video_path = video_path
        self.cap = None
        self.measure_y = None
        self.measure_right = None
        self.px_to_mm = Config.EXPECTED_WIDTH_PX / Config.REAL_WIDTH_MM

        # НОВОЕ: Буфер для сглаживания измерений
        self.width_history = deque(maxlen=Config.WIDTH_HISTORY_SIZE)
        self.last_valid_width = None

        # НОВОЕ: Инициализация CLAHE для улучшения контраста
        self.clahe = cv2.createCLAHE(
            clipLimit=Config.CLAHE_CLIP_LIMIT,
            tileGridSize=Config.CLAHE_GRID_SIZE
        )

        # НОВОЕ: Статистика
        self.measurement_stats = {
            'total_measurements': 0,
            'valid_measurements': 0,
            'edges_detected': 0
        }

    def initialize(self) -> bool:
        """Инициализирует видеопоток и рассчитывает параметры"""
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            print(f"Ошибка: Не удалось открыть видео по адресу {self.video_path}")
            return False

        # Расчет параметров измерения
        frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))

        self.measure_y = (frame_height // 2) - 45
        self.measure_right = frame_width - 220

        print(f"Видео инициализировано: {frame_width}x{frame_height}")
        print(f"Линия измерения: Y={self.measure_y}, X=[{Config.MEASURE_LEFT}, {self.measure_right}]")
        print(f"Коэффициент: {self.px_to_mm:.3f} px/mm")

        return True

    def preprocess_image(self, frame: np.ndarray) -> np.ndarray:
        """НОВЫЙ: Улучшенная предобработка изображения"""
        # Конвертация в градации серого для улучшения контраста
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Применение CLAHE для локального улучшения контраста
        enhanced = self.clahe.apply(gray)

        # Медианный фильтр для удаления шума с сохранением границ
        denoised = cv2.medianBlur(enhanced, Config.MEDIAN_BLUR_KERNEL)

        return denoised

    def detect_edges_accurately(self, enhanced: np.ndarray, hsv_mask: np.ndarray) -> np.ndarray:
        """НОВЫЙ: Точное определение границ с помощью комбинации методов"""
        # Детекция границ методом Canny
        edges = cv2.Canny(enhanced, Config.CANNY_THRESHOLD1, Config.CANNY_THRESHOLD2)

        # Объединение с HSV маской для выделения только области металла
        combined_edges = cv2.bitwise_and(edges, edges, mask=hsv_mask)

        # Морфологическое замыкание для соединения разрывов в границах
        kernel = np.ones((3, 3), np.uint8)
        closed_edges = cv2.morphologyEx(combined_edges, cv2.MORPH_CLOSE, kernel)

        return closed_edges

    def measure_width_improved(self, hsv_mask: np.ndarray, enhanced: np.ndarray,
                              frame: np.ndarray) -> Optional[float]:
        """НОВЫЙ: Улучшенный алгоритм измерения ширины"""
        if self.measure_y is None or self.measure_right is None:
            return None

        # Получаем строку для анализа
        roi_mask = hsv_mask[self.measure_y, Config.MEASURE_LEFT:self.measure_right]
        roi_enhanced = enhanced[self.measure_y, Config.MEASURE_LEFT:self.measure_right]

        # Сглаживание сигнала
        roi_smooth = cv2.GaussianBlur(roi_enhanced.astype(np.float32), (1, 5), 1).flatten()

        # Нормализация
        if np.max(roi_smooth) > np.min(roi_smooth):
            roi_norm = (roi_smooth - np.min(roi_smooth)) / (np.max(roi_smooth) - np.min(roi_smooth))
        else:
            roi_norm = roi_smooth

        # Поиск границ с помощью маски HSV (грубое определение)
        coords_mask = np.where(roi_mask > 0)[0]

        if len(coords_mask) == 0:
            return None

        # Точное определение левой границы
        left_approx = coords_mask[0]
        left_start = max(0, left_approx - 15)
        left_end = min(left_approx + 15, len(roi_norm))
        left_region = slice(left_start, left_end)
        left_edge = self.find_edge_position(roi_norm[left_region],
                                  left_start,  # Передаем смещение, а не search_region_left.start
                                  edge_type='rising')

        # Точное определение правой границы
        right_approx = coords_mask[-1]
        right_start = max(0, right_approx - 15)
        right_end = min(right_approx + 15, len(roi_norm))
        right_region = slice(right_start, right_end)
        right_edge = self.find_edge_position(roi_norm[right_region],
                                   right_start,  # Передаем смещение, а не search_region_right.start
                                   edge_type='falling')

        if left_edge is None or right_edge is None:
            return None

        # Вычисление ширины в пикселях
        width_px = right_edge - left_edge
        width_mm = width_px / self.px_to_mm

        # Визуализация
        left_abs = Config.MEASURE_LEFT + left_edge
        right_abs = Config.MEASURE_LEFT + right_edge

        # Рисуем точные границы
        cv2.line(frame, (left_abs, self.measure_y - 20),
                (left_abs, self.measure_y + 20), (0, 255, 0), 3)
        cv2.line(frame, (right_abs, self.measure_y - 20),
                (right_abs, self.measure_y + 20), (0, 255, 0), 3)

        # Рисуем линию профиля интенсивности
        self.draw_intensity_profile(frame, roi_norm, left_edge, right_edge)

        # Сглаживание измерений
        self.width_history.append(width_mm)
        smoothed_width = np.mean(self.width_history) if self.width_history else width_mm

        self.last_valid_width = smoothed_width
        self.measurement_stats['valid_measurements'] += 1

        return smoothed_width

    def find_edge_position(self, profile: np.ndarray, offset: int, edge_type: str = 'rising') -> Optional[int]:
        """НОВЫЙ: Точное определение позиции границы по профилю интенсивности"""
        if len(profile) == 0:
            return None

        # Вычисление градиента
        gradient = np.gradient(profile)

        if edge_type == 'rising':
            # Ищем максимальный положительный градиент
            edge_idx = np.argmax(gradient)
        else:
            # Ищем минимальный отрицательный градиент (максимальный по модулю)
            edge_idx = np.argmin(gradient)

        # Субпиксельная интерполяция для большей точности
        if 0 < edge_idx < len(gradient) - 1:
            # Квадратичная интерполяция
            try:
                x0, x1, x2 = edge_idx - 1, edge_idx, edge_idx + 1
                y0, y1, y2 = gradient[x0], gradient[x1], gradient[x2]

                denominator = 2 * ((y2 - y1) - (y0 - y1))
                if denominator != 0:
                    offset_subpixel = (x1 - x0) * (y2 - y0) / denominator
                    edge_idx = x0 + offset_subpixel
            except:
                pass

        return int(offset + edge_idx)

    def draw_intensity_profile(self, frame: np.ndarray, profile: np.ndarray,
                             left_edge: int, right_edge: int):
        """НОВЫЙ: Визуализация профиля интенсивности"""
        # Параметры отображения
        profile_height = 50
        profile_y_start = self.measure_y + 60
        profile_width = len(profile)

        # Нормализация профиля для отображения
        if np.max(profile) > np.min(profile):
            profile_norm = (profile - np.min(profile)) / (np.max(profile) - np.min(profile))
        else:
            profile_norm = profile

        # Рисуем профиль
        for x in range(1, min(profile_width, frame.shape[1] - Config.MEASURE_LEFT)):
            x_abs = Config.MEASURE_LEFT + x
            y1 = profile_y_start + int(profile_norm[x-1] * profile_height)
            y2 = profile_y_start + int(profile_norm[x] * profile_height)
            cv2.line(frame, (x_abs-1, y1), (x_abs, y2), (200, 200, 200), 1)

        # Отмечаем границы на профиле
        if left_edge < len(profile_norm):
            cv2.circle(frame, (Config.MEASURE_LEFT + left_edge,
                     profile_y_start + int(profile_norm[left_edge] * profile_height)),
                     3, (0, 255, 0), -1)
        if right_edge < len(profile_norm):
            cv2.circle(frame, (Config.MEASURE_LEFT + right_edge,
                     profile_y_start + int(profile_norm[right_edge] * profile_height)),
                     3, (0, 255, 0), -1)

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Optional[float]]:
        """Улучшенная обработка кадра"""
        self.measurement_stats['total_measurements'] += 1

        # 1. HSV маска для выделения металла
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv_mask = cv2.inRange(hsv, Config.LOWER_METAL, Config.UPPER_METAL)

        # 2. Улучшенная предобработка
        enhanced = self.preprocess_image(frame)

        # 3. Точное определение границ
        edges = self.detect_edges_accurately(enhanced, hsv_mask)

        # 4. Измерение ширины
        width_mm = self.measure_width_improved(hsv_mask, enhanced, frame)

        # 5. Визуализация
        frame = self.visualize_results(frame, hsv_mask, edges, width_mm)

        return frame, width_mm

    def visualize_results(self, frame: np.ndarray, hsv_mask: np.ndarray,
                         edges: np.ndarray, width_mm: Optional[float]) -> np.ndarray:
        """Улучшенная визуализация результатов"""
        # Рисуем линии измерения
        cv2.line(frame, (Config.MEASURE_LEFT, self.measure_y - 30),
                (self.measure_right, self.measure_y - 30), (255, 255, 0), 2)
        cv2.line(frame, (Config.MEASURE_LEFT, self.measure_y + 30),
                (self.measure_right, self.measure_y + 30), (255, 255, 0), 2)

        # Отображение ширины с улучшенным форматированием
        if width_mm is not None:
            # Цвет в зависимости от значения
            color = (0, 255, 0) if width_mm >= 134 else (0, 0, 255)

            cv2.putText(
                frame,
                f"Width: {width_mm:.2f} mm",
                (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                color,
                2
            )

            # Отображение статистики
            reliability = (self.measurement_stats['valid_measurements'] /
                         max(1, self.measurement_stats['total_measurements'])) * 100
            cv2.putText(
                frame,
                f"Reliability: {reliability:.1f}%",
                (50, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1
            )
        else:
            cv2.putText(
                frame,
                "Width: N/A",
                (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

        # Визуализация границ Canny (маленькое окошко)
        edges_small = cv2.resize(edges, (320, 240))
        edges_colored = cv2.cvtColor(edges_small, cv2.COLOR_GRAY2BGR)

        # Вставляем маленькое окошко в правый верхний угол
        h, w = frame.shape[:2]
        frame[10:250, w-330:w-10] = cv2.resize(edges_colored, (320, 240))

        return frame

    def release(self):
        """Освобождает ресурсы видеопотока"""
        if self.cap is not None:
            self.cap.release()
            print("\nСтатистика измерений:")
            print(f"  Всего измерений: {self.measurement_stats['total_measurements']}")
            print(f"  Успешных измерений: {self.measurement_stats['valid_measurements']}")
            if self.measurement_stats['total_measurements'] > 0:
                reliability = (self.measurement_stats['valid_measurements'] /
                             self.measurement_stats['total_measurements'] * 100)
                print(f"  Надежность: {reliability:.1f}%")
