"""
ESS AI System - 장비 운전시간 추적 및 관리
운전시간 균등화 시스템 (Load Balancing)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum
import json


class EquipmentStatus(Enum):
    """장비 상태"""
    RUNNING = "running"
    STOPPED = "stopped"
    STANDBY = "standby"
    FAULT = "fault"
    MAINTENANCE = "maintenance"


class EquipmentType(Enum):
    """장비 타입"""
    SW_PUMP = "sw_pump"
    FW_PUMP = "fw_pump"
    ER_FAN = "er_fan"


@dataclass
class EquipmentRuntime:
    """장비 운전시간 데이터"""
    equipment_id: str
    equipment_type: EquipmentType

    # 운전시간
    total_runtime_hours: float = 0.0  # 총 누적 운전시간
    daily_runtime_hours: float = 0.0  # 일일 운전시간
    continuous_runtime_hours: float = 0.0  # 연속 운전시간

    # 상태
    status: EquipmentStatus = EquipmentStatus.STOPPED
    last_start_time: Optional[datetime] = None
    last_stop_time: Optional[datetime] = None

    # 카운트
    start_count: int = 0  # 기동 횟수
    fault_count: int = 0  # 고장 횟수

    # 고장 이력
    last_fault_time: Optional[datetime] = None

    # 정비
    last_maintenance_hours: float = 0.0  # 마지막 정비 시점 운전시간
    maintenance_interval_hours: float = 1000.0  # 정비 주기

    def update_runtime(self, current_time: datetime) -> None:
        """운전시간 업데이트"""
        if self.status == EquipmentStatus.RUNNING and self.last_start_time:
            elapsed = (current_time - self.last_start_time).total_seconds() / 3600.0
            self.continuous_runtime_hours = elapsed

    def start(self, current_time: datetime) -> None:
        """기동"""
        self.status = EquipmentStatus.RUNNING
        self.last_start_time = current_time
        self.start_count += 1

    def stop(self, current_time: datetime) -> None:
        """정지"""
        if self.status == EquipmentStatus.RUNNING and self.last_start_time:
            runtime = (current_time - self.last_start_time).total_seconds() / 3600.0
            self.total_runtime_hours += runtime
            self.daily_runtime_hours += runtime

        self.status = EquipmentStatus.STOPPED
        self.last_stop_time = current_time
        self.continuous_runtime_hours = 0.0

    def needs_maintenance(self) -> bool:
        """정비 필요 여부"""
        hours_since_maintenance = self.total_runtime_hours - self.last_maintenance_hours
        return hours_since_maintenance >= self.maintenance_interval_hours

    def reset_daily_runtime(self) -> None:
        """일일 운전시간 리셋"""
        self.daily_runtime_hours = 0.0


class EquipmentManager:
    """장비 관리자"""

    def __init__(self):
        self.equipments: Dict[str, EquipmentRuntime] = {}
        self._initialize_equipments()

    def _initialize_equipments(self) -> None:
        """장비 초기화"""
        # SW Pumps
        for i in range(1, 4):
            self.equipments[f"SW_P{i}"] = EquipmentRuntime(
                equipment_id=f"SW_P{i}",
                equipment_type=EquipmentType.SW_PUMP
            )

        # FW Pumps
        for i in range(1, 4):
            self.equipments[f"FW_P{i}"] = EquipmentRuntime(
                equipment_id=f"FW_P{i}",
                equipment_type=EquipmentType.FW_PUMP
            )

        # ER Fans
        for i in range(1, 5):
            self.equipments[f"FAN_{i}"] = EquipmentRuntime(
                equipment_id=f"FAN_{i}",
                equipment_type=EquipmentType.ER_FAN
            )

    def get_equipment(self, equipment_id: str) -> Optional[EquipmentRuntime]:
        """장비 조회"""
        return self.equipments.get(equipment_id)

    def get_equipments_by_type(self, eq_type: EquipmentType) -> List[EquipmentRuntime]:
        """타입별 장비 목록"""
        return [eq for eq in self.equipments.values() if eq.equipment_type == eq_type]

    def get_running_equipments(self, eq_type: EquipmentType) -> List[EquipmentRuntime]:
        """운전 중인 장비 목록"""
        return [eq for eq in self.get_equipments_by_type(eq_type)
                if eq.status == EquipmentStatus.RUNNING]

    def get_available_equipments(self, eq_type: EquipmentType) -> List[EquipmentRuntime]:
        """가용 장비 목록 (정상 상태)"""
        now = datetime.now()
        return [eq for eq in self.get_equipments_by_type(eq_type)
                if eq.status in [EquipmentStatus.STOPPED, EquipmentStatus.STANDBY]
                and not (eq.last_fault_time and (now - eq.last_fault_time).total_seconds() < 86400)]

    def select_equipment_to_start(self, eq_type: EquipmentType) -> Optional[EquipmentRuntime]:
        """
        기동할 장비 선택
        우선순위:
        1. 누적 운전시간이 가장 적은 장비
        2. 마지막 정지 시간이 오래된 장비
        3. 장비 번호 순서
        """
        available = self.get_available_equipments(eq_type)
        if not available:
            return None

        # 누적 운전시간 기준 정렬 (적은 순)
        available.sort(key=lambda eq: (
            eq.total_runtime_hours,
            -(eq.last_stop_time.timestamp() if eq.last_stop_time else 0),
            eq.equipment_id
        ))

        return available[0]

    def select_equipment_to_stop(self, eq_type: EquipmentType) -> Optional[EquipmentRuntime]:
        """
        정지할 장비 선택
        우선순위:
        1. 누적 운전시간이 가장 많은 장비
        2. 연속 운전시간이 긴 장비
        3. 장비 번호 역순
        """
        running = self.get_running_equipments(eq_type)
        if not running:
            return None

        # 누적 운전시간 기준 정렬 (많은 순)
        running.sort(key=lambda eq: (
            -eq.total_runtime_hours,
            -eq.continuous_runtime_hours,
            eq.equipment_id
        ), reverse=True)

        return running[0]

    def calculate_runtime_balance_score(self, eq_type: EquipmentType) -> float:
        """
        운전시간 균등화 점수 (100점 만점)
        편차가 적을수록 높은 점수
        """
        equipments = self.get_equipments_by_type(eq_type)
        if len(equipments) < 2:
            return 100.0

        runtimes = [eq.total_runtime_hours for eq in equipments]
        avg_runtime = sum(runtimes) / len(runtimes)

        if avg_runtime == 0:
            return 100.0

        variance = sum([(r - avg_runtime) ** 2 for r in runtimes]) / len(runtimes)
        std_dev = variance ** 0.5

        # 표준편차를 점수로 변환 (작을수록 높은 점수)
        cv = (std_dev / avg_runtime) * 100  # 변동계수 (%)
        score = max(0, 100 - cv * 10)  # CV 10%당 100점 감점

        return min(100.0, score)

    def get_runtime_statistics(self, eq_type: EquipmentType) -> Dict:
        """운전시간 통계"""
        equipments = self.get_equipments_by_type(eq_type)
        runtimes = [eq.total_runtime_hours for eq in equipments]

        return {
            "equipment_type": eq_type.value,
            "total_equipments": len(equipments),
            "running_count": len([eq for eq in equipments if eq.status == EquipmentStatus.RUNNING]),
            "average_runtime": sum(runtimes) / len(runtimes) if runtimes else 0,
            "max_runtime": max(runtimes) if runtimes else 0,
            "min_runtime": min(runtimes) if runtimes else 0,
            "runtime_deviation": max(runtimes) - min(runtimes) if runtimes else 0,
            "balance_score": self.calculate_runtime_balance_score(eq_type)
        }


def create_equipment_manager() -> EquipmentManager:
    """장비 관리자 생성"""
    return EquipmentManager()
