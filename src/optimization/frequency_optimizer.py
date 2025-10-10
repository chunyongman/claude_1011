"""
ESS AI System - 주파수 최적화 및 에너지 효율 알고리즘
60Hz 고정 대비 펌프 46-52%, 팬 50-58% 절감 목표
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum
import numpy as np


class OptimizationPhase(Enum):
    """최적화 단계"""
    WEEK_1 = 1  # 46-48% 절감
    WEEK_2 = 2  # 48-50% 절감
    WEEK_3_PLUS = 3  # 50-52% 지속 개선


@dataclass
class SavingsTarget:
    """절감 목표"""
    # 초기 목표 (0-6개월, 규칙 기반)
    initial_pump_min: float = 46.0  # %
    initial_pump_max: float = 48.0
    initial_fan_min: float = 50.0
    initial_fan_max: float = 54.0

    # 학습 후 목표 (12개월+, 적응형)
    mature_pump_min: float = 48.0
    mature_pump_max: float = 52.0
    mature_fan_min: float = 54.0
    mature_fan_max: float = 58.0


@dataclass
class AffinityLaws:
    """
    Affinity Laws (상사 법칙)
    - 유량: Q ∝ f
    - 압력: P ∝ f²
    - 전력: W ∝ f³
    """

    @staticmethod
    def calculate_power_ratio(freq_hz: float, rated_freq_hz: float = 60.0) -> float:
        """
        전력 비율 계산 (세제곱 법칙)

        Args:
            freq_hz: 운전 주파수
            rated_freq_hz: 정격 주파수 (기본 60Hz)

        Returns:
            전력 비율 (60Hz 대비)
        """
        freq_ratio = freq_hz / rated_freq_hz
        power_ratio = freq_ratio ** 3
        return power_ratio

    @staticmethod
    def calculate_power(freq_hz: float, rated_power_kw: float, rated_freq_hz: float = 60.0) -> float:
        """
        실제 전력 계산 (kW)
        """
        power_ratio = AffinityLaws.calculate_power_ratio(freq_hz, rated_freq_hz)
        return rated_power_kw * power_ratio

    @staticmethod
    def calculate_savings_percent(current_freq: float, baseline_freq: float = 60.0) -> float:
        """
        절감률 계산 (%)

        Args:
            current_freq: 현재 주파수
            baseline_freq: 기준 주파수 (60Hz)

        Returns:
            절감률 (%)
        """
        current_power = AffinityLaws.calculate_power_ratio(current_freq, baseline_freq)
        savings = (1.0 - current_power) * 100.0
        return savings


@dataclass
class EfficiencyCurve:
    """효율 곡선"""

    @staticmethod
    def pump_efficiency(freq_hz: float) -> float:
        """
        펌프 효율 (%)
        최적: 45-50Hz (92-95%)
        """
        if 45.0 <= freq_hz <= 50.0:
            # 최적 구간: 47.5Hz에서 95% 최대
            deviation = abs(freq_hz - 47.5)
            return 95.0 - deviation * 0.6  # 92-95% 범위
        elif freq_hz < 45.0:
            # 저속 구간 (효율 하락)
            return max(80.0, 85.0 + (freq_hz - 40.0) * 1.4)
        else:
            # 고속 구간 (효율 하락)
            return max(88.0, 95.0 - (freq_hz - 50.0) * 0.7)

    @staticmethod
    def fan_efficiency(freq_hz: float) -> float:
        """
        팬 효율 (%)
        최적: 40-45Hz (88-92%)
        """
        if 40.0 <= freq_hz <= 45.0:
            # 최적 구간: 42.5Hz에서 92% 최대
            deviation = abs(freq_hz - 42.5)
            return 92.0 - deviation * 0.8  # 88-92% 범위
        elif freq_hz < 40.0:
            # 저속 (최소값)
            return max(75.0, 80.0 + (freq_hz - 35.0) * 1.6)
        else:
            # 고속 구간 (효율 하락)
            return max(82.0, 92.0 - (freq_hz - 45.0) * 0.67)


@dataclass
class OptimizationObjective:
    """
    다목적 최적화 목적함수
    가중치: 에너지 50%, 온도 30%, 균등화 20%
    """
    energy_weight: float = 0.5
    temperature_weight: float = 0.3
    balancing_weight: float = 0.2

    def calculate_objective(
        self,
        energy_score: float,
        temperature_score: float,
        balancing_score: float
    ) -> float:
        """
        종합 목적함수 계산 (0-100점)
        """
        objective = (
            self.energy_weight * energy_score +
            self.temperature_weight * temperature_score +
            self.balancing_weight * balancing_score
        )
        return objective


class FrequencyOptimizer:
    """
    주파수 최적화기
    60Hz 고정 대비 에너지 절감
    """

    def __init__(self, system_age_months: int = 0):
        self.system_age_months = system_age_months
        self.savings_target = SavingsTarget()
        self.objective = OptimizationObjective()

        # 최적화 단계
        self.current_phase = OptimizationPhase.WEEK_1
        self.phase_start_date: Optional[datetime] = datetime.now()

        # 성과 추적
        self.savings_history: List[Dict] = []

        # 안전 위반 카운트
        self.safety_violations = 0

    def get_current_target(self) -> Dict[str, Tuple[float, float]]:
        """
        현재 목표 절감률

        Returns:
            {
                'pump': (min%, max%),
                'fan': (min%, max%)
            }
        """
        if self.system_age_months < 6:
            # 초기 목표 (규칙 기반)
            return {
                'pump': (self.savings_target.initial_pump_min, self.savings_target.initial_pump_max),
                'fan': (self.savings_target.initial_fan_min, self.savings_target.initial_fan_max)
            }
        else:
            # 학습 후 목표 (적응형)
            return {
                'pump': (self.savings_target.mature_pump_min, self.savings_target.mature_pump_max),
                'fan': (self.savings_target.mature_fan_min, self.savings_target.mature_fan_max)
            }

    def optimize_frequency(
        self,
        current_temp: float,
        target_temp: float,
        current_freq: float,
        equipment_type: str,  # 'pump' or 'fan'
        rated_power_kw: float
    ) -> Tuple[float, Dict]:
        """
        주파수 최적화

        Returns:
            (최적 주파수, 성과 정보)
        """
        # 온도 오차
        temp_error = abs(current_temp - target_temp)

        # 현재 전력 및 절감률
        current_power = AffinityLaws.calculate_power(current_freq, rated_power_kw)
        baseline_power = AffinityLaws.calculate_power(60.0, rated_power_kw)
        current_savings = AffinityLaws.calculate_savings_percent(current_freq, 60.0)

        # 목표 절감률
        target = self.get_current_target()
        target_min, target_max = target[equipment_type]

        # 효율 곡선 기반 최적 주파수
        if equipment_type == 'pump':
            optimal_freq_range = (45.0, 50.0)
            efficiency_func = EfficiencyCurve.pump_efficiency
        else:  # fan
            optimal_freq_range = (40.0, 45.0)
            efficiency_func = EfficiencyCurve.fan_efficiency

        # 온도 제어 필요 여부
        if temp_error > 0.5:
            # 온도 오차가 크면 온도 제어 우선
            if current_temp > target_temp:
                # 냉각 필요 - 주파수 증가
                optimized_freq = min(60.0, current_freq + 2.0)
            else:
                # 온도 낮음 - 주파수 감소
                optimized_freq = max(40.0, current_freq - 2.0)
        else:
            # 온도 안정 - 절감 목표에 맞춘 주파수 선택
            # 목표 절감률의 중간값에 해당하는 주파수 계산
            target_savings_mid = (target_min + target_max) / 2.0

            # 역산: 절감률 → 주파수
            # savings% = (1 - (f/60)³) * 100
            # f = 60 * (1 - savings/100)^(1/3)
            power_ratio = 1.0 - (target_savings_mid / 100.0)
            target_freq = 60.0 * (power_ratio ** (1.0/3.0))

            # 효율 곡선 범위 내로 제한
            target_freq = max(optimal_freq_range[0], min(optimal_freq_range[1], target_freq))

            # 점진적 이동 (1Hz/step)
            if abs(current_freq - target_freq) > 1.0:
                if current_freq > target_freq:
                    optimized_freq = current_freq - 1.0
                else:
                    optimized_freq = current_freq + 1.0
            else:
                optimized_freq = target_freq

        # 절감률 계산
        optimized_savings = AffinityLaws.calculate_savings_percent(optimized_freq, 60.0)

        # 성과 정보
        performance = {
            "current_freq": current_freq,
            "optimized_freq": optimized_freq,
            "current_power_kw": current_power,
            "baseline_power_kw": baseline_power,
            "current_savings_percent": current_savings,
            "optimized_savings_percent": optimized_savings,
            "target_savings_min": target_min,
            "target_savings_max": target_max,
            "meets_target": target_min <= optimized_savings <= target_max,
            "efficiency_percent": efficiency_func(optimized_freq),
            "temp_error": temp_error
        }

        return optimized_freq, performance

    def calculate_24h_average_savings(self) -> Dict:
        """
        24시간 평균 절감률
        """
        if len(self.savings_history) == 0:
            return {
                "pump_savings_avg": 0.0,
                "fan_savings_avg": 0.0,
                "overall_savings_avg": 0.0
            }

        # 최근 24시간 데이터
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent_data = [
            d for d in self.savings_history
            if datetime.fromisoformat(d['timestamp']) >= cutoff_time
        ]

        if len(recent_data) == 0:
            return {
                "pump_savings_avg": 0.0,
                "fan_savings_avg": 0.0,
                "overall_savings_avg": 0.0
            }

        # 평균 계산
        pump_savings = [d['pump_savings'] for d in recent_data if 'pump_savings' in d]
        fan_savings = [d['fan_savings'] for d in recent_data if 'fan_savings' in d]

        pump_avg = sum(pump_savings) / len(pump_savings) if pump_savings else 0.0
        fan_avg = sum(fan_savings) / len(fan_savings) if fan_savings else 0.0
        overall_avg = (pump_avg + fan_avg) / 2.0

        return {
            "pump_savings_avg": pump_avg,
            "fan_savings_avg": fan_avg,
            "overall_savings_avg": overall_avg,
            "data_points": len(recent_data)
        }

    def record_performance(
        self,
        pump_freq: float,
        fan_freq: float,
        pump_power_kw: float,
        fan_power_kw: float
    ) -> None:
        """성과 기록"""
        pump_savings = AffinityLaws.calculate_savings_percent(pump_freq, 60.0)
        fan_savings = AffinityLaws.calculate_savings_percent(fan_freq, 60.0)

        record = {
            "timestamp": datetime.now().isoformat(),
            "pump_freq": pump_freq,
            "fan_freq": fan_freq,
            "pump_savings": pump_savings,
            "fan_savings": fan_savings,
            "pump_power_kw": pump_power_kw,
            "fan_power_kw": fan_power_kw
        }

        self.savings_history.append(record)

        # 최근 1000개만 유지
        if len(self.savings_history) > 1000:
            self.savings_history = self.savings_history[-1000:]

    def get_optimization_summary(self) -> str:
        """최적화 요약"""
        target = self.get_current_target()
        avg_savings = self.calculate_24h_average_savings()

        summary = []
        summary.append("📊 주파수 최적화 성과 (60Hz 고정 대비)")
        summary.append(f"\n시스템 경과: {self.system_age_months}개월")

        summary.append(f"\n📈 현재 목표:")
        summary.append(f"  펌프: {target['pump'][0]:.0f}-{target['pump'][1]:.0f}% 절감")
        summary.append(f"  팬: {target['fan'][0]:.0f}-{target['fan'][1]:.0f}% 절감")

        summary.append(f"\n📊 24시간 평균 성과:")
        summary.append(f"  펌프: {avg_savings['pump_savings_avg']:.1f}% 절감")
        summary.append(f"  팬: {avg_savings['fan_savings_avg']:.1f}% 절감")
        summary.append(f"  전체: {avg_savings['overall_savings_avg']:.1f}% 절감")

        # 목표 달성 여부
        pump_meets = target['pump'][0] <= avg_savings['pump_savings_avg'] <= target['pump'][1]
        fan_meets = target['fan'][0] <= avg_savings['fan_savings_avg'] <= target['fan'][1]

        summary.append(f"\n🎯 목표 달성:")
        summary.append(f"  펌프: {'✅' if pump_meets else '❌'}")
        summary.append(f"  팬: {'✅' if fan_meets else '❌'}")

        return "\n".join(summary)


def create_frequency_optimizer(system_age_months: int = 0) -> FrequencyOptimizer:
    """주파수 최적화기 생성"""
    return FrequencyOptimizer(system_age_months)
