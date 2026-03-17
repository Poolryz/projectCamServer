from collections import deque
from typing import Optional, Tuple, Dict, Any

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
        self._ema_width: Optional[float] = None
        self._last_edges: Optional[Tuple[float, float]] = None

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

    def build_metal_mask(self, hsv_mask: np.ndarray, enhanced_gray: np.ndarray) -> np.ndarray:
        """
        NEW: более стабильная маска металла.
        Берём HSV как подсказку, но добавляем маску по яркости (Otsu) в полосе измерения.
        Это помогает, когда HSV плохо отделяет металл/фон из-за ИК/освещения.
        """
        if self.measure_y is None:
            return hsv_mask

        h, w = enhanced_gray.shape[:2]
        y0 = max(0, int(self.measure_y - Config.MEASURE_BAND_HALF_HEIGHT))
        y1 = min(h, int(self.measure_y + Config.MEASURE_BAND_HALF_HEIGHT))

        band = enhanced_gray[y0:y1, :]
        # Otsu по полосе (стабильнее чем по всему кадру)
        _, thr = cv2.threshold(band, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        intensity_mask = np.zeros_like(hsv_mask)
        intensity_mask[y0:y1, :] = thr

        # Объединяем (OR) и чистим морфологией
        combined = cv2.bitwise_or(hsv_mask, intensity_mask)
        k = np.ones((Config.MASK_MORPH_KERNEL, Config.MASK_MORPH_KERNEL), np.uint8)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, k)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k)
        return combined

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

    def _detect_edges_for_row(
        self,
        row: int,
        hsv_mask: np.ndarray,
        enhanced: np.ndarray,
        left_bound: Optional[int] = None,
        right_bound: Optional[int] = None,
    ) -> Tuple[Optional[float], Optional[float], np.ndarray]:
        """Вычисляет позиции левого и правого краёв для одной строки.
        Возвращает (left_edge, right_edge, roi_norm)."""
        lb = left_bound if left_bound is not None else Config.MEASURE_LEFT
        rb = right_bound if right_bound is not None else self.measure_right
        roi_mask = hsv_mask[row, lb:rb]
        roi_enhanced = enhanced[row, lb:rb]

        roi_smooth = cv2.GaussianBlur(
            roi_enhanced.astype(np.float32),
            (1, Config.PROFILE_GAUSS_KERNEL),
            Config.PROFILE_GAUSS_SIGMA,
        ).flatten()

        mn, mx = np.min(roi_smooth), np.max(roi_smooth)
        roi_norm = (roi_smooth - mn) / (mx - mn) if mx > mn else roi_smooth

        coords_mask = np.where(roi_mask > 0)[0]
        if len(coords_mask) == 0:
            return None, None, roi_norm

        left_approx = coords_mask[0]
        left_start = max(0, left_approx - Config.EDGE_SEARCH_HALF_WINDOW)
        left_end = min(left_approx + Config.EDGE_SEARCH_HALF_WINDOW, len(roi_norm))
        left_edge = self.find_edge_position(
            roi_norm[left_start:left_end], left_start, edge_type='rising')

        right_approx = coords_mask[-1]
        right_start = max(0, right_approx - Config.EDGE_SEARCH_HALF_WINDOW)
        right_end = min(right_approx + Config.EDGE_SEARCH_HALF_WINDOW, len(roi_norm))
        right_edge = self.find_edge_position(
            roi_norm[right_start:right_end], right_start, edge_type='falling')

        return left_edge, right_edge, roi_norm

    def _compute_dynamic_bounds(
        self,
        metal_mask: np.ndarray,
        frame_width: int,
        pad: int = 60,
    ) -> Tuple[int, int]:
        """Вычисляет границы ROI по фактическому положению металла в полосе измерения.

        Сканирует несколько строк вокруг measure_y и берёт крайние пиксели маски.
        Это позволяет обнаруживать металл независимо от его горизонтального смещения.
        """
        half = Config.MEASURE_SCAN_LINES // 2
        h = metal_mask.shape[0]
        y0 = max(0, self.measure_y - half)
        y1 = min(h, self.measure_y + half + 1)

        band = metal_mask[y0:y1, :]
        cols = np.where(band > 0)[1]
        if len(cols) > 0:
            left_bound = max(0, int(cols.min()) - pad)
            right_bound = min(frame_width, int(cols.max()) + pad)
        else:
            # Металл не найден в полосе — используем стандартные границы
            left_bound = Config.MEASURE_LEFT
            right_bound = self.measure_right
        return left_bound, right_bound

    def measure_width_improved(
        self,
        hsv_mask: np.ndarray,
        enhanced: np.ndarray,
        frame: np.ndarray,
    ) -> Tuple[Optional[float], Dict[str, Any]]:
        """Улучшенный алгоритм измерения ширины с многострочным сканированием."""
        if self.measure_y is None or self.measure_right is None:
            return None, {"ok": False, "reason": "not_initialized"}

        # --- Динамические границы ROI: следуем за реальным положением металла ---
        dyn_left, dyn_right = self._compute_dynamic_bounds(hsv_mask, enhanced.shape[1])

        # --- Многострочное сканирование: медиана по N строкам убирает шум одной строки ---
        half = Config.MEASURE_SCAN_LINES // 2
        h = enhanced.shape[0]
        rows = range(max(0, self.measure_y - half), min(h, self.measure_y + half + 1))

        left_edges_all: list = []
        right_edges_all: list = []
        center_roi_norm: Optional[np.ndarray] = None

        for row in rows:
            le, re, roi_norm = self._detect_edges_for_row(
                row, hsv_mask, enhanced, dyn_left, dyn_right
            )
            if le is not None:
                left_edges_all.append(le)
            if re is not None:
                right_edges_all.append(re)
            if row == self.measure_y:
                center_roi_norm = roi_norm

        if len(left_edges_all) == 0 or len(right_edges_all) == 0:
            return None, {"ok": False, "reason": "edge_not_found"}

        # Медиана устойчива к выбросам отдельных строк
        left_edge = float(np.median(left_edges_all))
        right_edge = float(np.median(right_edges_all))

        roi_norm = center_roi_norm if center_roi_norm is not None else np.array([])

        width_px = right_edge - left_edge
        if width_px <= 0:
            return None, {"ok": False, "reason": "invalid_width_px", "width_px": float(width_px)}
        width_mm = width_px / self.px_to_mm

        if self._ema_width is not None:
            if abs(width_mm - self._ema_width) > Config.MAX_OUTLIER_DELTA_MM:
                return None, {
                    "ok": False,
                    "reason": "outlier_rejected",
                    "width_mm_raw": float(width_mm),
                    "width_mm_ref": float(self._ema_width),
                }

        left_abs = dyn_left + left_edge
        right_abs = dyn_left + right_edge

        cv2.line(
            frame,
            (int(round(left_abs)), self.measure_y - 20),
            (int(round(left_abs)), self.measure_y + 20),
            (0, 255, 0),
            3,
        )
        cv2.line(
            frame,
            (int(round(right_abs)), self.measure_y - 20),
            (int(round(right_abs)), self.measure_y + 20),
            (0, 255, 0),
            3,
        )

        if len(roi_norm) > 0:
            self.draw_intensity_profile(frame, roi_norm, int(round(left_edge)), int(round(right_edge)), dyn_left)

        if self._ema_width is None:
            self._ema_width = float(width_mm)
        else:
            a = Config.EMA_ALPHA
            self._ema_width = (1 - a) * self._ema_width + a * float(width_mm)

        self.width_history.append(self._ema_width)
        smoothed_width = float(np.mean(self.width_history)) if self.width_history else float(self._ema_width)

        self.last_valid_width = smoothed_width
        self.measurement_stats['valid_measurements'] += 1

        self._last_edges = (float(left_edge), float(right_edge))

        # Оценка уверенности по центральной строке
        confidence = 1.0
        if len(roi_norm) > 0:
            grad = np.gradient(roi_norm)
            max_abs_grad = float(np.max(np.abs(grad))) + 1e-9
            lwin = slice(max(0, int(round(left_edge)) - 5), min(len(grad), int(round(left_edge)) + 6))
            rwin = slice(max(0, int(round(right_edge)) - 5), min(len(grad), int(round(right_edge)) + 6))
            l_strength = float(np.max(grad[lwin])) / max_abs_grad if (lwin.stop - lwin.start) > 0 else 0.0
            r_strength = float(-np.min(grad[rwin])) / max_abs_grad if (rwin.stop - rwin.start) > 0 else 0.0
            confidence = float(max(0.0, min(1.0, (l_strength + r_strength) / 2.0)))

        if confidence < Config.MIN_CONFIDENCE_THRESHOLD:
            return None, {
                "ok": False,
                "reason": "low_confidence",
                "confidence": confidence,
                "width_mm_raw": float(width_mm),
            }

        return smoothed_width, {
            "ok": True,
            "width_mm_raw": float(width_mm),
            "width_mm": float(smoothed_width),
            "width_mm_2dp": float(round(smoothed_width, 2)),
            "width_px": float(width_px),
            "left_edge_px": float(left_abs),
            "right_edge_px": float(right_abs),
            "left_edge_px_2dp": float(round(left_abs, 2)),
            "right_edge_px_2dp": float(round(right_abs, 2)),
            "measure_y": int(self.measure_y),
            "confidence": confidence,
        }

    def find_edge_position(self, profile: np.ndarray, offset: int, edge_type: str = 'rising') -> Optional[float]:
        """Поиск края по пересечению порогового уровня (50% перехода).

        Метод порогового пересечения устойчив для размытых и тёмных краёв:
        точка пересечения середины склона остаётся стабильной даже при
        плавном/неравномерном переходе, тогда как пик градиента на размытом
        крае плоский и легко сдвигается шумом.
        Fallback: пик градиента, если пересечение не найдено.
        """
        if len(profile) < 3:
            return None

        # Дополнительное сглаживание в окне поиска — подавляет шум на размытом крае
        sigma = Config.EDGE_EXTRA_SMOOTH_SIGMA
        k = max(3, int(6 * sigma + 1) | 1)  # нечётный размер ядра
        smooth = cv2.GaussianBlur(
            profile.astype(np.float32).reshape(1, -1),
            (k, 1),
            sigma,
        ).flatten()

        lo = float(np.min(smooth))
        hi = float(np.max(smooth))
        if hi - lo < 0.05:
            return None

        threshold = lo + Config.EDGE_THRESHOLD_FRACTION * (hi - lo)

        if edge_type == 'rising':
            # Ищем первое пересечение снизу вверх (фон → металл)
            for i in range(len(smooth) - 1):
                if smooth[i] <= threshold < smooth[i + 1]:
                    t = (threshold - float(smooth[i])) / (float(smooth[i + 1]) - float(smooth[i]) + 1e-9)
                    return float(offset) + float(i) + t
        else:
            # Ищем последнее пересечение сверху вниз (металл → фон).
            # Скан с правого конца, чтобы правый край тёмного объекта
            # не сместил нас влево из-за провала яркости на самом крае.
            for i in range(len(smooth) - 2, -1, -1):
                if smooth[i] >= threshold > smooth[i + 1]:
                    t = (float(smooth[i]) - threshold) / (float(smooth[i]) - float(smooth[i + 1]) + 1e-9)
                    return float(offset) + float(i) + t

        # Fallback: пик градиента с субпиксельной интерполяцией
        gradient = np.gradient(smooth)
        edge_idx: float = float(np.argmax(gradient) if edge_type == 'rising' else np.argmin(gradient))
        ei = int(edge_idx)
        if 0 < ei < len(gradient) - 1:
            y0 = float(gradient[ei - 1])
            y1 = float(gradient[ei])
            y2 = float(gradient[ei + 1])
            denom = y0 - 2.0 * y1 + y2
            if denom != 0.0:
                edge_idx = float(ei) + 0.5 * (y0 - y2) / denom

        return float(offset) + float(edge_idx)

    def draw_intensity_profile(self, frame: np.ndarray, profile: np.ndarray,
                             left_edge: int, right_edge: int,
                             left_offset: Optional[int] = None):
        """НОВЫЙ: Визуализация профиля интенсивности"""
        x_origin = left_offset if left_offset is not None else Config.MEASURE_LEFT

        profile_height = 50
        profile_y_start = self.measure_y + 60
        profile_width = len(profile)

        if np.max(profile) > np.min(profile):
            profile_norm = (profile - np.min(profile)) / (np.max(profile) - np.min(profile))
        else:
            profile_norm = profile

        for x in range(1, min(profile_width, frame.shape[1] - x_origin)):
            x_abs = x_origin + x
            y1 = profile_y_start + int(profile_norm[x-1] * profile_height)
            y2 = profile_y_start + int(profile_norm[x] * profile_height)
            cv2.line(frame, (x_abs-1, y1), (x_abs, y2), (200, 200, 200), 1)

        if left_edge < len(profile_norm):
            cv2.circle(frame, (x_origin + left_edge,
                     profile_y_start + int(profile_norm[left_edge] * profile_height)),
                     3, (0, 255, 0), -1)
        if right_edge < len(profile_norm):
            cv2.circle(frame, (x_origin + right_edge,
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

        # 2.1 NEW: комбинированная маска (HSV + яркость в полосе)
        metal_mask = self.build_metal_mask(hsv_mask, enhanced)

        # 3. Точное определение границ
        edges = self.detect_edges_accurately(enhanced, metal_mask)

        # 4. Измерение ширины
        width_mm, meta = self.measure_width_improved(metal_mask, enhanced, frame)

        # 5. Визуализация
        frame = self.visualize_results(frame, metal_mask, edges, width_mm)

        # meta может быть полезен для WebSocket
        meta_out: Dict[str, Any] = {"timestamp": float(cv2.getTickCount() / cv2.getTickFrequency())}
        meta_out.update(meta if isinstance(meta, dict) else {})
        return frame, width_mm, meta_out

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
