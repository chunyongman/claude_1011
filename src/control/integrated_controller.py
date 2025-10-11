"""
ESS AI System - 통합 제어기
- 안전 제약조건 우선순위 제어
- 긴급 제어 모드
- 에너지 절감 + PID 통합
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

from .energy_saving import EnergySavingController, ControlStrategy
from .pid_controller import DualPIDController
from ..core.safety_constraints import SafetyConstraints, SafetyLevel


class ControlPriority(Enum):
    """제어 우선순위"""
    PRIORITY_1_PRESSURE = 1  # PX1 ≥ 1.0 bar
    PRIORITY_2_COOLER_PROTECTION = 2  # T2/T3 < 49°C
    PRIORITY_3_TEMPERATURE_TARGET = 3  # T5, T6 목표
    PRIORITY_4_FW_INLET_LIMIT = 4  # T4 < 48°C
    PRIORITY_5_ENERGY_OPTIMIZATION = 5  # 에너지 최적화


@dataclass
class ControlDecision:
    """제어 결정"""
    sw_pump_freq: float
    fw_pump_freq: float
    er_fan_freq: float
    control_mode: str
    priority_violated: Optional[int] = None
    emergency_action: bool = False
    reason: str = ""
    timestamp: datetime = None


class IntegratedController:
    """
    통합 제어기
    """

    def __init__(self):
        # 하위 제어기
        self.energy_saving = EnergySavingController()
        self.pid_controller = DualPIDController()
        self.safety_constraints = SafetyConstraints()

        # 제어 모드
        self.emergency_mode = False

    def compute_control(
        self,
        temperatures: Dict[str, float],
        pressure: float,
        engine_load: float,
        current_frequencies: Dict[str, float]
    ) -> ControlDecision:
        """
        통합 제어 계산

        우선순위:
        1. PX1 ≥ 1.0 bar
        2. T2/T3 < 49°C
        3. T5 = 35±0.5°C, T6 = 43±1.0°C
        4. T4 < 48°C
        5. 에너지 최적화
        """
        decision = ControlDecision(
            sw_pump_freq=50.0,
            fw_pump_freq=50.0,
            er_fan_freq=48.0,
            control_mode="normal",
            timestamp=datetime.now()
        )

        # === 우선순위 1: 압력 유지 ===
        if pressure < 1.0:
            decision.sw_pump_freq = min(60.0, current_frequencies.get('sw_pump', 50.0) + 5.0)
            decision.control_mode = "emergency_pressure"
            decision.priority_violated = 1
            decision.emergency_action = True
            decision.reason = f"압력 부족: {pressure:.2f}bar < 1.0bar"
            return decision

        # === 우선순위 2: Cooler 보호 (T2/T3 < 49°C) ===
        t2_t3_max = max(temperatures.get('T2', 0), temperatures.get('T3', 0))
        if t2_t3_max >= 49.0:
            decision.sw_pump_freq = 60.0
            decision.control_mode = "emergency_cooler"
            decision.priority_violated = 2
            decision.emergency_action = True
            decision.reason = f"Cooler 과열: max(T2,T3)={t2_t3_max:.1f}°C ≥ 49°C"
            return decision

        # === 우선순위 4: T4 < 48°C ===
        if temperatures.get('T4', 0) >= 48.0:
            decision.fw_pump_freq = 60.0
            decision.control_mode = "emergency_fw_inlet"
            decision.priority_violated = 4
            decision.emergency_action = True
            decision.reason = f"FW 입구 과열: T4={temperatures['T4']:.1f}°C ≥ 48°C"
            return decision

        # === 우선순위 3 & 5: PID + 에너지 절감 ===
        # PID 제어
        pid_output = self.pid_controller.compute_control_outputs(
            t5_measured=temperatures.get('T5', 35.0),
            t6_measured=temperatures.get('T6', 43.0),
            engine_load_percent=engine_load,
            seawater_temp=temperatures.get('T1', 28.0),
            dt_seconds=2.0
        )

        # 에너지 절감 제어
        energy_decision = self.energy_saving.evaluate_control_decision(
            temperatures=temperatures,
            current_frequencies=current_frequencies
        )

        # 통합 결정 (PID + 에너지 절감)
        decision.sw_pump_freq = max(
            pid_output['sw_pump_freq'],
            energy_decision['sw_pump_freq']
        )

        decision.er_fan_freq = max(
            pid_output['er_fan_freq'],
            energy_decision['er_fan_freq']
        )

        decision.fw_pump_freq = energy_decision['fw_pump_freq']  # FW 펌프는 T4 기반 (Energy Saving)

        decision.control_mode = "integrated_pid_energy"
        decision.reason = f"PID + 에너지 절감 통합 제어"

        return decision

    def get_control_summary(self) -> str:
        """제어 요약"""
        summary = []
        summary.append("🎮 통합 제어 상태")
        summary.append(f"  긴급 모드: {'🚨 Yes' if self.emergency_mode else '✅ No'}")

        # PID 정보
        pid_info = self.pid_controller.get_controllers_info()
        summary.append(f"\n  T5 제어: {pid_info['t5_controller']['error']:.2f}°C 오차")
        summary.append(f"  T6 제어: {pid_info['t6_controller']['error']:.2f}°C 오차")

        # 에너지 절감 정보
        summary.append(f"\n{self.energy_saving.get_savings_summary()}")

        return "\n".join(summary)


def create_integrated_controller() -> IntegratedController:
    """통합 제어기 생성"""
    return IntegratedController()
