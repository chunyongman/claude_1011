"""
ESS AI System - Sensor Data Models
센서 데이터 모델 정의 및 유효성 검증
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import numpy as np
from enum import Enum


class SensorStatus(Enum):
    """센서 상태"""
    NORMAL = "normal"
    OUT_OF_RANGE = "out_of_range"
    RAPID_CHANGE = "rapid_change"
    SIGMA_VIOLATION = "sigma_violation"
    ERROR = "error"


@dataclass
class SensorConfig:
    """센서 설정"""
    description: str
    plc_tag: str
    unit: str
    range: Tuple[float, float]
    sigma_multiplier: float = 3.0
    max_change_rate: float = 2.0  # per minute
    normal_range: Optional[Tuple[float, float]] = None


@dataclass
class SensorReading:
    """센서 측정값"""
    value: float
    timestamp: datetime
    status: SensorStatus = SensorStatus.NORMAL
    previous_value: Optional[float] = None
    error_message: Optional[str] = None

    def validate_range(self, sensor_config: SensorConfig) -> bool:
        """범위 검증"""
        min_val, max_val = sensor_config.range
        if not (min_val <= self.value <= max_val):
            self.status = SensorStatus.OUT_OF_RANGE
            self.error_message = f"Value {self.value}{sensor_config.unit} out of range [{min_val}, {max_val}]"
            return False
        return True

    def validate_change_rate(self, sensor_config: SensorConfig, time_diff_minutes: float) -> bool:
        """변화율 검증"""
        if self.previous_value is None:
            return True

        change = abs(self.value - self.previous_value)
        max_change = sensor_config.max_change_rate * time_diff_minutes

        if change > max_change:
            self.status = SensorStatus.RAPID_CHANGE
            self.error_message = f"Rapid change: {change:.2f}{sensor_config.unit} in {time_diff_minutes:.1f}min (max: {max_change:.2f})"
            return False
        return True


@dataclass
class CoolingSystemTemperatures:
    """냉각 시스템 온도 센서"""
    T1: SensorReading  # LT F.W Cooler S.W Inlet
    T2: SensorReading  # No.1 Cooler S.W Outlet
    T3: SensorReading  # No.2 Cooler S.W Outlet
    T4: SensorReading  # LT F.W Cooler F.W Inlet
    T5: SensorReading  # LT F.W Cooler F.W Outlet

    def validate_heat_exchange(self) -> Tuple[bool, Optional[str]]:
        """
        열교환 원리 검증
        - T1 < T2/T3 < 49°C (해수 가열)
        - T4 > T5 (담수 냉각)
        - T4 < 48°C (담수 입구 상한)
        """
        errors = []

        # 해수 가열 검증
        if self.T2.value <= self.T1.value:
            errors.append(f"Heat exchange error: T2({self.T2.value}°C) <= T1({self.T1.value}°C)")

        if self.T3.value <= self.T1.value:
            errors.append(f"Heat exchange error: T3({self.T3.value}°C) <= T1({self.T1.value}°C)")

        if self.T2.value >= 49.0:
            errors.append(f"SW outlet temp too high: T2={self.T2.value}°C (limit: 49°C)")

        if self.T3.value >= 49.0:
            errors.append(f"SW outlet temp too high: T3={self.T3.value}°C (limit: 49°C)")

        # 담수 냉각 검증
        if self.T5.value >= self.T4.value:
            errors.append(f"FW cooling error: T5({self.T5.value}°C) >= T4({self.T4.value}°C)")

        if self.T4.value >= 48.0:
            errors.append(f"FW inlet temp too high: T4={self.T4.value}°C (limit: 48°C)")

        if errors:
            return False, "; ".join(errors)
        return True, None

    def calculate_heat_exchange_efficiency(self) -> float:
        """열교환 효율 계산"""
        # 해수 온도 상승
        sw_temp_rise = ((self.T2.value + self.T3.value) / 2.0) - self.T1.value
        # 담수 온도 하강
        fw_temp_drop = self.T4.value - self.T5.value

        if sw_temp_rise > 0:
            efficiency = (fw_temp_drop / sw_temp_rise) * 100.0
            return min(100.0, max(0.0, efficiency))
        return 0.0


@dataclass
class VentilationSystemTemperatures:
    """환기 시스템 온도 센서"""
    T6: SensorReading  # E/R Upper Deck (Inside)
    T7: SensorReading  # Engine Casing Outside (Ambient)

    def validate_temperatures(self) -> Tuple[bool, Optional[str]]:
        """온도 관계 검증"""
        errors = []

        # T6 정상 범위 (42-44°C)
        if not (42.0 <= self.T6.value <= 44.0):
            if self.T6.value > 44.0:
                errors.append(f"E/R temp high: T6={self.T6.value}°C (normal: 42-44°C)")

        # T6 > T7 확인 (엔진룸이 외기보다 따뜻해야 함)
        if self.T6.value <= self.T7.value:
            errors.append(f"E/R temp anomaly: T6({self.T6.value}°C) <= T7({self.T7.value}°C)")

        if errors:
            return False, "; ".join(errors)
        return True, None

    def get_temperature_difference(self) -> float:
        """엔진룸-외기 온도차"""
        return self.T6.value - self.T7.value


@dataclass
class PressureData:
    """압력 데이터"""
    PX1: SensorReading  # SW Pump Discharge Manifold

    def validate_pressure(self) -> Tuple[bool, Optional[str]]:
        """압력 검증 (최소 1.0 bar)"""
        if self.PX1.value < 1.0:
            return False, f"Pressure too low: {self.PX1.value} bar (min: 1.0 bar)"
        return True, None


@dataclass
class OperatingConditions:
    """운전 조건"""
    engine_load: float  # %
    gps_latitude: float
    gps_longitude: float
    gps_speed: float  # knots
    utc_time: datetime

    def get_season(self) -> str:
        """계절 분류 (북반구 기준)"""
        month = self.utc_time.month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "autumn"

    def get_region(self) -> str:
        """지역 분류"""
        if -23.5 <= self.gps_latitude <= 23.5:
            return "tropical"
        elif abs(self.gps_latitude) > 66.5:
            return "polar"
        else:
            return "temperate"

    def is_navigation(self) -> bool:
        """항해 중 여부"""
        return self.gps_speed > 2.0  # 2 knots 이상


@dataclass
class SystemSensorData:
    """전체 시스템 센서 데이터"""
    cooling: CoolingSystemTemperatures
    ventilation: VentilationSystemTemperatures
    pressure: PressureData
    operating: OperatingConditions
    timestamp: datetime = field(default_factory=datetime.now)

    def validate_all(self) -> Tuple[bool, List[str]]:
        """전체 시스템 검증"""
        errors = []

        # 열교환 검증
        valid, error = self.cooling.validate_heat_exchange()
        if not valid:
            errors.append(error)

        # 환기 온도 검증
        valid, error = self.ventilation.validate_temperatures()
        if not valid:
            errors.append(error)

        # 압력 검증
        valid, error = self.pressure.validate_pressure()
        if not valid:
            errors.append(error)

        return len(errors) == 0, errors

    def get_system_state_summary(self) -> Dict:
        """시스템 상태 요약"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cooling": {
                "SW_inlet": self.cooling.T1.value,
                "SW_outlet_avg": (self.cooling.T2.value + self.cooling.T3.value) / 2.0,
                "FW_inlet": self.cooling.T4.value,
                "FW_outlet": self.cooling.T5.value,
                "heat_exchange_efficiency": self.cooling.calculate_heat_exchange_efficiency()
            },
            "ventilation": {
                "ER_temp": self.ventilation.T6.value,
                "ambient_temp": self.ventilation.T7.value,
                "temp_diff": self.ventilation.get_temperature_difference()
            },
            "pressure": {
                "SW_discharge": self.pressure.PX1.value
            },
            "operating": {
                "engine_load": self.operating.engine_load,
                "season": self.operating.get_season(),
                "region": self.operating.get_region(),
                "is_navigation": self.operating.is_navigation(),
                "gps_speed": self.operating.gps_speed
            }
        }


class SigmaFilter:
    """3-시그마 필터"""

    def __init__(self, window_size: int = 30):
        self.window_size = window_size
        self.history: Dict[str, List[float]] = {}

    def add_value(self, sensor_id: str, value: float) -> None:
        """값 추가"""
        if sensor_id not in self.history:
            self.history[sensor_id] = []

        self.history[sensor_id].append(value)
        if len(self.history[sensor_id]) > self.window_size:
            self.history[sensor_id].pop(0)

    def check_sigma_violation(self, sensor_id: str, value: float, sigma_multiplier: float = 3.0) -> Tuple[bool, Optional[str]]:
        """시그마 위반 검사"""
        if sensor_id not in self.history or len(self.history[sensor_id]) < 10:
            return True, None

        values = np.array(self.history[sensor_id])
        mean = np.mean(values)
        std = np.std(values)

        if std > 0:
            deviation = abs(value - mean)
            threshold = sigma_multiplier * std

            if deviation > threshold:
                return False, f"Sigma violation: {value:.2f} (mean: {mean:.2f}, std: {std:.2f}, threshold: {threshold:.2f})"

        return True, None
