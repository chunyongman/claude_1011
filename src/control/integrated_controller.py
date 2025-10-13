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

        # === 긴급 상황 체크 (복합 가능) ===
        emergency_actions = []

        # 우선순위 2: Cooler 보호 (T2/T3 < 49°C, 히스테리시스: 49°C 이상에서 긴급, 47°C 이하에서 해제)
        t2_t3_max = max(temperatures.get('T2', 0), temperatures.get('T3', 0))
        if t2_t3_max >= 49.0:
            decision.sw_pump_freq = 60.0
            emergency_actions.append(f"Cooler 과열: max(T2,T3)={t2_t3_max:.1f}°C ≥ 49°C")
            decision.priority_violated = 2
            decision.emergency_action = True
        elif t2_t3_max >= 47.0:  # 히스테리시스 구간 (47~49°C): 현재값보다 낮추지 않음 (감속 방지)
            current_sw = current_frequencies.get('sw_pump', 50.0)
            # PID가 주파수를 낮추려고 해도 현재값 이상 유지
            # (온도가 여전히 높으므로 감속 방지)
            # 단, emergency_actions에 추가하여 히스테리시스 상태임을 표시
            if current_sw >= 50.0:  # 50 Hz 이상이면 현재 주파수 유지
                decision.sw_pump_freq = current_sw
                emergency_actions.append(f"Cooler 주의: max(T2,T3)={t2_t3_max:.1f}°C (감속 방지, {current_sw:.1f}Hz 유지)")
                decision.priority_violated = 2
                decision.emergency_action = True
            # 50 Hz 미만이면 PID가 처리 (emergency_actions 없음)

        # 우선순위 4: T4 < 48°C (히스테리시스: 48°C 이상에서 긴급, 46°C 이하에서 해제)
        t4_temp = temperatures.get('T4', 0)
        if t4_temp >= 48.0:
            decision.fw_pump_freq = 60.0
            emergency_actions.append(f"FW 입구 과열: T4={t4_temp:.1f}°C ≥ 48°C")
            if decision.priority_violated is None:
                decision.priority_violated = 4
            decision.emergency_action = True
        elif t4_temp >= 46.0:  # 히스테리시스 구간 (46~48°C): 현재값보다 낮추지 않음 (감속 방지)
            current_fw = current_frequencies.get('fw_pump', 50.0)
            # PID가 주파수를 낮추려고 해도 현재값 이상 유지
            # (온도가 여전히 높으므로 감속 방지)
            if current_fw >= 50.0:  # 50 Hz 이상이면 현재 주파수 유지
                decision.fw_pump_freq = current_fw
                emergency_actions.append(f"FW 입구 주의: T4={t4_temp:.1f}°C (감속 방지, {current_fw:.1f}Hz 유지)")
                if decision.priority_violated is None:
                    decision.priority_violated = 4
                decision.emergency_action = True
            # 50 Hz 미만이면 PID가 처리

        # 긴급 상황이 있으면 즉시 반환 (단, 다른 온도 경고도 추가)
        if emergency_actions:
            decision.control_mode = "emergency_multiple" if len(emergency_actions) > 1 else ("emergency_cooler" if t2_t3_max >= 49.0 else "emergency_fw_inlet")

            # 추가 경고 정보 (T5, T6)
            warnings = []
            t5 = temperatures.get('T5', 35.0)
            t6 = temperatures.get('T6', 43.0)
            if t5 > 37.0:  # T5 목표 35°C + 2°C 마진
                warnings.append(f"T5={t5:.1f}°C (목표 35°C)")
            if t6 > 45.0:  # T6 목표 43°C + 2°C 마진
                warnings.append(f"T6={t6:.1f}°C (목표 43°C)")

            if warnings:
                decision.reason = " | ".join(emergency_actions) + " [추가 경고: " + ", ".join(warnings) + "]"
            else:
                decision.reason = " | ".join(emergency_actions)

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

        # === 우선순위 1: 압력 제약 (주파수 감소 제한) ===
        # PID 제어가 주파수를 낮추려고 해도 압력이 1.0 미만이면 현재 값 이하로 내려가지 않도록 함
        if pressure < 1.0:
            current_sw_freq = current_frequencies.get('sw_pump', 50.0)
            if decision.sw_pump_freq < current_sw_freq:
                # 주파수를 낮추려고 하는 경우 → 현재 값 유지
                decision.sw_pump_freq = current_sw_freq
                decision.control_mode = "pressure_constraint"
                decision.priority_violated = 1
                decision.emergency_action = False  # 긴급은 아니고 제약 조건
                decision.reason = f"압력 제약 활성: {pressure:.2f}bar < 1.0bar → SW 펌프 주파수 감소 제한 (현재 {current_sw_freq:.1f}Hz 유지)"

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
