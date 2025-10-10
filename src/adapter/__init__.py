"""
어댑터 모듈
운영/시뮬레이션 모드 통합 인터페이스
"""

from .base_adapter import (
    SensorAdapter,
    EquipmentAdapter,
    GPSAdapter,
    SensorData,
    ControlCommand,
    EquipmentStatus
)

from .sim_adapter import (
    SimSensorAdapter,
    SimEquipmentAdapter,
    SimGPSAdapter
)

from .plc_adapter import (
    PLCSensorAdapter,
    VFDEquipmentAdapter,
    HardwareGPSAdapter
)

__all__ = [
    # Base
    'SensorAdapter',
    'EquipmentAdapter',
    'GPSAdapter',
    'SensorData',
    'ControlCommand',
    'EquipmentStatus',

    # Simulation
    'SimSensorAdapter',
    'SimEquipmentAdapter',
    'SimGPSAdapter',

    # Production
    'PLCSensorAdapter',
    'VFDEquipmentAdapter',
    'HardwareGPSAdapter',
]
