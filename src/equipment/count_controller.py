"""
ESS AI System - 펌프 및 팬 대수 제어
- 펌프: 엔진 부하 기준 (30% 기준)
- 팬: 온도 기준 (T6 42~44°C 유지)
- SW/FW 펌프 동기화 100%
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from enum import Enum

from .equipment_manager import EquipmentManager, EquipmentType, EquipmentStatus


class CountChangeReason(Enum):
    """대수 변경 이유"""
    ENGINE_LOAD_INCREASE = "engine_load_increase"
    ENGINE_LOAD_DECREASE = "engine_load_decrease"
    TEMPERATURE_HIGH = "temperature_high"
    TEMPERATURE_LOW = "temperature_low"
    ROTATION = "rotation"
    BACKUP = "backup"


@dataclass
class CountControlDecision:
    """대수 제어 결정"""
    sw_pump_count: int
    fw_pump_count: int
    er_fan_count: int

    sw_pump_ids: List[str]
    fw_pump_ids: List[str]
    er_fan_ids: List[str]

    change_reason: str = ""
    overlap_transition: bool = False  # 중첩 전환 필요 여부


class CountController:
    """
    대수 제어기
    """

    def __init__(self, equipment_manager: EquipmentManager):
        self.equipment_manager = equipment_manager

        # 펌프 대수 (엔진 부하 기준)
        self.engine_load_threshold = 30.0  # %
        self.pump_count_low_load = 1  # 저부하시 1대
        self.pump_count_high_load = 2  # 고부하시 2대

        # 팬 대수 및 주파수 (온도 기준)
        self.t6_target_min = 42.0  # °C
        self.t6_target_max = 44.0  # °C
        self.fan_min_count = 2  # 최소 2대
        self.fan_max_count = 4  # 최대 4대

        # 전환 중첩 시간
        self.overlap_duration_seconds = 30.0

        # 로테이션 주기
        self.pump_rotation_interval_hours = 24.0
        self.fan_rotation_interval_hours = 6.0

        # 마지막 로테이션 시간
        self.last_pump_rotation: Optional[datetime] = None
        self.last_fan_rotation: Optional[datetime] = None

    def decide_pump_count(self, engine_load_percent: float) -> int:
        """
        펌프 대수 결정 (엔진 부하 기준)

        < 30%: 1대
        >= 30%: 2대
        """
        if engine_load_percent < self.engine_load_threshold:
            return self.pump_count_low_load
        else:
            return self.pump_count_high_load

    def decide_fan_count(
        self,
        t6_temperature: float,
        current_count: int,
        current_frequency: float
    ) -> Tuple[int, str]:
        """
        팬 대수 결정 (온도 기준)

        우선순위:
        1. 주파수 조절 (40~60Hz)
        2. 대수 조절 (2~4대)

        Returns: (권장 대수, 이유)
        """
        # 온도가 너무 높음
        if t6_temperature > self.t6_target_max:
            # 주파수가 이미 최대(60Hz)이면 대수 증가
            if current_frequency >= 59.0 and current_count < self.fan_max_count:
                return current_count + 1, "온도 높음 + 주파수 한계 → 대수 증가"
            else:
                return current_count, "주파수로 제어"

        # 온도가 너무 낮음
        elif t6_temperature < self.t6_target_min:
            # 주파수가 이미 최소(40Hz)이면 대수 감소
            if current_frequency <= 41.0 and current_count > self.fan_min_count:
                return current_count - 1, "온도 낮음 + 주파수 한계 → 대수 감소"
            else:
                return current_count, "주파수로 제어"

        # 정상 범위
        else:
            return current_count, "온도 정상"

    def compute_count_control(
        self,
        engine_load_percent: float,
        t6_temperature: float,
        current_fan_frequency: float
    ) -> CountControlDecision:
        """
        전체 대수 제어 계산

        핵심 규칙:
        - SW/FW 펌프는 항상 동일 대수
        - 팬은 최소 2대 보장
        """
        # 현재 운전 중인 장비
        current_sw = self.equipment_manager.get_running_equipments(EquipmentType.SW_PUMP)
        current_fw = self.equipment_manager.get_running_equipments(EquipmentType.FW_PUMP)
        current_fans = self.equipment_manager.get_running_equipments(EquipmentType.ER_FAN)

        # 펌프 대수 결정
        target_pump_count = self.decide_pump_count(engine_load_percent)

        # 팬 대수 결정
        target_fan_count, fan_reason = self.decide_fan_count(
            t6_temperature,
            len(current_fans),
            current_fan_frequency
        )

        # 펌프 선택
        sw_pump_ids = self._select_pumps(EquipmentType.SW_PUMP, target_pump_count)
        fw_pump_ids = self._select_pumps(EquipmentType.FW_PUMP, target_pump_count)

        # 팬 선택
        fan_ids = self._select_fans(target_fan_count)

        # 변경 이유
        reason = []
        if len(current_sw) != target_pump_count:
            if target_pump_count > len(current_sw):
                reason.append(f"엔진부하 {engine_load_percent:.0f}% → 펌프 증가 ({len(current_sw)}→{target_pump_count}대)")
            else:
                reason.append(f"엔진부하 {engine_load_percent:.0f}% → 펌프 감소 ({len(current_sw)}→{target_pump_count}대)")

        if len(current_fans) != target_fan_count:
            reason.append(f"T6={t6_temperature:.1f}°C → 팬 {len(current_fans)}→{target_fan_count}대: {fan_reason}")

        decision = CountControlDecision(
            sw_pump_count=target_pump_count,
            fw_pump_count=target_pump_count,  # 항상 SW와 동일
            er_fan_count=target_fan_count,
            sw_pump_ids=sw_pump_ids,
            fw_pump_ids=fw_pump_ids,
            er_fan_ids=fan_ids,
            change_reason="; ".join(reason) if reason else "현재 대수 유지",
            overlap_transition=len(current_sw) != target_pump_count  # 펌프 대수 변경시 중첩 전환
        )

        return decision

    def _select_pumps(self, pump_type: EquipmentType, target_count: int) -> List[str]:
        """펌프 선택 (운전시간 균등화)"""
        running = self.equipment_manager.get_running_equipments(pump_type)
        current_count = len(running)

        if current_count == target_count:
            # 현재 대수 유지
            return [eq.equipment_id for eq in running]

        elif current_count < target_count:
            # 대수 증가 - 운전시간 적은 펌프 추가
            selected = [eq.equipment_id for eq in running]

            for _ in range(target_count - current_count):
                next_pump = self.equipment_manager.select_equipment_to_start(pump_type)
                if next_pump:
                    selected.append(next_pump.equipment_id)

            return selected

        else:
            # 대수 감소 - 운전시간 많은 펌프 정지
            to_stop = self.equipment_manager.select_equipment_to_stop(pump_type)
            selected = [eq.equipment_id for eq in running if eq.equipment_id != to_stop.equipment_id]
            return selected[:target_count]

    def _select_fans(self, target_count: int) -> List[str]:
        """팬 선택 (운전시간 균등화)"""
        return self._select_pumps(EquipmentType.ER_FAN, target_count)

    def check_rotation_needed(self) -> Dict[str, bool]:
        """로테이션 필요 여부"""
        now = datetime.now()

        pump_rotation_needed = False
        if self.last_pump_rotation is None:
            pump_rotation_needed = True
        else:
            hours_since = (now - self.last_pump_rotation).total_seconds() / 3600.0
            pump_rotation_needed = hours_since >= self.pump_rotation_interval_hours

        fan_rotation_needed = False
        if self.last_fan_rotation is None:
            fan_rotation_needed = True
        else:
            hours_since = (now - self.last_fan_rotation).total_seconds() / 3600.0
            fan_rotation_needed = hours_since >= self.fan_rotation_interval_hours

        return {
            "pump_rotation_needed": pump_rotation_needed,
            "fan_rotation_needed": fan_rotation_needed
        }

    def execute_rotation(self, equipment_type: str) -> bool:
        """
        로테이션 실행
        - 펌프: 24시간 주기
        - 팬: 6시간 주기
        """
        if equipment_type == "pump":
            # SW 펌프 로테이션
            sw_running = self.equipment_manager.get_running_equipments(EquipmentType.SW_PUMP)
            if sw_running:
                to_stop = self.equipment_manager.select_equipment_to_stop(EquipmentType.SW_PUMP)
                to_start = self.equipment_manager.select_equipment_to_start(EquipmentType.SW_PUMP)

                if to_stop and to_start:
                    print(f"🔄 SW 펌프 로테이션: {to_stop.equipment_id} → {to_start.equipment_id}")

            # FW 펌프 로테이션 (SW와 동기화)
            fw_running = self.equipment_manager.get_running_equipments(EquipmentType.FW_PUMP)
            if fw_running:
                to_stop = self.equipment_manager.select_equipment_to_stop(EquipmentType.FW_PUMP)
                to_start = self.equipment_manager.select_equipment_to_start(EquipmentType.FW_PUMP)

                if to_stop and to_start:
                    print(f"🔄 FW 펌프 로테이션: {to_stop.equipment_id} → {to_start.equipment_id}")

            self.last_pump_rotation = datetime.now()
            return True

        elif equipment_type == "fan":
            # 팬 로테이션
            running = self.equipment_manager.get_running_equipments(EquipmentType.ER_FAN)
            if running:
                to_stop = self.equipment_manager.select_equipment_to_stop(EquipmentType.ER_FAN)
                to_start = self.equipment_manager.select_equipment_to_start(EquipmentType.ER_FAN)

                if to_stop and to_start:
                    print(f"🔄 팬 로테이션: {to_stop.equipment_id} → {to_start.equipment_id}")

            self.last_fan_rotation = datetime.now()
            return True

        return False


def create_count_controller(equipment_manager: EquipmentManager) -> CountController:
    """대수 제어기 생성"""
    return CountController(equipment_manager)
