"""
시뮬레이션용 어댑터
물리 엔진과 연동
"""

from typing import Dict, Optional
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.adapter.base_adapter import (
    SensorAdapter,
    EquipmentAdapter,
    GPSAdapter,
    SensorData,
    ControlCommand,
    EquipmentStatus
)
from src.simulation.physics_engine import PhysicsEngine, VoyagePattern


class SimSensorAdapter(SensorAdapter):
    """시뮬레이션 센서 어댑터"""

    def __init__(self, physics_engine: PhysicsEngine):
        """
        초기화

        Args:
            physics_engine: 물리 엔진 인스턴스
        """
        self.physics_engine = physics_engine

    def read_sensors(self) -> SensorData:
        """센서 값 읽기 (물리 엔진에서)"""
        return SensorData(
            T1=self.physics_engine.T1,
            T2=self.physics_engine.T2,
            T3=self.physics_engine.T3,
            T4=self.physics_engine.T4,
            T5=self.physics_engine.T5,
            T6=self.physics_engine.T6,
            T7=self.physics_engine.T7,
            PX1=self.physics_engine.PX1,
            engine_load=0.0  # 별도 설정 필요
        )


class SimEquipmentAdapter(EquipmentAdapter):
    """시뮬레이션 장비 어댑터"""

    def __init__(self, physics_engine: PhysicsEngine, voyage_pattern: VoyagePattern):
        """
        초기화

        Args:
            physics_engine: 물리 엔진 인스턴스
            voyage_pattern: 운항 패턴 생성기
        """
        self.physics_engine = physics_engine
        self.voyage_pattern = voyage_pattern
        self.current_command: Optional[ControlCommand] = None
        self.simulation_time = 0  # 초

        # 장비 상태 저장
        self.equipment_status: Dict[str, EquipmentStatus] = {}

    def send_command(self, command: ControlCommand) -> bool:
        """
        제어 명령 전송 (물리 엔진 업데이트)

        Args:
            command: 제어 명령

        Returns:
            성공 여부
        """
        self.current_command = command

        # 엔진 부하 계산
        engine_load = self.voyage_pattern.get_engine_load(self.simulation_time)

        # 환경 조건
        seawater_temp = self.voyage_pattern.get_seawater_temp(self.simulation_time)
        outside_air_temp = self.voyage_pattern.get_outside_air_temp(self.simulation_time)

        # 물리 엔진 스텝 실행
        sensor_values = self.physics_engine.step(
            engine_load=engine_load,
            sw_pump_count=command.sw_pump_count,
            sw_pump_freq=command.sw_pump_freq,
            fw_pump_count=command.fw_pump_count,
            fw_pump_freq=command.fw_pump_freq,
            er_fan_count=command.er_fan_count,
            er_fan_freq=command.er_fan_freq,
            seawater_temp=seawater_temp,
            outside_air_temp=outside_air_temp
        )

        # 장비 상태 업데이트
        self._update_equipment_status(command)

        # 시뮬레이션 시간 증가
        self.simulation_time += 1

        return True

    def _update_equipment_status(self, command: ControlCommand):
        """장비 상태 업데이트"""
        # SW 펌프
        for i in range(1, 4):
            eq_id = f"SW-P{i}"
            is_running = i <= command.sw_pump_count
            power = self.physics_engine.sw_pump.get_power(command.sw_pump_freq) if is_running else 0.0

            self.equipment_status[eq_id] = EquipmentStatus(
                equipment_id=eq_id,
                is_running=is_running,
                frequency=command.sw_pump_freq if is_running else 0.0,
                power=power
            )

        # FW 펌프
        for i in range(1, 4):
            eq_id = f"FW-P{i}"
            is_running = i <= command.fw_pump_count
            power = self.physics_engine.fw_pump.get_power(command.fw_pump_freq) if is_running else 0.0

            self.equipment_status[eq_id] = EquipmentStatus(
                equipment_id=eq_id,
                is_running=is_running,
                frequency=command.fw_pump_freq if is_running else 0.0,
                power=power
            )

        # E/R 팬
        for i in range(1, 5):
            eq_id = f"ER-F{i}"
            is_running = i <= command.er_fan_count
            power = self.physics_engine.er_fan.get_power(command.er_fan_freq) if is_running else 0.0

            self.equipment_status[eq_id] = EquipmentStatus(
                equipment_id=eq_id,
                is_running=is_running,
                frequency=command.er_fan_freq if is_running else 0.0,
                power=power
            )

    def get_status(self, equipment_id: str) -> Optional[EquipmentStatus]:
        """
        장비 상태 읽기

        Args:
            equipment_id: 장비 ID (예: "SW-P1")

        Returns:
            장비 상태
        """
        return self.equipment_status.get(equipment_id)

    def reset(self):
        """시뮬레이션 리셋"""
        self.simulation_time = 0
        self.current_command = None
        self.equipment_status.clear()
        self.physics_engine.reset()


class SimGPSAdapter(GPSAdapter):
    """시뮬레이션 GPS 어댑터"""

    def __init__(
        self,
        latitude: float = 37.5,
        longitude: float = 126.9,
        speed: float = 20.0,
        heading: float = 90.0
    ):
        """
        초기화

        Args:
            latitude: 위도
            longitude: 경도
            speed: 속도 (knots)
            heading: 방위 (degrees)
        """
        self.latitude = latitude
        self.longitude = longitude
        self.speed = speed
        self.heading = heading

    def get_position(self) -> Dict[str, float]:
        """
        GPS 위치 정보

        Returns:
            위치 정보 딕셔너리
        """
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "speed": self.speed,
            "heading": self.heading
        }

    def set_position(self, latitude: float, longitude: float, speed: float, heading: float):
        """위치 설정 (시뮬레이션용)"""
        self.latitude = latitude
        self.longitude = longitude
        self.speed = speed
        self.heading = heading
