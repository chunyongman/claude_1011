"""
예측적 제어 로직
5-15분 후 상황을 예측하여 미리 대응
"""
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime
import numpy as np

from src.ml.temperature_predictor import (
    PolynomialRegressionPredictor,
    TemperatureSequence,
    TemperaturePrediction
)
from src.ml.random_forest_optimizer import (
    RandomForestOptimizer,
    OptimizationInput,
    OptimizationOutput
)
from src.ml.pattern_classifier import (
    PatternClassifier,
    EnginePattern,
    PatternObservation
)


@dataclass
class PredictiveControlOutput:
    """예측 제어 출력"""
    timestamp: datetime

    # 예측 정보
    temperature_prediction: TemperaturePrediction
    current_pattern: EnginePattern
    predicted_pattern: EnginePattern
    pattern_confidence: float

    # 제어 출력
    pump_frequency_hz: float
    pump_count: int
    fan_frequency_hz: float
    fan_count: int

    # 제어 근거
    control_mode: str  # "reactive", "predictive", "pattern_based"
    prediction_weight: float  # 예측 가중치 (0-1)
    reasoning: str


class PredictiveController:
    """
    예측적 제어 시스템

    통합:
    - Polynomial Regression: 온도 예측
    - Random Forest: 최적화 모델
    - Pattern Classifier: 패턴 인식
    """

    def __init__(
        self,
        temp_predictor: PolynomialRegressionPredictor,
        rf_optimizer: RandomForestOptimizer,
        pattern_classifier: PatternClassifier
    ):
        """
        Args:
            temp_predictor: 온도 예측 모델
            rf_optimizer: Random Forest 최적화 모델
            pattern_classifier: 패턴 분류기
        """
        self.temp_predictor = temp_predictor
        self.rf_optimizer = rf_optimizer
        self.pattern_classifier = pattern_classifier

        # 제어 파라미터
        self.t5_target = 35.0
        self.t6_target = 43.0

        # 예측 임계값
        self.temp_rise_threshold = 1.0  # °C
        self.temp_fall_threshold = -0.5  # °C

        # 성능 통계
        self.total_predictions = 0
        self.predictive_actions = 0
        self.reactive_actions = 0

    def compute_predictive_control(
        self,
        # 현재 센서 데이터
        current_temps: Dict[str, float],  # T1-T7
        current_pressure: float,
        current_engine_load: float,
        current_ship_speed: float,
        current_gps: Dict[str, float],  # lat, lon

        # 시퀀스 데이터 (30분)
        temp_sequence: TemperatureSequence,

        # 현재 제어 상태
        current_pump_freq: float,
        current_pump_count: int,
        current_fan_freq: float,
        current_fan_count: int

    ) -> PredictiveControlOutput:
        """
        예측적 제어 계산

        Returns:
            PredictiveControlOutput
        """
        self.total_predictions += 1
        timestamp = datetime.now()

        # 1. 온도 예측
        temp_prediction = self.temp_predictor.predict(temp_sequence)

        # 2. 패턴 분류
        pattern_obs = self.pattern_classifier.classify_pattern(
            engine_load_sequence=temp_sequence.engine_load_sequence,
            ship_speed_sequence=[current_ship_speed] * len(temp_sequence.timestamps),
            t6_sequence=temp_sequence.t6_sequence,
            timestamps=temp_sequence.timestamps
        )

        current_pattern = pattern_obs.pattern

        # 3. 다음 패턴 예측
        predicted_pattern, pattern_conf = self.pattern_classifier.predict_next_pattern(
            current_pattern, time_horizon_minutes=15
        )

        # 4. 제어 모드 결정
        control_mode, prediction_weight = self._determine_control_mode(
            temp_prediction, current_pattern, current_temps
        )

        # 5. 제어 출력 계산
        if control_mode == "predictive":
            # 예측 기반 제어
            output = self._predictive_control(
                temp_prediction, current_pattern, predicted_pattern,
                current_temps, current_engine_load, current_ship_speed,
                current_gps, prediction_weight
            )
            self.predictive_actions += 1
            reasoning = self._explain_predictive_action(temp_prediction, current_pattern)

        elif control_mode == "pattern_based":
            # 패턴 기반 제어
            output = self._pattern_based_control(
                current_pattern, current_temps, current_engine_load,
                current_ship_speed, current_gps, current_pump_freq, current_fan_freq
            )
            reasoning = f"패턴 기반 제어: {current_pattern.value}"

        else:
            # 반응적 제어 (기존 방식)
            output = self._reactive_control(
                current_temps, current_engine_load, current_ship_speed, current_gps
            )
            self.reactive_actions += 1
            reasoning = "반응적 제어: 온도 안정, 예측 불필요"

        return PredictiveControlOutput(
            timestamp=timestamp,
            temperature_prediction=temp_prediction,
            current_pattern=current_pattern,
            predicted_pattern=predicted_pattern,
            pattern_confidence=pattern_conf,
            pump_frequency_hz=output['pump_freq'],
            pump_count=output['pump_count'],
            fan_frequency_hz=output['fan_freq'],
            fan_count=output['fan_count'],
            control_mode=control_mode,
            prediction_weight=prediction_weight,
            reasoning=reasoning
        )

    def _determine_control_mode(
        self,
        temp_pred: TemperaturePrediction,
        pattern: EnginePattern,
        current_temps: Dict[str, float]
    ) -> tuple[str, float]:
        """
        제어 모드 결정

        Returns:
            (제어 모드, 예측 가중치)
        """
        # 10분 후 예측 온도 변화
        t5_delta = temp_pred.t5_pred_10min - current_temps['T5']
        t6_delta = temp_pred.t6_pred_10min - current_temps['T6']

        # 1. 온도 상승 예측 → 예측적 제어
        if t5_delta > self.temp_rise_threshold or t6_delta > self.temp_rise_threshold:
            weight = 0.8 if pattern == EnginePattern.ACCELERATION else 0.6
            return "predictive", weight

        # 2. 온도 대폭 하강 예측 → 예측적 제어
        if t5_delta < self.temp_fall_threshold or t6_delta < self.temp_fall_threshold:
            weight = 0.7 if pattern == EnginePattern.DECELERATION else 0.5
            return "predictive", weight

        # 3. 패턴 기반 제어 (가속/감속/정박)
        if pattern in [EnginePattern.ACCELERATION, EnginePattern.DECELERATION, EnginePattern.BERTHING]:
            if self.pattern_classifier.is_pattern_learned(pattern):
                return "pattern_based", 0.4

        # 4. 반응적 제어 (정속)
        return "reactive", 0.0

    def _predictive_control(
        self,
        temp_pred: TemperaturePrediction,
        current_pattern: EnginePattern,
        predicted_pattern: EnginePattern,
        current_temps: Dict[str, float],
        engine_load: float,
        ship_speed: float,
        gps: Dict[str, float],
        prediction_weight: float
    ) -> Dict:
        """예측 기반 제어"""
        # Random Forest 최적화 (10분 후 예측값 사용)
        opt_input = OptimizationInput(
            t1_seawater=current_temps['T1'],
            t5_fw_outlet=temp_pred.t5_pred_10min,  # 예측값 사용
            t6_er_temp=temp_pred.t6_pred_10min,  # 예측값 사용
            t7_outside_air=current_temps['T7'],
            hour=datetime.now().hour,
            season=datetime.now().month // 3,
            gps_latitude=gps['lat'],
            gps_longitude=gps['lon'],
            ship_speed_knots=ship_speed,
            engine_load_percent=engine_load
        )

        opt_output = self.rf_optimizer.predict(opt_input)

        # 예측 가중치 적용
        # 높은 가중치 = 예측값에 더 의존
        base_pump_freq = opt_output.pump_frequency_hz
        base_fan_freq = opt_output.fan_frequency_hz

        # 패턴 전략 반영
        pattern_params = self.pattern_classifier.get_optimal_control_params(
            current_pattern, base_pump_freq, base_fan_freq
        )

        # 가중 평균
        final_pump_freq = (prediction_weight * pattern_params['pump_frequency_hz'] +
                          (1 - prediction_weight) * base_pump_freq)
        final_fan_freq = (prediction_weight * pattern_params['fan_frequency_hz'] +
                         (1 - prediction_weight) * base_fan_freq)

        return {
            'pump_freq': final_pump_freq,
            'pump_count': opt_output.pump_count,
            'fan_freq': final_fan_freq,
            'fan_count': opt_output.fan_count
        }

    def _pattern_based_control(
        self,
        pattern: EnginePattern,
        current_temps: Dict[str, float],
        engine_load: float,
        ship_speed: float,
        gps: Dict[str, float],
        current_pump_freq: float,
        current_fan_freq: float
    ) -> Dict:
        """패턴 기반 제어"""
        # 패턴 전략
        params = self.pattern_classifier.get_optimal_control_params(
            pattern, current_pump_freq, current_fan_freq
        )

        # 펌프 대수 결정 (엔진 부하 기반)
        pump_count = 2 if engine_load >= 30 else 1

        # 팬 대수 결정 (온도 기반)
        if current_temps['T6'] > 44.0:
            fan_count = 4
        elif current_temps['T6'] > 43.0:
            fan_count = 3
        else:
            fan_count = 2

        return {
            'pump_freq': params['pump_frequency_hz'],
            'pump_count': pump_count,
            'fan_freq': params['fan_frequency_hz'],
            'fan_count': fan_count
        }

    def _reactive_control(
        self,
        current_temps: Dict[str, float],
        engine_load: float,
        ship_speed: float,
        gps: Dict[str, float]
    ) -> Dict:
        """반응적 제어 (기존 방식)"""
        opt_input = OptimizationInput(
            t1_seawater=current_temps['T1'],
            t5_fw_outlet=current_temps['T5'],
            t6_er_temp=current_temps['T6'],
            t7_outside_air=current_temps['T7'],
            hour=datetime.now().hour,
            season=datetime.now().month // 3,
            gps_latitude=gps['lat'],
            gps_longitude=gps['lon'],
            ship_speed_knots=ship_speed,
            engine_load_percent=engine_load
        )

        opt_output = self.rf_optimizer.predict(opt_input)

        return {
            'pump_freq': opt_output.pump_frequency_hz,
            'pump_count': opt_output.pump_count,
            'fan_freq': opt_output.fan_frequency_hz,
            'fan_count': opt_output.fan_count
        }

    def _explain_predictive_action(
        self,
        temp_pred: TemperaturePrediction,
        pattern: EnginePattern
    ) -> str:
        """예측 제어 설명"""
        t5_delta = temp_pred.t5_pred_10min - temp_pred.t5_current
        t6_delta = temp_pred.t6_pred_10min - temp_pred.t6_current

        reasons = []

        if t5_delta > self.temp_rise_threshold:
            reasons.append(f"T5 상승 예측 (+{t5_delta:.1f}°C)")
        if t6_delta > self.temp_rise_threshold:
            reasons.append(f"T6 상승 예측 (+{t6_delta:.1f}°C)")
        if t5_delta < self.temp_fall_threshold:
            reasons.append(f"T5 하강 예측 ({t5_delta:.1f}°C)")
        if t6_delta < self.temp_fall_threshold:
            reasons.append(f"T6 하강 예측 ({t6_delta:.1f}°C)")

        reasons.append(f"패턴: {pattern.value}")

        return "예측적 제어: " + ", ".join(reasons)

    def get_performance_stats(self) -> Dict:
        """성능 통계"""
        total = self.total_predictions
        if total == 0:
            return {
                'total_predictions': 0,
                'predictive_ratio': 0.0,
                'reactive_ratio': 0.0
            }

        return {
            'total_predictions': total,
            'predictive_actions': self.predictive_actions,
            'reactive_actions': self.reactive_actions,
            'predictive_ratio': (self.predictive_actions / total) * 100.0,
            'reactive_ratio': (self.reactive_actions / total) * 100.0
        }
