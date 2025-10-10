"""
엔진 부하 패턴 분류 및 학습
가속/정속/감속/정박 패턴 자동 인식
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import numpy as np


class EnginePattern(Enum):
    """엔진 부하 패턴"""
    ACCELERATION = "acceleration"  # 가속
    STEADY_STATE = "steady_state"  # 정속
    DECELERATION = "deceleration"  # 감속
    BERTHING = "berthing"  # 정박


@dataclass
class PatternObservation:
    """패턴 관측 데이터"""
    timestamp: datetime

    # 엔진 부하 (%)
    engine_load: float
    engine_load_trend: float  # %/min

    # GPS 속도 (knots)
    ship_speed: float
    ship_speed_trend: float  # knots/min

    # 온도 변화
    t6_trend: float  # °C/min

    # 분류된 패턴
    pattern: EnginePattern


@dataclass
class PatternStrategy:
    """패턴별 제어 전략"""
    pattern: EnginePattern

    # 냉각 전략
    cooling_bias: float  # -1.0 ~ +1.0 (음수=감축, 양수=강화)

    # 예측 가중치
    prediction_weight: float  # 0.0 ~ 1.0

    # 주파수 조정
    freq_adjustment_hz: float  # -5 ~ +5 Hz

    # 설명
    description: str


class PatternClassifier:
    """엔진 부하 패턴 분류기"""

    def __init__(self, window_minutes: int = 10):
        """
        Args:
            window_minutes: 패턴 판정 윈도우 (기본값: 10분)
        """
        self.window_minutes = window_minutes

        # 패턴별 제어 전략
        self.strategies = {
            EnginePattern.ACCELERATION: PatternStrategy(
                pattern=EnginePattern.ACCELERATION,
                cooling_bias=+0.3,  # 냉각 강화
                prediction_weight=0.8,  # 높은 예측 의존
                freq_adjustment_hz=+2.0,  # 사전 증속
                description="가속 패턴: 냉각 부하 증가 예상, 사전 냉각 강화"
            ),
            EnginePattern.STEADY_STATE: PatternStrategy(
                pattern=EnginePattern.STEADY_STATE,
                cooling_bias=0.0,  # 중립
                prediction_weight=0.3,  # 낮은 예측 의존
                freq_adjustment_hz=0.0,  # 안정적 유지
                description="정속 패턴: 안정적 제어 유지"
            ),
            EnginePattern.DECELERATION: PatternStrategy(
                pattern=EnginePattern.DECELERATION,
                cooling_bias=-0.3,  # 냉각 감축
                prediction_weight=0.6,  # 중간 예측 의존
                freq_adjustment_hz=-2.0,  # 단계적 감속
                description="감속 패턴: 냉각 부하 감소 예상, 단계적 감축"
            ),
            EnginePattern.BERTHING: PatternStrategy(
                pattern=EnginePattern.BERTHING,
                cooling_bias=-0.5,  # 대폭 감축
                prediction_weight=0.4,  # 낮은 예측 의존
                freq_adjustment_hz=-5.0,  # 최소 전력 모드
                description="정박 패턴: 최소 전력 모드 전환 준비"
            )
        }

        # 패턴 학습 데이터
        self.pattern_history: List[PatternObservation] = []

        # 패턴별 누적 카운트
        self.pattern_counts = {
            EnginePattern.ACCELERATION: 0,
            EnginePattern.STEADY_STATE: 0,
            EnginePattern.DECELERATION: 0,
            EnginePattern.BERTHING: 0
        }

        # 패턴 전환 학습 시작 임계값
        self.learning_threshold = 30

    def classify_pattern(
        self,
        engine_load_sequence: List[float],
        ship_speed_sequence: List[float],
        t6_sequence: List[float],
        timestamps: List[datetime]
    ) -> PatternObservation:
        """
        패턴 분류

        Args:
            engine_load_sequence: 엔진 부하 시퀀스 (최근 10분)
            ship_speed_sequence: 선속 시퀀스
            t6_sequence: E/R 온도 시퀀스
            timestamps: 타임스탬프

        Returns:
            PatternObservation
        """
        if len(engine_load_sequence) < 2:
            raise ValueError("Insufficient data for pattern classification")

        # 추세 계산
        engine_load_trend = self._calculate_trend(engine_load_sequence, timestamps)
        ship_speed_trend = self._calculate_trend(ship_speed_sequence, timestamps)
        t6_trend = self._calculate_trend(t6_sequence, timestamps)

        current_load = engine_load_sequence[-1]
        current_speed = ship_speed_sequence[-1]

        # 패턴 분류 로직
        pattern = self._determine_pattern(
            current_load, engine_load_trend,
            current_speed, ship_speed_trend
        )

        observation = PatternObservation(
            timestamp=timestamps[-1],
            engine_load=current_load,
            engine_load_trend=engine_load_trend,
            ship_speed=current_speed,
            ship_speed_trend=ship_speed_trend,
            t6_trend=t6_trend,
            pattern=pattern
        )

        # 히스토리 저장
        self.pattern_history.append(observation)
        self.pattern_counts[pattern] += 1

        # 히스토리 크기 제한 (최근 1000개)
        if len(self.pattern_history) > 1000:
            self.pattern_history = self.pattern_history[-1000:]

        return observation

    def _calculate_trend(
        self,
        values: List[float],
        timestamps: List[datetime]
    ) -> float:
        """
        선형 추세 계산 (단위/분)

        Returns:
            변화율 (예: %/min, knots/min, °C/min)
        """
        if len(values) < 2:
            return 0.0

        # 시간 간격 (분)
        time_span = (timestamps[-1] - timestamps[0]).total_seconds() / 60.0
        if time_span < 0.1:
            return 0.0

        # 선형 회귀 (간단한 방법)
        value_change = values[-1] - values[0]
        trend = value_change / time_span

        return trend

    def _determine_pattern(
        self,
        current_load: float,
        load_trend: float,
        current_speed: float,
        speed_trend: float
    ) -> EnginePattern:
        """
        패턴 결정

        우선순위:
        1. 정박 (부하 <20%, 속도 <3 knots)
        2. 가속 (부하 증가 >2%/min 또는 속도 증가 >0.5 knots/min)
        3. 감속 (부하 감소 <-2%/min 또는 속도 감소 <-0.5 knots/min)
        4. 정속 (나머지)
        """
        # 1. 정박 판정
        if current_load < 20.0 and current_speed < 3.0:
            return EnginePattern.BERTHING

        # 2. 가속 판정
        if load_trend > 2.0 or speed_trend > 0.5:
            # 30-70% 구간 가속은 학습 중점 대상
            if 30.0 <= current_load <= 70.0:
                return EnginePattern.ACCELERATION
            else:
                return EnginePattern.ACCELERATION

        # 3. 감속 판정
        if load_trend < -2.0 or speed_trend < -0.5:
            return EnginePattern.DECELERATION

        # 4. 정속 (기본)
        return EnginePattern.STEADY_STATE

    def get_control_strategy(self, pattern: EnginePattern) -> PatternStrategy:
        """패턴별 제어 전략 반환"""
        return self.strategies[pattern]

    def is_pattern_learned(self, pattern: EnginePattern) -> bool:
        """패턴 학습 완료 여부 (30회 이상 누적)"""
        return self.pattern_counts[pattern] >= self.learning_threshold

    def get_pattern_statistics(self) -> Dict:
        """패턴 통계"""
        total = sum(self.pattern_counts.values())

        if total == 0:
            return {
                'total_observations': 0,
                'pattern_distribution': {},
                'learned_patterns': []
            }

        distribution = {
            pattern.value: {
                'count': count,
                'percentage': (count / total) * 100.0,
                'learned': self.is_pattern_learned(pattern)
            }
            for pattern, count in self.pattern_counts.items()
        }

        learned = [p.value for p in self.pattern_counts.keys()
                  if self.is_pattern_learned(p)]

        return {
            'total_observations': total,
            'pattern_distribution': distribution,
            'learned_patterns': learned
        }

    def predict_next_pattern(
        self,
        current_pattern: EnginePattern,
        time_horizon_minutes: int = 15
    ) -> Tuple[EnginePattern, float]:
        """
        다음 패턴 예측 (간단한 Markov Chain)

        Returns:
            (예측 패턴, 신뢰도)
        """
        if len(self.pattern_history) < 10:
            return current_pattern, 0.5

        # 패턴 전환 확률 학습
        transitions = {}
        for i in range(len(self.pattern_history) - 1):
            from_pattern = self.pattern_history[i].pattern
            to_pattern = self.pattern_history[i + 1].pattern

            if from_pattern not in transitions:
                transitions[from_pattern] = {}

            if to_pattern not in transitions[from_pattern]:
                transitions[from_pattern][to_pattern] = 0

            transitions[from_pattern][to_pattern] += 1

        # 현재 패턴에서 전환 확률 계산
        if current_pattern not in transitions:
            return current_pattern, 0.5

        next_patterns = transitions[current_pattern]
        total = sum(next_patterns.values())

        if total == 0:
            return current_pattern, 0.5

        # 가장 높은 확률의 패턴
        most_likely = max(next_patterns.items(), key=lambda x: x[1])
        confidence = most_likely[1] / total

        return most_likely[0], confidence

    def get_optimal_control_params(
        self,
        current_pattern: EnginePattern,
        base_pump_freq: float,
        base_fan_freq: float
    ) -> Dict[str, float]:
        """
        패턴 기반 최적 제어 파라미터

        Args:
            current_pattern: 현재 패턴
            base_pump_freq: 기본 펌프 주파수
            base_fan_freq: 기본 팬 주파수

        Returns:
            조정된 제어 파라미터
        """
        strategy = self.get_control_strategy(current_pattern)

        # 주파수 조정
        adjusted_pump_freq = base_pump_freq + strategy.freq_adjustment_hz
        adjusted_fan_freq = base_fan_freq + strategy.freq_adjustment_hz * 0.8

        # 범위 제한
        adjusted_pump_freq = np.clip(adjusted_pump_freq, 40.0, 60.0)
        adjusted_fan_freq = np.clip(adjusted_fan_freq, 35.0, 60.0)

        return {
            'pump_frequency_hz': adjusted_pump_freq,
            'fan_frequency_hz': adjusted_fan_freq,
            'cooling_bias': strategy.cooling_bias,
            'prediction_weight': strategy.prediction_weight,
            'strategy_description': strategy.description
        }
