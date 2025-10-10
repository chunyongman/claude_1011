"""
센서 이상 감지 시스템
Isolation Forest 기반 이상 패턴 감지
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from enum import Enum
import numpy as np


class SensorReliability(Enum):
    """센서 신뢰도"""
    NORMAL = "normal"  # 정상
    ABNORMAL = "abnormal"  # 이상


class AnomalyType(Enum):
    """이상 타입"""
    HOT_SPOT = "hot_spot"  # Hot Spot
    PRESSURE_ABNORMAL = "pressure_abnormal"  # 압력 이상
    RAPID_TEMP_CHANGE = "rapid_temp_change"  # 급격한 온도 변화
    SENSOR_DRIFT = "sensor_drift"  # 센서 드리프트
    OUT_OF_RANGE = "out_of_range"  # 범위 벗어남


@dataclass
class SensorReading:
    """센서 읽기값"""
    sensor_id: str
    timestamp: datetime
    value: float
    unit: str


@dataclass
class SensorAnomaly:
    """센서 이상"""
    timestamp: datetime
    sensor_id: str
    anomaly_type: AnomalyType
    value: float
    expected_range: Tuple[float, float]
    deviation_score: float  # 0-1 (높을수록 심각)
    description: str


@dataclass
class SensorStatus:
    """센서 상태"""
    sensor_id: str
    reliability: SensorReliability
    recent_anomalies: List[SensorAnomaly]
    failure_count: int
    last_normal_time: Optional[datetime]


class IsolationForestDetector:
    """
    Isolation Forest 기반 이상 감지

    scikit-learn 없이 간단한 구현
    """

    def __init__(self, n_trees: int = 10, sample_size: int = 50):
        """
        Args:
            n_trees: 트리 개수
            sample_size: 샘플 크기
        """
        self.n_trees = n_trees
        self.sample_size = sample_size
        self.trees: List[Dict] = []
        self.is_trained = False

    def fit(self, X: np.ndarray):
        """
        학습

        Args:
            X: 학습 데이터 (n_samples, n_features)
        """
        n_samples = X.shape[0]
        self.trees = []

        for _ in range(self.n_trees):
            # 랜덤 샘플
            indices = np.random.choice(n_samples, size=min(self.sample_size, n_samples), replace=False)
            sample = X[indices]

            # 간단한 트리 구조 (범위 기반)
            tree = {
                'min': np.min(sample, axis=0),
                'max': np.max(sample, axis=0),
                'mean': np.mean(sample, axis=0),
                'std': np.std(sample, axis=0)
            }
            self.trees.append(tree)

        self.is_trained = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        예측

        Args:
            X: 테스트 데이터 (n_samples, n_features)

        Returns:
            이상 점수 (0-1, 높을수록 이상)
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained")

        scores = []

        for x in X:
            # 각 트리에서 이상 점수 계산
            tree_scores = []
            for tree in self.trees:
                # 범위 벗어남 정도 + 표준편차 기준
                range_score = 0.0
                std_score = 0.0

                for i in range(len(x)):
                    # 범위 체크
                    if x[i] < tree['min'][i] or x[i] > tree['max'][i]:
                        range_score += 1.0

                    # 표준편차 기준 (3-sigma)
                    deviation = abs(x[i] - tree['mean'][i]) / (tree['std'][i] + 1e-8)
                    if deviation > 3:
                        std_score += deviation / 10.0

                tree_score = min(1.0, (range_score + std_score) / len(x))
                tree_scores.append(tree_score)

            # 평균 이상 점수
            scores.append(np.mean(tree_scores))

        return np.array(scores)


class SensorAnomalyDetector:
    """
    센서 이상 감지 시스템

    - Isolation Forest 기반
    - Hot Spot, 압력 이상, 급격한 온도 변화 감지
    """

    def __init__(self):
        """초기화"""
        # Isolation Forest 모델
        self.isolation_forest = IsolationForestDetector(n_trees=10, sample_size=50)

        # 센서 범위 정의
        self.sensor_ranges = {
            'T1': (15.0, 40.0),  # SW Inlet
            'T2': (20.0, 50.0),  # No.1 Cooler SW Outlet
            'T3': (20.0, 50.0),  # No.2 Cooler SW Outlet
            'T4': (30.0, 45.0),  # FW Inlet
            'T5': (30.0, 40.0),  # FW Outlet
            'T6': (35.0, 55.0),  # E/R Temperature
            'T7': (20.0, 45.0),  # Outside Air
            'PX1': (0.5, 3.0)    # LT Cooler SW Outlet Pressure
        }

        # 센서 상태
        self.sensor_status: Dict[str, SensorStatus] = {
            sensor_id: SensorStatus(
                sensor_id=sensor_id,
                reliability=SensorReliability.NORMAL,
                recent_anomalies=[],
                failure_count=0,
                last_normal_time=datetime.now()
            )
            for sensor_id in self.sensor_ranges.keys()
        }

        # 히스토리 (학습용)
        self.sensor_history: Dict[str, List[float]] = {
            sensor_id: [] for sensor_id in self.sensor_ranges.keys()
        }

        # 이상 히스토리
        self.anomaly_history: List[SensorAnomaly] = []

    def add_sensor_reading(self, sensor_id: str, value: float):
        """센서 읽기값 추가 (학습 데이터)"""
        if sensor_id not in self.sensor_history:
            return

        self.sensor_history[sensor_id].append(value)

        # 히스토리 크기 제한 (최근 500개)
        if len(self.sensor_history[sensor_id]) > 500:
            self.sensor_history[sensor_id] = self.sensor_history[sensor_id][-500:]

    def train_model(self):
        """Isolation Forest 모델 학습"""
        # 모든 센서 데이터 결합
        all_data = []

        min_length = min(len(history) for history in self.sensor_history.values() if history)
        if min_length < 50:
            raise ValueError(f"Insufficient training data: {min_length} samples (minimum 50)")

        for i in range(min_length):
            sample = [
                self.sensor_history['T1'][i],
                self.sensor_history['T2'][i],
                self.sensor_history['T3'][i],
                self.sensor_history['T4'][i],
                self.sensor_history['T5'][i],
                self.sensor_history['T6'][i],
                self.sensor_history['T7'][i],
                self.sensor_history['PX1'][i]
            ]
            all_data.append(sample)

        X = np.array(all_data)
        self.isolation_forest.fit(X)

    def detect_anomalies(self, sensor_readings: Dict[str, float]) -> List[SensorAnomaly]:
        """
        이상 감지

        Args:
            sensor_readings: 센서 읽기값 {'T1': 28.0, 'T2': 32.0, ...}

        Returns:
            감지된 이상 목록
        """
        anomalies = []
        timestamp = datetime.now()

        # 1. 범위 체크 (Out of Range)
        for sensor_id, value in sensor_readings.items():
            if sensor_id not in self.sensor_ranges:
                continue

            min_val, max_val = self.sensor_ranges[sensor_id]

            if value < min_val or value > max_val:
                anomaly = SensorAnomaly(
                    timestamp=timestamp,
                    sensor_id=sensor_id,
                    anomaly_type=AnomalyType.OUT_OF_RANGE,
                    value=value,
                    expected_range=(min_val, max_val),
                    deviation_score=1.0,
                    description=f"{sensor_id} 값이 정상 범위를 벗어남: {value:.1f} (범위: {min_val}-{max_val})"
                )
                anomalies.append(anomaly)
                self._update_sensor_status(sensor_id, anomaly)

        # 2. Hot Spot 감지 (T2, T3 vs T1)
        if 'T1' in sensor_readings and 'T2' in sensor_readings and 'T3' in sensor_readings:
            t1 = sensor_readings['T1']
            t2 = sensor_readings['T2']
            t3 = sensor_readings['T3']

            # Hot Spot: T2 또는 T3가 T1 대비 과도하게 높음
            if t2 > t1 + 15 or t3 > t1 + 15:
                hotspot_sensor = 'T2' if t2 > t3 else 'T3'
                anomaly = SensorAnomaly(
                    timestamp=timestamp,
                    sensor_id=hotspot_sensor,
                    anomaly_type=AnomalyType.HOT_SPOT,
                    value=sensor_readings[hotspot_sensor],
                    expected_range=(t1, t1 + 15),
                    deviation_score=0.8,
                    description=f"Hot Spot 감지: {hotspot_sensor}={sensor_readings[hotspot_sensor]:.1f}°C (T1+15°C 초과)"
                )
                anomalies.append(anomaly)
                self._update_sensor_status(hotspot_sensor, anomaly)

        # 3. 압력 이상 (PX1 < 1.0bar)
        if 'PX1' in sensor_readings:
            px1 = sensor_readings['PX1']
            if px1 < 1.0:
                anomaly = SensorAnomaly(
                    timestamp=timestamp,
                    sensor_id='PX1',
                    anomaly_type=AnomalyType.PRESSURE_ABNORMAL,
                    value=px1,
                    expected_range=(1.0, 3.0),
                    deviation_score=0.9,
                    description=f"압력 이상: PX1={px1:.2f}bar (최소 1.0bar 필요)"
                )
                anomalies.append(anomaly)
                self._update_sensor_status('PX1', anomaly)

        # 4. 급격한 온도 변화 (히스토리 기반)
        for sensor_id in ['T5', 'T6']:
            if sensor_id in sensor_readings and sensor_id in self.sensor_history:
                if len(self.sensor_history[sensor_id]) >= 10:
                    recent_avg = np.mean(self.sensor_history[sensor_id][-10:])
                    current = sensor_readings[sensor_id]
                    change = abs(current - recent_avg)

                    # 급격한 변화: 5분(10샘플) 평균 대비 3°C 이상
                    if change > 3.0:
                        anomaly = SensorAnomaly(
                            timestamp=timestamp,
                            sensor_id=sensor_id,
                            anomaly_type=AnomalyType.RAPID_TEMP_CHANGE,
                            value=current,
                            expected_range=(recent_avg - 3, recent_avg + 3),
                            deviation_score=0.7,
                            description=f"급격한 온도 변화: {sensor_id} {recent_avg:.1f}°C → {current:.1f}°C"
                        )
                        anomalies.append(anomaly)
                        self._update_sensor_status(sensor_id, anomaly)

        # 5. Isolation Forest 기반 이상 (모델 학습 후)
        if self.isolation_forest.is_trained:
            sample = np.array([[
                sensor_readings.get('T1', 0),
                sensor_readings.get('T2', 0),
                sensor_readings.get('T3', 0),
                sensor_readings.get('T4', 0),
                sensor_readings.get('T5', 0),
                sensor_readings.get('T6', 0),
                sensor_readings.get('T7', 0),
                sensor_readings.get('PX1', 0)
            ]])

            scores = self.isolation_forest.predict(sample)
            if scores[0] > 0.7:  # 임계값
                anomaly = SensorAnomaly(
                    timestamp=timestamp,
                    sensor_id="SYSTEM",
                    anomaly_type=AnomalyType.SENSOR_DRIFT,
                    value=scores[0],
                    expected_range=(0.0, 0.7),
                    deviation_score=scores[0],
                    description=f"센서 패턴 이상 감지 (Isolation Forest 점수: {scores[0]:.2f})"
                )
                anomalies.append(anomaly)

        # 히스토리 저장
        self.anomaly_history.extend(anomalies)
        if len(self.anomaly_history) > 1000:
            self.anomaly_history = self.anomaly_history[-1000:]

        return anomalies

    def _update_sensor_status(self, sensor_id: str, anomaly: SensorAnomaly):
        """센서 상태 업데이트"""
        if sensor_id not in self.sensor_status:
            return

        status = self.sensor_status[sensor_id]
        status.recent_anomalies.append(anomaly)
        status.failure_count += 1

        # 최근 이상 크기 제한 (최근 10개)
        if len(status.recent_anomalies) > 10:
            status.recent_anomalies = status.recent_anomalies[-10:]

        # 신뢰도 판정 (최근 10개 중 5개 이상 이상 = ABNORMAL)
        if len(status.recent_anomalies) >= 5:
            status.reliability = SensorReliability.ABNORMAL
        else:
            status.reliability = SensorReliability.NORMAL
            status.last_normal_time = datetime.now()

    def get_sensor_backup(self, failed_sensor: str) -> Optional[str]:
        """
        센서 고장시 백업 센서 반환

        Returns:
            백업 센서 ID or None
        """
        # T2 ↔ T3 (서로 백업 가능)
        if failed_sensor == 'T2':
            return 'T3'
        elif failed_sensor == 'T3':
            return 'T2'

        # 다른 센서는 백업 불가
        return None

    def get_sensor_status_summary(self) -> Dict:
        """센서 상태 요약"""
        summary = {
            'total_sensors': len(self.sensor_status),
            'normal': 0,
            'abnormal': 0,
            'abnormal_sensors': [],
            'total_anomalies': len(self.anomaly_history)
        }

        for sensor_id, status in self.sensor_status.items():
            if status.reliability == SensorReliability.NORMAL:
                summary['normal'] += 1
            else:
                summary['abnormal'] += 1
                summary['abnormal_sensors'].append(sensor_id)

        return summary
