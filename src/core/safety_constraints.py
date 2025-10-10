"""
ESS AI System - 안전 제약조건 및 제어 목표값
절대 위반 불가 규칙 (하드코딩)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime


class SafetyLevel(Enum):
    """안전 레벨"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ConstraintType(Enum):
    """제약조건 타입"""
    TEMPERATURE_LIMIT = "temperature_limit"
    FREQUENCY_LIMIT = "frequency_limit"
    PRESSURE_LIMIT = "pressure_limit"
    RATE_LIMIT = "rate_limit"
    OPERATION_COUNT = "operation_count"


@dataclass
class SafetyConstraint:
    """안전 제약조건"""
    name: str
    constraint_type: ConstraintType
    description: str
    hard_coded: bool = True  # 학습 불가 영역
    enabled: bool = True


@dataclass
class TemperatureLimits:
    """
    온도 제약조건 (절대 위반 불가)
    학습 불가 영역
    """
    # SW 출구 온도 (T2, T3)
    sw_outlet_max: float = 48.0  # °C
    sw_outlet_emergency: float = 49.0  # °C - 이 이상이면 강제 증속

    # FW 출구 온도 (T5)
    fw_outlet_max: float = 36.0  # °C

    # FW 입구 온도 (T4)
    fw_inlet_max: float = 48.0  # °C

    # E/R 온도 (T6)
    er_temp_max: float = 50.0  # °C - 이 이상이면 전 팬 60Hz 강제

    # 정상 운전 목표 온도
    sw_outlet_target: float = 45.0  # °C
    fw_outlet_target: float = 33.0  # °C
    er_temp_target: float = 43.0  # °C

    def check_sw_outlet(self, temp: float) -> Tuple[SafetyLevel, Optional[str]]:
        """SW 출구 온도 확인"""
        if temp >= self.sw_outlet_emergency:
            return SafetyLevel.EMERGENCY, f"SW 출구 온도 위험: {temp}°C (긴급한계: {self.sw_outlet_emergency}°C) - 강제 증속 필요"
        elif temp >= self.sw_outlet_max:
            return SafetyLevel.CRITICAL, f"SW 출구 온도 높음: {temp}°C (한계: {self.sw_outlet_max}°C)"
        elif temp >= self.sw_outlet_target + 2.0:
            return SafetyLevel.WARNING, f"SW 출구 온도 경고: {temp}°C (목표: {self.sw_outlet_target}°C)"
        return SafetyLevel.NORMAL, None

    def check_fw_outlet(self, temp: float) -> Tuple[SafetyLevel, Optional[str]]:
        """FW 출구 온도 확인"""
        if temp > self.fw_outlet_max:
            return SafetyLevel.CRITICAL, f"FW 출구 온도 높음: {temp}°C (한계: {self.fw_outlet_max}°C) - SW펌프 증속 필요"
        elif temp >= self.fw_outlet_target + 2.0:
            return SafetyLevel.WARNING, f"FW 출구 온도 경고: {temp}°C (목표: {self.fw_outlet_target}°C)"
        return SafetyLevel.NORMAL, None

    def check_er_temp(self, temp: float) -> Tuple[SafetyLevel, Optional[str]]:
        """E/R 온도 확인"""
        if temp > self.er_temp_max:
            return SafetyLevel.EMERGENCY, f"E/R 온도 위험: {temp}°C (한계: {self.er_temp_max}°C) - 전 팬 60Hz 강제"
        elif temp >= self.er_temp_target + 2.0:
            return SafetyLevel.WARNING, f"E/R 온도 경고: {temp}°C (목표: {self.er_temp_target}°C)"
        return SafetyLevel.NORMAL, None


@dataclass
class FrequencyLimits:
    """
    주파수 제약조건 (절대 준수)
    """
    min_frequency: float = 40.0  # Hz
    max_frequency: float = 60.0  # Hz
    rated_frequency: float = 60.0  # Hz

    # 학습 허용 범위
    learning_min_deviation: float = 3.0  # ±3Hz 범위 내에서만 학습
    learning_max_deviation: float = 3.0

    # 변화율 제한
    max_frequency_change_per_minute: float = 5.0  # Hz/min - 급격한 변화 금지

    def check_frequency(self, freq: float) -> Tuple[bool, Optional[str]]:
        """주파수 범위 확인"""
        if not (self.min_frequency <= freq <= self.max_frequency):
            return False, f"주파수 범위 위반: {freq}Hz (허용: {self.min_frequency}-{self.max_frequency}Hz)"
        return True, None

    def check_frequency_change(self, current_freq: float, new_freq: float, time_minutes: float = 1.0) -> Tuple[bool, Optional[str]]:
        """주파수 변화율 확인"""
        change = abs(new_freq - current_freq)
        max_allowed_change = self.max_frequency_change_per_minute * time_minutes

        if change > max_allowed_change:
            return False, f"주파수 급변 금지: {change:.1f}Hz in {time_minutes:.1f}min (최대: {max_allowed_change:.1f}Hz)"
        return True, None

    def is_learning_allowed(self, freq: float, target_freq: float = 60.0) -> bool:
        """학습 허용 범위 여부"""
        deviation = abs(freq - target_freq)
        return deviation <= self.learning_max_deviation

    def get_safe_frequency(self, requested_freq: float) -> float:
        """안전한 주파수로 제한"""
        return max(self.min_frequency, min(self.max_frequency, requested_freq))


@dataclass
class OperationCountLimits:
    """운전 대수 제약조건"""
    # SW Pump (3대)
    sw_pump_total: int = 3
    sw_pump_min_running: int = 1
    sw_pump_max_running: int = 2  # 1대는 항상 대기
    sw_pump_min_with_engine: int = 1  # M/E 작동시 최소

    # FW Pump (3대)
    fw_pump_total: int = 3
    fw_pump_min_running: int = 1
    fw_pump_max_running: int = 2
    fw_pump_min_with_engine: int = 1

    # E/R Fan (4대)
    er_fan_total: int = 4
    er_fan_min_running: int = 2  # 최소 2대 운전
    er_fan_max_running: int = 4
    er_fan_min_with_engine: int = 3  # M/E 작동시 최소 3대

    def check_sw_pump_count(self, running_count: int, engine_running: bool = False) -> Tuple[bool, Optional[str]]:
        """SW 펌프 운전 대수 확인"""
        min_required = self.sw_pump_min_with_engine if engine_running else self.sw_pump_min_running

        if running_count < min_required:
            return False, f"SW 펌프 대수 부족: {running_count}대 (최소: {min_required}대)"
        if running_count > self.sw_pump_max_running:
            return False, f"SW 펌프 대수 초과: {running_count}대 (최대: {self.sw_pump_max_running}대)"
        return True, None

    def check_fw_pump_count(self, running_count: int, engine_running: bool = False) -> Tuple[bool, Optional[str]]:
        """FW 펌프 운전 대수 확인"""
        min_required = self.fw_pump_min_with_engine if engine_running else self.fw_pump_min_running

        if running_count < min_required:
            return False, f"FW 펌프 대수 부족: {running_count}대 (최소: {min_required}대)"
        if running_count > self.fw_pump_max_running:
            return False, f"FW 펌프 대수 초과: {running_count}대 (최대: {self.fw_pump_max_running}대)"
        return True, None

    def check_er_fan_count(self, running_count: int, engine_running: bool = False) -> Tuple[bool, Optional[str]]:
        """E/R 팬 운전 대수 확인"""
        min_required = self.er_fan_min_with_engine if engine_running else self.er_fan_min_running

        if running_count < min_required:
            return False, f"E/R 팬 대수 부족: {running_count}대 (최소: {min_required}대)"
        if running_count > self.er_fan_max_running:
            return False, f"E/R 팬 대수 초과: {running_count}대 (최대: {self.er_fan_max_running}대)"
        return True, None


@dataclass
class PressureLimits:
    """압력 제약조건"""
    sw_discharge_min: float = 1.0  # bar - 최소 압력
    sw_discharge_target: float = 2.0  # bar - 목표 압력
    sw_discharge_max: float = 3.0  # bar - 최대 압력

    def check_pressure(self, pressure: float) -> Tuple[SafetyLevel, Optional[str]]:
        """압력 확인"""
        if pressure < self.sw_discharge_min:
            return SafetyLevel.CRITICAL, f"압력 부족: {pressure}bar (최소: {self.sw_discharge_min}bar)"
        elif pressure < self.sw_discharge_target - 0.3:
            return SafetyLevel.WARNING, f"압력 낮음: {pressure}bar (목표: {self.sw_discharge_target}bar)"
        elif pressure > self.sw_discharge_max:
            return SafetyLevel.WARNING, f"압력 높음: {pressure}bar (최대: {self.sw_discharge_max}bar)"
        return SafetyLevel.NORMAL, None


@dataclass
class SafetyConstraints:
    """전체 안전 제약조건"""
    temperature: TemperatureLimits = field(default_factory=TemperatureLimits)
    frequency: FrequencyLimits = field(default_factory=FrequencyLimits)
    operation_count: OperationCountLimits = field(default_factory=OperationCountLimits)
    pressure: PressureLimits = field(default_factory=PressureLimits)

    # 학습 중단 조건
    safety_incident_count: int = 0
    consecutive_efficiency_drop_days: int = 0
    sensor_error_detected: bool = False

    incident_history: List[Dict] = field(default_factory=list)

    def validate_all(self, sensor_data, control_output, engine_running: bool = False) -> Tuple[bool, List[str], SafetyLevel]:
        """전체 안전 제약조건 검증"""
        errors = []
        max_safety_level = SafetyLevel.NORMAL

        # 온도 검증
        level, error = self.temperature.check_sw_outlet((sensor_data['T2'] + sensor_data['T3']) / 2.0)
        if error:
            errors.append(error)
            if level.value > max_safety_level.value:
                max_safety_level = level

        level, error = self.temperature.check_fw_outlet(sensor_data['T5'])
        if error:
            errors.append(error)
            if level.value > max_safety_level.value:
                max_safety_level = level

        level, error = self.temperature.check_er_temp(sensor_data['T6'])
        if error:
            errors.append(error)
            if level.value > max_safety_level.value:
                max_safety_level = level

        # 주파수 검증
        for device, freq in control_output.items():
            valid, error = self.frequency.check_frequency(freq)
            if not valid:
                errors.append(f"{device}: {error}")
                max_safety_level = SafetyLevel.CRITICAL

        # 압력 검증
        level, error = self.pressure.check_pressure(sensor_data['PX1'])
        if error:
            errors.append(error)
            if level.value > max_safety_level.value:
                max_safety_level = level

        return len(errors) == 0, errors, max_safety_level

    def apply_emergency_override(self, sensor_data) -> Dict[str, any]:
        """
        긴급 안전 오버라이드
        학습 불가 영역의 강제 제어
        """
        override = {
            "activated": False,
            "actions": []
        }

        # T2 또는 T3가 48°C 초과 → 강제 증속
        sw_avg = (sensor_data['T2'] + sensor_data['T3']) / 2.0
        if sw_avg >= self.temperature.sw_outlet_max:
            override["activated"] = True
            override["actions"].append({
                "reason": f"SW 출구 온도 {sw_avg:.1f}°C ≥ {self.temperature.sw_outlet_max}°C",
                "action": "SW 펌프 강제 증속 60Hz"
            })

        # E/R 온도 50°C 초과 → 전 팬 60Hz
        if sensor_data['T6'] > self.temperature.er_temp_max:
            override["activated"] = True
            override["actions"].append({
                "reason": f"E/R 온도 {sensor_data['T6']:.1f}°C > {self.temperature.er_temp_max}°C",
                "action": "전 팬 60Hz 강제 구동"
            })

        # T5가 36°C 초과 → SW 펌프 증속
        if sensor_data['T5'] > self.temperature.fw_outlet_max:
            override["activated"] = True
            override["actions"].append({
                "reason": f"FW 출구 온도 {sensor_data['T5']:.1f}°C > {self.temperature.fw_outlet_max}°C",
                "action": "SW 펌프 증속"
            })

        return override

    def should_stop_learning(self) -> Tuple[bool, str]:
        """학습 중단 필요 여부"""
        if self.safety_incident_count > 0:
            return True, f"안전 사고 {self.safety_incident_count}회 발생"

        if self.consecutive_efficiency_drop_days >= 3:
            return True, f"3일 연속 효율 저하"

        if self.sensor_error_detected:
            return True, "센서 오류 감지"

        return False, ""

    def record_safety_incident(self, incident_type: str, description: str) -> None:
        """안전 사고 기록"""
        self.safety_incident_count += 1
        self.incident_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": incident_type,
            "description": description,
            "count": self.safety_incident_count
        })

    def reset_learning_stop_conditions(self) -> None:
        """학습 중단 조건 리셋"""
        self.consecutive_efficiency_drop_days = 0
        self.sensor_error_detected = False
        # 안전 사고 카운트는 리셋하지 않음 (누적 관리)

    def get_constraints_summary(self) -> Dict:
        """제약조건 요약"""
        return {
            "temperature_limits": {
                "SW_outlet_max": f"{self.temperature.sw_outlet_max}°C",
                "FW_outlet_max": f"{self.temperature.fw_outlet_max}°C",
                "ER_temp_max": f"{self.temperature.er_temp_max}°C"
            },
            "frequency_limits": {
                "range": f"{self.frequency.min_frequency}-{self.frequency.max_frequency}Hz",
                "max_change_rate": f"{self.frequency.max_frequency_change_per_minute}Hz/min",
                "learning_tolerance": f"±{self.frequency.learning_max_deviation}Hz"
            },
            "operation_count": {
                "SW_pump": f"{self.operation_count.sw_pump_min_running}-{self.operation_count.sw_pump_max_running}대",
                "FW_pump": f"{self.operation_count.fw_pump_min_running}-{self.operation_count.fw_pump_max_running}대",
                "ER_fan": f"{self.operation_count.er_fan_min_running}-{self.operation_count.er_fan_max_running}대"
            },
            "pressure": {
                "SW_discharge_min": f"{self.pressure.sw_discharge_min}bar"
            },
            "learning_stop_conditions": {
                "safety_incidents": self.safety_incident_count,
                "consecutive_efficiency_drops": self.consecutive_efficiency_drop_days,
                "sensor_error": self.sensor_error_detected
            }
        }


def create_safety_constraints() -> SafetyConstraints:
    """안전 제약조건 생성"""
    return SafetyConstraints()
