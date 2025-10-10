"""
어댑터 베이스 클래스
운영/시뮬레이션 모드 통합 인터페이스
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class SensorData:
    """센서 데이터"""
    T1: float  # SW Inlet
    T2: float  # No.1 Cooler SW Outlet
    T3: float  # No.2 Cooler SW Outlet
    T4: float  # FW Inlet
    T5: float  # FW Outlet
    T6: float  # E/R Temperature
    T7: float  # Outside Air
    PX1: float  # SW Discharge Pressure
    engine_load: float  # Engine Load %


@dataclass
class ControlCommand:
    """제어 명령"""
    sw_pump_count: int
    sw_pump_freq: float
    fw_pump_count: int
    fw_pump_freq: float
    er_fan_count: int
    er_fan_freq: float


@dataclass
class EquipmentStatus:
    """장비 상태"""
    equipment_id: str
    is_running: bool
    frequency: float
    power: float
    status_bits: int = 0


class SensorAdapter(ABC):
    """센서 어댑터 인터페이스"""

    @abstractmethod
    def read_sensors(self) -> SensorData:
        """센서 값 읽기"""
        pass


class EquipmentAdapter(ABC):
    """장비 어댑터 인터페이스"""

    @abstractmethod
    def send_command(self, command: ControlCommand) -> bool:
        """제어 명령 전송"""
        pass

    @abstractmethod
    def get_status(self, equipment_id: str) -> Optional[EquipmentStatus]:
        """장비 상태 읽기"""
        pass


class GPSAdapter(ABC):
    """GPS 어댑터 인터페이스"""

    @abstractmethod
    def get_position(self) -> Dict[str, float]:
        """
        GPS 위치 정보

        Returns:
            {"latitude": float, "longitude": float, "speed": float, "heading": float}
        """
        pass
