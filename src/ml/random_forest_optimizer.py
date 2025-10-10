"""
Random Forest 최적화 모델
온도, 시간, 계절, GPS, 엔진부하 등을 입력받아 최적 주파수와 운전대수 출력
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import numpy as np
from datetime import datetime
import pickle
import os


@dataclass
class OptimizationInput:
    """최적화 입력 데이터"""
    # 온도 정보
    t1_seawater: float
    t5_fw_outlet: float
    t6_er_temp: float
    t7_outside_air: float

    # 시간 정보
    hour: int  # 0-23
    season: int  # 0-3 (봄/여름/가을/겨울)

    # 위치 정보
    gps_latitude: float
    gps_longitude: float

    # 운항 정보
    ship_speed_knots: float
    engine_load_percent: float

    def to_feature_vector(self) -> np.ndarray:
        """특징 벡터로 변환 (10개 특징)"""
        return np.array([
            self.t1_seawater,
            self.t5_fw_outlet,
            self.t6_er_temp,
            self.t7_outside_air,
            self.hour,
            self.season,
            self.gps_latitude,
            self.gps_longitude,
            self.ship_speed_knots,
            self.engine_load_percent
        ])


@dataclass
class OptimizationOutput:
    """최적화 출력 결과"""
    # 펌프 제어
    pump_frequency_hz: float
    pump_count: int

    # 팬 제어
    fan_frequency_hz: float
    fan_count: int

    # 예상 성능
    expected_t5: float
    expected_t6: float
    expected_power_kw: float
    expected_savings_percent: float

    # 모델 신뢰도
    confidence: float


class RandomForestOptimizer:
    """
    Random Forest 기반 최적화 모델

    모델 크기: ~1.5MB
    7개 입력 변수 → 최적 주파수 + 운전대수
    비선형 관계 학습
    """

    def __init__(self, n_trees: int = 50, max_depth: int = 10):
        """
        Args:
            n_trees: 트리 개수 (기본값: 50)
            max_depth: 최대 깊이 (기본값: 10)
        """
        self.n_trees = n_trees
        self.max_depth = max_depth

        # 트리 저장 (간단한 구현)
        self.trees_pump_freq: List[Dict] = []
        self.trees_pump_count: List[Dict] = []
        self.trees_fan_freq: List[Dict] = []
        self.trees_fan_count: List[Dict] = []

        # 정규화 파라미터
        self.feature_mean: Optional[np.ndarray] = None
        self.feature_std: Optional[np.ndarray] = None

        # 학습 메타데이터
        self.training_samples: int = 0
        self.last_training_time: Optional[datetime] = None
        self.prediction_accuracy: float = 0.0

        self.is_trained = False

    def _build_simple_tree(self, X: np.ndarray, y: np.ndarray, depth: int = 0) -> Dict:
        """
        단순 결정 트리 구축 (재귀)

        실제 sklearn의 Random Forest는 C로 최적화되어 있지만,
        여기서는 Xavier NX에서 추론 가능한 단순 구조 사용
        """
        n_samples, n_features = X.shape

        # 종료 조건
        if depth >= self.max_depth or n_samples < 5:
            return {'type': 'leaf', 'value': np.mean(y)}

        # 최적 분할 찾기 (간단한 그리디 탐색)
        best_feature = None
        best_threshold = None
        best_gain = 0.0

        current_variance = np.var(y)

        for feature_idx in range(n_features):
            # 중간값을 threshold로 사용
            threshold = np.median(X[:, feature_idx])

            left_mask = X[:, feature_idx] <= threshold
            right_mask = ~left_mask

            if np.sum(left_mask) < 2 or np.sum(right_mask) < 2:
                continue

            # Information Gain 계산
            left_var = np.var(y[left_mask])
            right_var = np.var(y[right_mask])

            weighted_var = (np.sum(left_mask) * left_var + np.sum(right_mask) * right_var) / n_samples
            gain = current_variance - weighted_var

            if gain > best_gain:
                best_gain = gain
                best_feature = feature_idx
                best_threshold = threshold

        # 분할이 유효하지 않으면 leaf
        if best_feature is None:
            return {'type': 'leaf', 'value': np.mean(y)}

        # 분할
        left_mask = X[:, best_feature] <= best_threshold
        right_mask = ~left_mask

        return {
            'type': 'node',
            'feature': best_feature,
            'threshold': best_threshold,
            'left': self._build_simple_tree(X[left_mask], y[left_mask], depth + 1),
            'right': self._build_simple_tree(X[right_mask], y[right_mask], depth + 1)
        }

    def _predict_tree(self, tree: Dict, x: np.ndarray) -> float:
        """단일 트리 예측"""
        if tree['type'] == 'leaf':
            return tree['value']

        if x[tree['feature']] <= tree['threshold']:
            return self._predict_tree(tree['left'], x)
        else:
            return self._predict_tree(tree['right'], x)

    def train(self, training_data: List[Tuple[OptimizationInput, OptimizationOutput]]):
        """
        모델 학습

        Args:
            training_data: [(입력, 출력)] 리스트
        """
        if len(training_data) < 100:
            raise ValueError(f"Insufficient training data: {len(training_data)} samples (minimum 100)")

        # 데이터 준비
        X_list = []
        y_pump_freq, y_pump_count = [], []
        y_fan_freq, y_fan_count = [], []

        for input_data, output_data in training_data:
            X_list.append(input_data.to_feature_vector())
            y_pump_freq.append(output_data.pump_frequency_hz)
            y_pump_count.append(output_data.pump_count)
            y_fan_freq.append(output_data.fan_frequency_hz)
            y_fan_count.append(output_data.fan_count)

        X = np.array(X_list)
        y_pump_freq = np.array(y_pump_freq)
        y_pump_count = np.array(y_pump_count)
        y_fan_freq = np.array(y_fan_freq)
        y_fan_count = np.array(y_fan_count)

        # 정규화
        self.feature_mean = np.mean(X, axis=0)
        self.feature_std = np.std(X, axis=0) + 1e-8
        X_norm = (X - self.feature_mean) / self.feature_std

        # Random Forest 학습 (각 트리는 랜덤 샘플로 학습)
        n_samples = X_norm.shape[0]

        self.trees_pump_freq = []
        self.trees_pump_count = []
        self.trees_fan_freq = []
        self.trees_fan_count = []

        for i in range(self.n_trees):
            # Bootstrap sampling
            indices = np.random.choice(n_samples, size=n_samples, replace=True)
            X_sample = X_norm[indices]

            # 각 목표 변수별 트리 학습
            self.trees_pump_freq.append(
                self._build_simple_tree(X_sample, y_pump_freq[indices])
            )
            self.trees_pump_count.append(
                self._build_simple_tree(X_sample, y_pump_count[indices])
            )
            self.trees_fan_freq.append(
                self._build_simple_tree(X_sample, y_fan_freq[indices])
            )
            self.trees_fan_count.append(
                self._build_simple_tree(X_sample, y_fan_count[indices])
            )

        # 메타데이터
        self.training_samples = len(training_data)
        self.last_training_time = datetime.now()
        self.is_trained = True

        # 정확도 평가
        predictions = [self.predict(inp) for inp, _ in training_data]
        freq_errors = []
        for pred, (_, actual) in zip(predictions, training_data):
            freq_errors.extend([
                abs(pred.pump_frequency_hz - actual.pump_frequency_hz),
                abs(pred.fan_frequency_hz - actual.fan_frequency_hz)
            ])

        self.prediction_accuracy = 100.0 * (1.0 - np.mean(freq_errors) / 20.0)

    def predict(self, input_data: OptimizationInput) -> OptimizationOutput:
        """최적화 예측"""
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        # 특징 벡터
        x = input_data.to_feature_vector()
        x_norm = (x - self.feature_mean) / self.feature_std

        # 각 트리의 예측을 평균 (Random Forest)
        pump_freq_preds = [self._predict_tree(tree, x_norm) for tree in self.trees_pump_freq]
        pump_count_preds = [self._predict_tree(tree, x_norm) for tree in self.trees_pump_count]
        fan_freq_preds = [self._predict_tree(tree, x_norm) for tree in self.trees_fan_freq]
        fan_count_preds = [self._predict_tree(tree, x_norm) for tree in self.trees_fan_count]

        pump_freq = np.mean(pump_freq_preds)
        pump_count = int(round(np.mean(pump_count_preds)))
        fan_freq = np.mean(fan_freq_preds)
        fan_count = int(round(np.mean(fan_count_preds)))

        # 범위 제한
        pump_freq = np.clip(pump_freq, 40.0, 60.0)
        pump_count = np.clip(pump_count, 1, 3)
        fan_freq = np.clip(fan_freq, 35.0, 60.0)
        fan_count = np.clip(fan_count, 2, 4)

        # 예상 성능 계산 (간단한 추정)
        expected_t5 = 35.0 - (60.0 - pump_freq) * 0.1
        expected_t6 = 43.0 - (60.0 - fan_freq) * 0.15

        # 전력 계산 (Affinity Laws)
        pump_power = pump_count * 132.0 * ((pump_freq / 60.0) ** 3)
        fan_power = fan_count * 54.3 * ((fan_freq / 60.0) ** 3)
        total_power = pump_power + fan_power

        # 절감률 (60Hz 기준 대비)
        baseline_power = 3 * 132.0 + 4 * 54.3
        savings = (1.0 - total_power / baseline_power) * 100.0

        # 신뢰도
        confidence = min(1.0, self.prediction_accuracy / 100.0)

        return OptimizationOutput(
            pump_frequency_hz=pump_freq,
            pump_count=pump_count,
            fan_frequency_hz=fan_freq,
            fan_count=fan_count,
            expected_t5=expected_t5,
            expected_t6=expected_t6,
            expected_power_kw=total_power,
            expected_savings_percent=savings,
            confidence=confidence
        )

    def save_model(self, filepath: str):
        """모델 저장 (~1.5MB)"""
        model_data = {
            'n_trees': self.n_trees,
            'max_depth': self.max_depth,
            'trees_pump_freq': self.trees_pump_freq,
            'trees_pump_count': self.trees_pump_count,
            'trees_fan_freq': self.trees_fan_freq,
            'trees_fan_count': self.trees_fan_count,
            'feature_mean': self.feature_mean,
            'feature_std': self.feature_std,
            'training_samples': self.training_samples,
            'last_training_time': self.last_training_time,
            'prediction_accuracy': self.prediction_accuracy
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

    def load_model(self, filepath: str):
        """모델 로드"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")

        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.n_trees = model_data['n_trees']
        self.max_depth = model_data['max_depth']
        self.trees_pump_freq = model_data['trees_pump_freq']
        self.trees_pump_count = model_data['trees_pump_count']
        self.trees_fan_freq = model_data['trees_fan_freq']
        self.trees_fan_count = model_data['trees_fan_count']
        self.feature_mean = model_data['feature_mean']
        self.feature_std = model_data['feature_std']
        self.training_samples = model_data['training_samples']
        self.last_training_time = model_data['last_training_time']
        self.prediction_accuracy = model_data['prediction_accuracy']

        self.is_trained = True

    def get_model_info(self) -> Dict:
        """모델 정보"""
        return {
            'n_trees': self.n_trees,
            'max_depth': self.max_depth,
            'is_trained': self.is_trained,
            'training_samples': self.training_samples,
            'last_training_time': self.last_training_time,
            'prediction_accuracy': f"{self.prediction_accuracy:.1f}%",
            'model_size_mb': self._estimate_model_size()
        }

    def _estimate_model_size(self) -> float:
        """모델 크기 추정 (MB)"""
        if not self.is_trained:
            return 0.0

        # 트리 구조 크기 추정 (대략적)
        # 각 트리당 ~7KB (최대 깊이 10, 약 1024 노드)
        total_bytes = self.n_trees * 4 * 7 * 1024  # 4개 목표 변수

        # 정규화 파라미터
        total_bytes += self.feature_mean.nbytes + self.feature_std.nbytes

        return total_bytes / (1024 * 1024)
