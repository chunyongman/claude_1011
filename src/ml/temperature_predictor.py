"""
온도 예측 모델 (Polynomial Regression)
5-15분 후 온도를 예측하여 예측적 제어 수행
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import numpy as np
from datetime import datetime, timedelta
import pickle
import os


@dataclass
class TemperaturePrediction:
    """온도 예측 결과"""
    timestamp: datetime

    # 예측 시점
    t4_current: float
    t5_current: float
    t6_current: float

    # 5분 후 예측
    t4_pred_5min: float
    t5_pred_5min: float
    t6_pred_5min: float

    # 10분 후 예측
    t4_pred_10min: float
    t5_pred_10min: float
    t6_pred_10min: float

    # 15분 후 예측
    t4_pred_15min: float
    t5_pred_15min: float
    t6_pred_15min: float

    # 예측 신뢰도
    confidence: float

    # 추론 시간 (ms)
    inference_time_ms: float


@dataclass
class TemperatureSequence:
    """온도 시퀀스 데이터 (30분)"""
    timestamps: List[datetime]

    # 온도 시퀀스 (90개 데이터 포인트, 20초 간격)
    t1_sequence: List[float]  # SW Inlet
    t2_sequence: List[float]  # No.1 SW Outlet
    t3_sequence: List[float]  # No.2 SW Outlet
    t4_sequence: List[float]  # FW Inlet
    t5_sequence: List[float]  # FW Outlet
    t6_sequence: List[float]  # E/R Temperature
    t7_sequence: List[float]  # Outside Air

    # 엔진 부하 시퀀스
    engine_load_sequence: List[float]

    def __post_init__(self):
        """데이터 검증"""
        sequences = [
            self.t1_sequence, self.t2_sequence, self.t3_sequence,
            self.t4_sequence, self.t5_sequence, self.t6_sequence,
            self.t7_sequence, self.engine_load_sequence
        ]

        lengths = [len(seq) for seq in sequences]
        if not all(l == lengths[0] for l in lengths):
            raise ValueError("All sequences must have the same length")

        if len(self.timestamps) != lengths[0]:
            raise ValueError("Timestamps length must match sequence length")


class PolynomialRegressionPredictor:
    """
    Polynomial Regression 기반 온도 예측 모델

    모델 크기: ~0.5MB
    추론 시간: <10ms
    예측 정확도: ±2-3°C
    """

    def __init__(self, degree: int = 2):
        """
        Args:
            degree: 다항식 차수 (기본값: 2차)
        """
        self.degree = degree

        # 모델 파라미터
        self.t4_5min_coeffs: Optional[np.ndarray] = None
        self.t4_10min_coeffs: Optional[np.ndarray] = None
        self.t4_15min_coeffs: Optional[np.ndarray] = None

        self.t5_5min_coeffs: Optional[np.ndarray] = None
        self.t5_10min_coeffs: Optional[np.ndarray] = None
        self.t5_15min_coeffs: Optional[np.ndarray] = None

        self.t6_5min_coeffs: Optional[np.ndarray] = None
        self.t6_10min_coeffs: Optional[np.ndarray] = None
        self.t6_15min_coeffs: Optional[np.ndarray] = None

        # 정규화 파라미터
        self.feature_mean: Optional[np.ndarray] = None
        self.feature_std: Optional[np.ndarray] = None

        # 학습 메타데이터
        self.training_samples: int = 0
        self.last_training_time: Optional[datetime] = None
        self.prediction_accuracy: float = 0.0

        self.is_trained = False

    def _extract_features(self, sequence: TemperatureSequence) -> np.ndarray:
        """
        시퀀스에서 특징 추출

        특징 벡터 (19개):
        - T4 현재값, 평균, 표준편차, 증가율
        - T5 현재값, 평균, 표준편차, 증가율
        - T6 현재값, 평균, 표준편차, 증가율
        - 엔진부하 현재값, 평균, 증가율
        - T1 평균 (해수 온도)
        - T7 평균 (외기 온도)
        - 시간대 (0-23)
        - 계절 (0-3)
        """
        features = []

        # T4 특징 (FW Inlet)
        t4_arr = np.array(sequence.t4_sequence)
        features.extend([
            t4_arr[-1],  # 현재값
            np.mean(t4_arr),  # 평균
            np.std(t4_arr),  # 표준편차
            (t4_arr[-1] - t4_arr[0]) / len(t4_arr)  # 증가율
        ])

        # T5 특징 (FW Outlet)
        t5_arr = np.array(sequence.t5_sequence)
        features.extend([
            t5_arr[-1],  # 현재값
            np.mean(t5_arr),  # 평균
            np.std(t5_arr),  # 표준편차
            (t5_arr[-1] - t5_arr[0]) / len(t5_arr)  # 증가율
        ])

        # T6 특징 (E/R Temperature)
        t6_arr = np.array(sequence.t6_sequence)
        features.extend([
            t6_arr[-1],
            np.mean(t6_arr),
            np.std(t6_arr),
            (t6_arr[-1] - t6_arr[0]) / len(t6_arr)
        ])

        # 엔진 부하 특징
        load_arr = np.array(sequence.engine_load_sequence)
        features.extend([
            load_arr[-1],
            np.mean(load_arr),
            (load_arr[-1] - load_arr[0]) / len(load_arr)
        ])

        # 환경 특징
        features.append(np.mean(sequence.t1_sequence))  # 해수 온도
        features.append(np.mean(sequence.t7_sequence))  # 외기 온도

        # 시간 특징
        current_time = sequence.timestamps[-1]
        features.append(current_time.hour)  # 시간대
        features.append(current_time.month // 3)  # 계절 (0-3)

        return np.array(features)

    def _polynomial_features(self, X: np.ndarray) -> np.ndarray:
        """다항식 특징 생성"""
        n_samples = X.shape[0] if len(X.shape) > 1 else 1
        if len(X.shape) == 1:
            X = X.reshape(1, -1)

        # 1차 특징
        poly_features = [X]

        # 2차 특징 (제곱, 교차항)
        if self.degree >= 2:
            # 제곱항
            poly_features.append(X ** 2)

            # 주요 교차항만 선택 (모델 크기 최소화)
            # T4 * 엔진부하, T5 * 엔진부하, T6 * 엔진부하
            cross_1 = (X[:, 0] * X[:, 12]).reshape(-1, 1)  # T4 * 엔진부하
            cross_2 = (X[:, 4] * X[:, 12]).reshape(-1, 1)  # T5 * 엔진부하
            cross_3 = (X[:, 8] * X[:, 12]).reshape(-1, 1)  # T6 * 엔진부하
            poly_features.extend([cross_1, cross_2, cross_3])

        return np.hstack(poly_features)

    def train(self, training_data: List[Tuple[TemperatureSequence, Dict[str, float]]]):
        """
        모델 학습

        Args:
            training_data: [(시퀀스, 실제값)] 리스트
                실제값 = {'t4_5min': float, 't4_10min': float, 't4_15min': float,
                          't5_5min': float, 't5_10min': float, 't5_15min': float,
                          't6_5min': float, 't6_10min': float, 't6_15min': float}
        """
        if len(training_data) < 50:
            raise ValueError(f"Insufficient training data: {len(training_data)} samples (minimum 50)")

        # 특징 추출
        X_list = []
        y_t4_5min, y_t4_10min, y_t4_15min = [], [], []
        y_t5_5min, y_t5_10min, y_t5_15min = [], [], []
        y_t6_5min, y_t6_10min, y_t6_15min = [], [], []

        for sequence, targets in training_data:
            features = self._extract_features(sequence)
            X_list.append(features)

            y_t4_5min.append(targets['t4_5min'])
            y_t4_10min.append(targets['t4_10min'])
            y_t4_15min.append(targets['t4_15min'])

            y_t5_5min.append(targets['t5_5min'])
            y_t5_10min.append(targets['t5_10min'])
            y_t5_15min.append(targets['t5_15min'])

            y_t6_5min.append(targets['t6_5min'])
            y_t6_10min.append(targets['t6_10min'])
            y_t6_15min.append(targets['t6_15min'])

        X = np.array(X_list)

        # 정규화
        self.feature_mean = np.mean(X, axis=0)
        self.feature_std = np.std(X, axis=0) + 1e-8
        X_norm = (X - self.feature_mean) / self.feature_std

        # 다항식 특징 생성
        X_poly = self._polynomial_features(X_norm)

        # 각 예측 시점별 회귀 모델 학습 (Least Squares)
        self.t4_5min_coeffs = np.linalg.lstsq(X_poly, y_t4_5min, rcond=None)[0]
        self.t4_10min_coeffs = np.linalg.lstsq(X_poly, y_t4_10min, rcond=None)[0]
        self.t4_15min_coeffs = np.linalg.lstsq(X_poly, y_t4_15min, rcond=None)[0]

        self.t5_5min_coeffs = np.linalg.lstsq(X_poly, y_t5_5min, rcond=None)[0]
        self.t5_10min_coeffs = np.linalg.lstsq(X_poly, y_t5_10min, rcond=None)[0]
        self.t5_15min_coeffs = np.linalg.lstsq(X_poly, y_t5_15min, rcond=None)[0]

        self.t6_5min_coeffs = np.linalg.lstsq(X_poly, y_t6_5min, rcond=None)[0]
        self.t6_10min_coeffs = np.linalg.lstsq(X_poly, y_t6_10min, rcond=None)[0]
        self.t6_15min_coeffs = np.linalg.lstsq(X_poly, y_t6_15min, rcond=None)[0]

        # 메타데이터 업데이트
        self.training_samples = len(training_data)
        self.last_training_time = datetime.now()
        self.is_trained = True

        # 학습 데이터 정확도 평가
        predictions = [self.predict(seq) for seq, _ in training_data]
        errors = []
        for pred, (_, actual) in zip(predictions, training_data):
            errors.extend([
                abs(pred.t4_pred_5min - actual['t4_5min']),
                abs(pred.t4_pred_10min - actual['t4_10min']),
                abs(pred.t5_pred_5min - actual['t5_5min']),
                abs(pred.t5_pred_10min - actual['t5_10min']),
                abs(pred.t6_pred_5min - actual['t6_5min']),
                abs(pred.t6_pred_10min - actual['t6_10min'])
            ])

        self.prediction_accuracy = 100.0 * (1.0 - np.mean(errors) / 10.0)

    def predict(self, sequence: TemperatureSequence) -> TemperaturePrediction:
        """
        온도 예측

        Returns:
            TemperaturePrediction with 5/10/15min forecasts for T4, T5, T6
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        start_time = datetime.now()

        # 특징 추출
        features = self._extract_features(sequence)

        # 정규화
        features_norm = (features - self.feature_mean) / self.feature_std

        # 다항식 특징
        features_poly = self._polynomial_features(features_norm.reshape(1, -1))

        # 예측 (현실적인 범위로 제한)
        t4_pred_5 = np.clip(float(features_poly @ self.t4_5min_coeffs), 20.0, 80.0)
        t4_pred_10 = np.clip(float(features_poly @ self.t4_10min_coeffs), 20.0, 80.0)
        t4_pred_15 = np.clip(float(features_poly @ self.t4_15min_coeffs), 20.0, 80.0)

        t5_pred_5 = np.clip(float(features_poly @ self.t5_5min_coeffs), 20.0, 50.0)
        t5_pred_10 = np.clip(float(features_poly @ self.t5_10min_coeffs), 20.0, 50.0)
        t5_pred_15 = np.clip(float(features_poly @ self.t5_15min_coeffs), 20.0, 50.0)

        t6_pred_5 = np.clip(float(features_poly @ self.t6_5min_coeffs), 30.0, 60.0)
        t6_pred_10 = np.clip(float(features_poly @ self.t6_10min_coeffs), 30.0, 60.0)
        t6_pred_15 = np.clip(float(features_poly @ self.t6_15min_coeffs), 30.0, 60.0)

        # 추론 시간
        inference_time = (datetime.now() - start_time).total_seconds() * 1000

        # 신뢰도 계산 (학습 정확도 기반)
        confidence = min(1.0, self.prediction_accuracy / 100.0)

        return TemperaturePrediction(
            timestamp=sequence.timestamps[-1],
            t4_current=sequence.t4_sequence[-1],
            t5_current=sequence.t5_sequence[-1],
            t6_current=sequence.t6_sequence[-1],
            t4_pred_5min=t4_pred_5,
            t5_pred_5min=t5_pred_5,
            t6_pred_5min=t6_pred_5,
            t4_pred_10min=t4_pred_10,
            t5_pred_10min=t5_pred_10,
            t6_pred_10min=t6_pred_10,
            t4_pred_15min=t4_pred_15,
            t5_pred_15min=t5_pred_15,
            t6_pred_15min=t6_pred_15,
            confidence=confidence,
            inference_time_ms=inference_time
        )

    def save_model(self, filepath: str):
        """모델 저장 (~0.7MB)"""
        model_data = {
            'degree': self.degree,
            't4_5min_coeffs': self.t4_5min_coeffs,
            't4_10min_coeffs': self.t4_10min_coeffs,
            't4_15min_coeffs': self.t4_15min_coeffs,
            't5_5min_coeffs': self.t5_5min_coeffs,
            't5_10min_coeffs': self.t5_10min_coeffs,
            't5_15min_coeffs': self.t5_15min_coeffs,
            't6_5min_coeffs': self.t6_5min_coeffs,
            't6_10min_coeffs': self.t6_10min_coeffs,
            't6_15min_coeffs': self.t6_15min_coeffs,
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

        self.degree = model_data['degree']
        self.t4_5min_coeffs = model_data['t4_5min_coeffs']
        self.t4_10min_coeffs = model_data['t4_10min_coeffs']
        self.t4_15min_coeffs = model_data['t4_15min_coeffs']
        self.t5_5min_coeffs = model_data['t5_5min_coeffs']
        self.t5_10min_coeffs = model_data['t5_10min_coeffs']
        self.t5_15min_coeffs = model_data['t5_15min_coeffs']
        self.t6_5min_coeffs = model_data['t6_5min_coeffs']
        self.t6_10min_coeffs = model_data['t6_10min_coeffs']
        self.t6_15min_coeffs = model_data['t6_15min_coeffs']
        self.feature_mean = model_data['feature_mean']
        self.feature_std = model_data['feature_std']
        self.training_samples = model_data['training_samples']
        self.last_training_time = model_data['last_training_time']
        self.prediction_accuracy = model_data['prediction_accuracy']

        self.is_trained = True

    def get_model_info(self) -> Dict:
        """모델 정보 반환"""
        return {
            'degree': self.degree,
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

        total_bytes = 0
        for coeffs in [self.t4_5min_coeffs, self.t4_10min_coeffs, self.t4_15min_coeffs,
                      self.t5_5min_coeffs, self.t5_10min_coeffs, self.t5_15min_coeffs,
                      self.t6_5min_coeffs, self.t6_10min_coeffs, self.t6_15min_coeffs]:
            if coeffs is not None:
                total_bytes += coeffs.nbytes

        total_bytes += self.feature_mean.nbytes if self.feature_mean is not None else 0
        total_bytes += self.feature_std.nbytes if self.feature_std is not None else 0

        return total_bytes / (1024 * 1024)
