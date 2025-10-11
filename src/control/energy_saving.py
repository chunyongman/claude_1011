"""
ESS AI System - 핵심 에너지 절감 원리
"잠깐 더 써서 나중에 훨씬 많이 절약"
- 선제적 대응: 온도 상승 차단
- 단계적 감속: 즉시 감속
- 세제곱 법칙: 전력 ∝ (주파수/60)³
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import numpy as np


class TemperatureTrend(Enum):
    """온도 추세"""
    RISING = "rising"  # 상승
    STABLE = "stable"  # 안정
    FALLING = "falling"  # 하강


class ControlStrategy(Enum):
    """제어 전략"""
    PROACTIVE_INCREASE = "proactive_increase"  # 선제적 증속
    GRADUAL_DECREASE = "gradual_decrease"  # 단계적 감속
    MAINTAIN = "maintain"  # 유지
    EMERGENCY = "emergency"  # 긴급


@dataclass
class EnergySavingMetrics:
    """에너지 절감 지표"""
    traditional_60hz_power: float = 0.0  # 60Hz 고정 방식 전력
    traditional_ess_power: float = 0.0  # 기존 ESS 방식 전력
    ai_ess_power: float = 0.0  # AI ESS 방식 전력

    savings_vs_60hz: float = 0.0  # 60Hz 대비 절감률
    savings_vs_traditional_ess: float = 0.0  # 기존 ESS 대비 절감률

    proactive_interventions: int = 0  # 선제적 개입 횟수
    emergency_preventions: int = 0  # 긴급 상황 예방 횟수


@dataclass
class TemperaturePredictor:
    """
    온도 예측기
    최근 데이터 기반 추세 분석
    """
    window_size: int = 15  # 30초 (2초 × 15)
    history: List[Tuple[datetime, float]] = field(default_factory=list)

    def add_measurement(self, timestamp: datetime, temperature: float) -> None:
        """측정값 추가"""
        self.history.append((timestamp, temperature))
        if len(self.history) > self.window_size:
            self.history.pop(0)

    def predict_trend(self) -> Tuple[TemperatureTrend, float]:
        """
        온도 추세 예측
        Returns: (추세, 변화율 °C/분)
        """
        if len(self.history) < 5:
            return TemperatureTrend.STABLE, 0.0

        # 선형 회귀로 추세 분석
        times = np.array([(t - self.history[0][0]).total_seconds() for t, _ in self.history])
        temps = np.array([temp for _, temp in self.history])

        # 기울기 계산
        if len(times) > 1:
            slope = np.polyfit(times, temps, 1)[0]  # °C/초
            slope_per_minute = slope * 60.0  # °C/분

            # 추세 판단
            if slope_per_minute > 0.5:  # 0.5°C/분 이상 상승
                return TemperatureTrend.RISING, slope_per_minute
            elif slope_per_minute < -0.5:  # 0.5°C/분 이상 하강
                return TemperatureTrend.FALLING, slope_per_minute
            else:
                return TemperatureTrend.STABLE, slope_per_minute

        return TemperatureTrend.STABLE, 0.0

    def predict_future_temperature(self, minutes_ahead: float) -> Optional[float]:
        """
        미래 온도 예측
        minutes_ahead: 예측 시간 (분)
        """
        if len(self.history) < 5:
            return None

        trend, rate = self.predict_trend()
        current_temp = self.history[-1][1]

        predicted_temp = current_temp + (rate * minutes_ahead)
        return predicted_temp


class EnergySavingController:
    """
    핵심 에너지 절감 제어기
    - 선제적 대응
    - 단계적 감속
    - 세제곱 법칙 기반 최적화
    """

    def __init__(self):
        # 온도 예측기
        self.t4_predictor = TemperaturePredictor()
        self.t5_predictor = TemperaturePredictor()
        self.t6_predictor = TemperaturePredictor()

        # 임계값
        self.t4_warning_threshold = 46.0  # T4 경고 (48°C 전 2도)
        self.t4_critical_threshold = 48.0  # T4 임계
        self.t2_t3_critical_threshold = 49.0  # T2/T3 임계
        self.t5_target = 35.0  # T5 목표
        self.t6_target = 43.0  # T6 목표

        # 선제적 증속
        self.proactive_increase_hz = 2.0  # 선제 증속량
        self.gradual_decrease_step_hz = 2.0  # 단계적 감속량

        # 에너지 절감 지표
        self.metrics = EnergySavingMetrics()

        # 제어 이력
        self.control_history: List[Dict] = []

    def calculate_power(self, frequency_hz: float, rated_power_kw: float) -> float:
        """
        전력 계산 (세제곱 법칙)
        전력 ∝ (주파수/60)³
        """
        frequency_ratio = frequency_hz / 60.0
        power = rated_power_kw * (frequency_ratio ** 3)
        return power

    def calculate_energy_savings(
        self,
        current_freq: float,
        proposed_freq: float,
        duration_minutes: float,
        rated_power_kw: float
    ) -> Dict[str, float]:
        """
        에너지 절감량 계산

        비교:
        1. 60Hz 고정
        2. 기존 ESS (50-55Hz → 60Hz)
        3. AI ESS (현재+2Hz)
        """
        # 1. 60Hz 고정 방식
        power_60hz = self.calculate_power(60.0, rated_power_kw)
        energy_60hz = power_60hz * (duration_minutes / 60.0)  # kWh

        # 2. 기존 ESS 방식 (임계치 도달시 60Hz)
        power_traditional = self.calculate_power(55.0, rated_power_kw)  # 평균 55Hz
        energy_traditional = power_traditional * (duration_minutes / 60.0)

        # 3. AI ESS 방식 (현재+2Hz)
        power_ai = self.calculate_power(proposed_freq, rated_power_kw)
        energy_ai = power_ai * (duration_minutes / 60.0)

        # 절감률
        savings_vs_60hz = ((energy_60hz - energy_ai) / energy_60hz) * 100.0
        savings_vs_traditional = ((energy_traditional - energy_ai) / energy_traditional) * 100.0

        return {
            "energy_60hz_kwh": energy_60hz,
            "energy_traditional_ess_kwh": energy_traditional,
            "energy_ai_ess_kwh": energy_ai,
            "savings_vs_60hz_percent": savings_vs_60hz,
            "savings_vs_traditional_ess_percent": savings_vs_traditional,
            "power_60hz_kw": power_60hz,
            "power_traditional_kw": power_traditional,
            "power_ai_kw": power_ai
        }

    def decide_proactive_control(
        self,
        current_temp: float,
        current_freq: float,
        sensor_name: str
    ) -> Tuple[ControlStrategy, float, str]:
        """
        선제적 제어 결정

        Returns: (전략, 권장 주파수, 이유)
        """
        # 온도 예측기 선택
        if sensor_name == "T4":
            predictor = self.t4_predictor
            warning_threshold = self.t4_warning_threshold
            critical_threshold = self.t4_critical_threshold
        elif sensor_name == "T5":
            predictor = self.t5_predictor
            warning_threshold = self.t5_target + 0.5
            critical_threshold = 36.0
        elif sensor_name == "T6":
            predictor = self.t6_predictor
            warning_threshold = self.t6_target + 1.0
            critical_threshold = 50.0
        else:
            return ControlStrategy.MAINTAIN, current_freq, "Unknown sensor"

        # 추세 예측
        trend, rate = predictor.predict_trend()
        predicted_temp_5min = predictor.predict_future_temperature(5.0)

        # === 온도 상승 시나리오: 선제적 대응 ===
        if trend == TemperatureTrend.RISING:
            # 경고 수준에 접근 중
            if current_temp >= warning_threshold:
                # 선제적 증속
                new_freq = min(60.0, current_freq + self.proactive_increase_hz)
                self.metrics.proactive_interventions += 1

                reason = f"{sensor_name}={current_temp:.1f}°C 상승 추세 (예측: {predicted_temp_5min:.1f}°C), 선제 증속 +{self.proactive_increase_hz}Hz"

                # 임계치 도달 예방
                if predicted_temp_5min and predicted_temp_5min >= critical_threshold:
                    self.metrics.emergency_preventions += 1
                    reason += f" [긴급 예방: {critical_threshold}°C 도달 차단]"

                return ControlStrategy.PROACTIVE_INCREASE, new_freq, reason

        # === 온도 하강 시나리오: 단계적 감속 ===
        elif trend == TemperatureTrend.FALLING:
            # 목표 온도 이하로 안정적 하강
            if current_temp < warning_threshold - 1.0:
                # 단계적 감속
                new_freq = max(40.0, current_freq - self.gradual_decrease_step_hz)

                reason = f"{sensor_name}={current_temp:.1f}°C 하강 추세, 단계 감속 -{self.gradual_decrease_step_hz}Hz"

                return ControlStrategy.GRADUAL_DECREASE, new_freq, reason

        # === 안정 상태: 유지 ===
        return ControlStrategy.MAINTAIN, current_freq, f"{sensor_name} 안정 ({trend.value})"

    def evaluate_control_decision(
        self,
        temperatures: Dict[str, float],
        current_frequencies: Dict[str, float]
    ) -> Dict[str, any]:
        """
        전체 제어 결정 평가

        Returns: {
            "sw_pump_freq": 권장 주파수,
            "fw_pump_freq": 권장 주파수,
            "er_fan_freq": 권장 주파수,
            "strategy": 제어 전략,
            "reason": 이유,
            "energy_savings": 절감 효과
        }
        """
        # T5 기반 SW 펌프 제어
        sw_strategy, sw_freq, sw_reason = self.decide_proactive_control(
            temperatures['T5'],
            current_frequencies.get('sw_pump', 50.0),
            "T5"
        )

        # T4 기반 FW 펌프 제어
        fw_strategy, fw_freq, fw_reason = self.decide_proactive_control(
            temperatures['T4'],
            current_frequencies.get('fw_pump', 50.0),
            "T4"
        )

        # T6 기반 E/R 팬 제어
        er_strategy, er_freq, er_reason = self.decide_proactive_control(
            temperatures['T6'],
            current_frequencies.get('er_fan', 48.0),
            "T6"
        )

        # 에너지 절감 계산 (SW 펌프 예시)
        savings = self.calculate_energy_savings(
            current_freq=current_frequencies.get('sw_pump', 50.0),
            proposed_freq=sw_freq,
            duration_minutes=10.0,
            rated_power_kw=132.0  # SW 펌프 정격
        )

        decision = {
            "sw_pump_freq": sw_freq,
            "fw_pump_freq": fw_freq,
            "er_fan_freq": er_freq,
            "sw_strategy": sw_strategy.value,
            "fw_strategy": fw_strategy.value,
            "er_strategy": er_strategy.value,
            "sw_reason": sw_reason,
            "fw_reason": fw_reason,
            "er_reason": er_reason,
            "energy_savings": savings,
            "timestamp": datetime.now()
        }

        # 이력 저장
        self.control_history.append(decision)
        if len(self.control_history) > 1000:
            self.control_history.pop(0)

        return decision

    def update_metrics(self, decision: Dict) -> None:
        """절감 지표 업데이트"""
        savings = decision.get("energy_savings", {})

        self.metrics.ai_ess_power = savings.get("power_ai_kw", 0.0)
        self.metrics.traditional_ess_power = savings.get("power_traditional_kw", 0.0)
        self.metrics.traditional_60hz_power = savings.get("power_60hz_kw", 0.0)

        self.metrics.savings_vs_60hz = savings.get("savings_vs_60hz_percent", 0.0)
        self.metrics.savings_vs_traditional_ess = savings.get("savings_vs_traditional_ess_percent", 0.0)

    def get_savings_summary(self) -> str:
        """절감 효과 요약"""
        summary = []
        summary.append("📊 에너지 절감 효과")
        summary.append(f"  60Hz 고정 대비: {self.metrics.savings_vs_60hz:.1f}% 절감")
        summary.append(f"  기존 ESS 대비: {self.metrics.savings_vs_traditional_ess:.1f}% 추가 절감")
        summary.append(f"  선제적 개입: {self.metrics.proactive_interventions}회")
        summary.append(f"  긴급 예방: {self.metrics.emergency_preventions}회")
        summary.append(f"\n💡 절감 원리:")
        summary.append(f"  - 선제적 대응: 온도 상승 차단 (현재+2Hz)")
        summary.append(f"  - 단계적 감속: 즉시 감속 (-2Hz 단계)")
        summary.append(f"  - 세제곱 법칙: 전력 ∝ (주파수/60)³")

        return "\n".join(summary)


def create_energy_saving_controller() -> EnergySavingController:
    """에너지 절감 제어기 생성"""
    return EnergySavingController()
