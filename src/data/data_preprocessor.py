"""
ESS AI System - 데이터 품질 관리 및 AI 입력 전처리
- 3-시그마 필터링
- 변화율 검증
- ML 모델 입력 준비
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats

from ..models.sensor_data import SystemSensorData, SigmaFilter


@dataclass
class DataQualityMetrics:
    """데이터 품질 지표"""
    outliers_detected: int = 0
    outliers_filtered: int = 0
    interpolations: int = 0
    rate_violations: int = 0
    total_samples: int = 0

    def get_quality_rate(self) -> float:
        """품질 비율 (%))"""
        if self.total_samples == 0:
            return 100.0
        issues = self.outliers_detected + self.rate_violations
        return ((self.total_samples - issues) / self.total_samples) * 100.0


class DataPreprocessor:
    """
    데이터 전처리기
    - 이상치 필터링 (3-시그마)
    - 변화율 검증
    - ML 모델 입력 준비
    """

    def __init__(self, sigma_window_size: int = 30):
        self.sigma_filter = SigmaFilter(window_size=sigma_window_size)
        self.metrics = DataQualityMetrics()

        # 센서별 이전 값 (변화율 계산용)
        self.previous_values: Dict[str, Tuple[float, datetime]] = {}

    def filter_outliers(
        self,
        sensor_id: str,
        value: float,
        sigma_multiplier: float = 3.0
    ) -> Tuple[bool, Optional[str]]:
        """
        3-시그마 필터링
        Returns: (is_valid, error_message)
        """
        self.metrics.total_samples += 1

        # 시그마 필터에 값 추가
        self.sigma_filter.add_value(sensor_id, value)

        # 시그마 위반 검사
        is_valid, error_msg = self.sigma_filter.check_sigma_violation(
            sensor_id, value, sigma_multiplier
        )

        if not is_valid:
            self.metrics.outliers_detected += 1
            return False, error_msg

        return True, None

    def check_rate_of_change(
        self,
        sensor_id: str,
        value: float,
        max_change_per_minute: float,
        current_time: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        변화율 검증
        Returns: (is_valid, error_message)
        """
        if sensor_id not in self.previous_values:
            # 첫 번째 값
            self.previous_values[sensor_id] = (value, current_time)
            return True, None

        prev_value, prev_time = self.previous_values[sensor_id]
        time_diff = (current_time - prev_time).total_seconds() / 60.0  # minutes

        if time_diff > 0:
            change = abs(value - prev_value)
            max_allowed = max_change_per_minute * time_diff

            if change > max_allowed:
                self.metrics.rate_violations += 1
                error_msg = f"Rate violation: {change:.2f}/min > {max_change_per_minute:.2f}/min"
                return False, error_msg

        # 값 업데이트
        self.previous_values[sensor_id] = (value, current_time)
        return True, None

    def validate_data_point(
        self,
        sensor_data: SystemSensorData,
        sensor_configs: Dict[str, Dict]
    ) -> Tuple[bool, List[str]]:
        """
        데이터 포인트 전체 검증
        Returns: (is_valid, error_messages)
        """
        errors = []

        # 온도 센서 검증
        temp_sensors = {
            'T1': sensor_data.cooling.T1.value,
            'T2': sensor_data.cooling.T2.value,
            'T3': sensor_data.cooling.T3.value,
            'T4': sensor_data.cooling.T4.value,
            'T5': sensor_data.cooling.T5.value,
            'T6': sensor_data.ventilation.T6.value,
            'T7': sensor_data.ventilation.T7.value
        }

        for sensor_id, value in temp_sensors.items():
            if sensor_id in sensor_configs:
                config = sensor_configs[sensor_id]

                # 3-시그마 필터링
                valid, error = self.filter_outliers(
                    sensor_id,
                    value,
                    config.get('sigma_multiplier', 3.0)
                )
                if not valid:
                    errors.append(f"{sensor_id}: {error}")

                # 변화율 검증
                valid, error = self.check_rate_of_change(
                    sensor_id,
                    value,
                    config.get('max_change_rate', 2.0),
                    sensor_data.timestamp
                )
                if not valid:
                    errors.append(f"{sensor_id}: {error}")

        # 압력 센서 검증
        valid, error = self.filter_outliers('PX1', sensor_data.pressure.PX1.value, 3.0)
        if not valid:
            errors.append(f"PX1: {error}")

        return len(errors) == 0, errors

    def prepare_polynomial_regression_input(
        self,
        historical_data: List[SystemSensorData],
        target_sensor: str = 'T2'
    ) -> Optional[np.ndarray]:
        """
        Polynomial Regression 입력 준비
        - 최근 30분 온도 시퀀스
        - 5-15분 후 온도 예측용
        """
        if len(historical_data) < 30:
            return None

        # 온도 시퀀스 추출
        temperature_sequence = []
        for data in historical_data[-30:]:
            if target_sensor == 'T2':
                temp = data.cooling.T2.value
            elif target_sensor == 'T6':
                temp = data.ventilation.T6.value
            else:
                temp = data.cooling.T2.value

            temperature_sequence.append(temp)

        return np.array(temperature_sequence)

    def prepare_random_forest_input(
        self,
        current_data: SystemSensorData
    ) -> np.ndarray:
        """
        Random Forest 입력 준비
        7개 변수: [온도평균, 시간(hour), 계절, GPS위도, GPS경도, 엔진부하, 외기온도]
        """
        # 평균 온도
        avg_temp = (
            current_data.cooling.T2.value +
            current_data.cooling.T3.value +
            current_data.ventilation.T6.value
        ) / 3.0

        # 시간 (0-23)
        hour = current_data.timestamp.hour

        # 계절 (0: 겨울, 1: 봄, 2: 여름, 3: 가을)
        season_map = {'winter': 0, 'spring': 1, 'summer': 2, 'autumn': 3}
        season = season_map.get(current_data.operating.get_season(), 0)

        # GPS
        gps_lat = current_data.operating.gps_latitude
        gps_lon = current_data.operating.gps_longitude

        # 엔진 부하
        engine_load = current_data.operating.engine_load

        # 외기 온도
        ambient_temp = current_data.ventilation.T7.value

        features = np.array([
            avg_temp,
            hour,
            season,
            gps_lat,
            gps_lon,
            engine_load,
            ambient_temp
        ])

        return features

    def normalize_features(
        self,
        features: np.ndarray,
        feature_ranges: Optional[Dict[int, Tuple[float, float]]] = None
    ) -> np.ndarray:
        """
        특징 정규화 (0-1 범위)
        feature_ranges: {feature_index: (min, max)}
        """
        if feature_ranges is None:
            # 기본 범위
            feature_ranges = {
                0: (20.0, 50.0),   # 평균 온도
                1: (0.0, 23.0),     # 시간
                2: (0.0, 3.0),      # 계절
                3: (-90.0, 90.0),   # GPS 위도
                4: (-180.0, 180.0), # GPS 경도
                5: (0.0, 100.0),    # 엔진 부하
                6: (0.0, 50.0)      # 외기 온도
            }

        normalized = np.zeros_like(features, dtype=float)

        for i, value in enumerate(features):
            if i in feature_ranges:
                min_val, max_val = feature_ranges[i]
                normalized[i] = (value - min_val) / (max_val - min_val)
                normalized[i] = np.clip(normalized[i], 0.0, 1.0)
            else:
                normalized[i] = value

        return normalized

    def create_time_series_windows(
        self,
        data_sequence: List[SystemSensorData],
        window_size: int = 15,  # 15개 포인트 = 30초
        target_sensor: str = 'T2'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        시계열 윈도우 생성 (LSTM 등 사용시)
        Returns: (X, y) - X: 입력 시퀀스, y: 타겟값
        """
        if len(data_sequence) < window_size + 1:
            return np.array([]), np.array([])

        X_windows = []
        y_targets = []

        for i in range(len(data_sequence) - window_size):
            # 윈도우 데이터
            window = data_sequence[i:i+window_size]
            window_temps = []

            for data in window:
                if target_sensor == 'T2':
                    temp = data.cooling.T2.value
                elif target_sensor == 'T6':
                    temp = data.ventilation.T6.value
                else:
                    temp = data.cooling.T2.value

                window_temps.append(temp)

            # 타겟 (다음 값)
            next_data = data_sequence[i + window_size]
            if target_sensor == 'T2':
                target = next_data.cooling.T2.value
            elif target_sensor == 'T6':
                target = next_data.ventilation.T6.value
            else:
                target = next_data.cooling.T2.value

            X_windows.append(window_temps)
            y_targets.append(target)

        return np.array(X_windows), np.array(y_targets)

    def get_statistics(
        self,
        data_sequence: List[SystemSensorData],
        sensor: str = 'T2'
    ) -> Dict:
        """데이터 통계"""
        if len(data_sequence) == 0:
            return {}

        values = []
        for data in data_sequence:
            if sensor == 'T2':
                values.append(data.cooling.T2.value)
            elif sensor == 'T6':
                values.append(data.ventilation.T6.value)
            elif sensor == 'PX1':
                values.append(data.pressure.PX1.value)

        values_array = np.array(values)

        return {
            "sensor": sensor,
            "count": len(values),
            "mean": float(np.mean(values_array)),
            "std": float(np.std(values_array)),
            "min": float(np.min(values_array)),
            "max": float(np.max(values_array)),
            "median": float(np.median(values_array)),
            "p25": float(np.percentile(values_array, 25)),
            "p75": float(np.percentile(values_array, 75))
        }

    def get_quality_metrics(self) -> Dict:
        """품질 지표"""
        return {
            "total_samples": self.metrics.total_samples,
            "outliers_detected": self.metrics.outliers_detected,
            "outliers_filtered": self.metrics.outliers_filtered,
            "rate_violations": self.metrics.rate_violations,
            "interpolations": self.metrics.interpolations,
            "quality_rate": f"{self.metrics.get_quality_rate():.2f}%"
        }

    def reset_metrics(self) -> None:
        """지표 리셋"""
        self.metrics = DataQualityMetrics()


def create_data_preprocessor(sigma_window_size: int = 30) -> DataPreprocessor:
    """데이터 전처리기 생성"""
    return DataPreprocessor(sigma_window_size)
