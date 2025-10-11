"""
HMI 상태 관리자
운전 모드, 긴급 정지, 알람 상태를 관리합니다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime, timedelta
import time
import sys
import os

# GPS 모듈 import
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.gps.gps_processor import GPSProcessor, GPSData, EnvironmentClassification
from src.diagnostics.vfd_monitor import VFDMonitor, VFDDiagnostic, DanfossStatusBits, VFDStatus


class ControlMode(Enum):
    """제어 모드"""
    FIXED_60HZ = "60Hz 고정"
    AI_CONTROL = "AI 제어"


class AlarmPriority(Enum):
    """알람 우선순위"""
    CRITICAL = "CRITICAL"  # Red
    WARNING = "WARNING"    # Yellow
    INFO = "INFO"          # Blue


class ForceMode60HzState(Enum):
    """60Hz 강제 전환 상태"""
    NORMAL = "NORMAL"
    FORCING = "FORCING"
    FORCED = "FORCED"


@dataclass
class EquipmentGroup:
    """장비 그룹"""
    name: str
    control_mode: ControlMode = ControlMode.AI_CONTROL
    target_frequency: float = 60.0
    actual_frequencies: Dict[str, float] = field(default_factory=dict)

    def get_avg_actual_frequency(self) -> float:
        """실제 주파수 평균 계산"""
        if not self.actual_frequencies:
            return 0.0
        return sum(self.actual_frequencies.values()) / len(self.actual_frequencies)

    def get_max_deviation(self) -> float:
        """최대 편차 계산"""
        if not self.actual_frequencies:
            return 0.0
        deviations = [abs(freq - self.target_frequency) for freq in self.actual_frequencies.values()]
        return max(deviations)


@dataclass
class Alarm:
    """알람 정보"""
    timestamp: datetime
    priority: AlarmPriority
    equipment: str
    message: str
    acknowledged: bool = False

    def get_color(self) -> str:
        """알람 색상 반환"""
        if self.priority == AlarmPriority.CRITICAL:
            return "red"
        elif self.priority == AlarmPriority.WARNING:
            return "yellow"
        else:
            return "blue"


class HMIStateManager:
    """HMI 상태 관리자"""

    def __init__(self):
        """초기화"""
        # 장비 그룹 초기화
        self.groups: Dict[str, EquipmentGroup] = {
            "SW_PUMPS": EquipmentGroup(name="SW 펌프"),
            "FW_PUMPS": EquipmentGroup(name="FW 펌프"),
            "ER_FANS": EquipmentGroup(name="E/R 팬")
        }

        # 60Hz 강제 전환 상태
        self.force_60hz_state = ForceMode60HzState.NORMAL
        self.force_60hz_start_time: Optional[float] = None
        self.force_60hz_duration = 30.0  # 30초 점진적 전환
        self.force_60hz_completed = False  # 60Hz 강제 전환 완료 플래그

        # 알람 리스트
        self.alarms: List[Alarm] = []
        self.max_alarms = 100  # 최대 알람 저장 개수

        # 시스템 시작 시간 (실제 운영 시 데이터베이스나 파일에서 로드)
        # 현재는 시뮬레이션: 8개월 전으로 설정
        self.system_start_time = datetime.now() - timedelta(days=8*30)  # 8개월 전
        self.deployment_date = datetime.now() - timedelta(days=8*30)  # 배포일

        # 학습 진행 상태 (8개월 운영 기준 시뮬레이션 데이터)
        # 실제 운영 시 데이터베이스나 ML 모듈에서 로드
        self.learning_progress = {
            "temperature_prediction_accuracy": 82.5,  # 8개월차: Stage 2 단계
            "optimization_accuracy": 79.3,
            "average_energy_savings": 49.8,
            "total_learning_hours": 5760.0,  # 8개월 * 30일 * 24시간
            "last_learning_time": datetime.now() - timedelta(hours=1)  # 1시간 전 마지막 학습
        }

        # GPS 프로세서 초기화
        self.gps_processor = GPSProcessor()
        self.current_environment: Optional[EnvironmentClassification] = None
        self.last_gps_update: Optional[datetime] = None

        # VFD 모니터 초기화
        self.vfd_monitor = VFDMonitor()
        self.current_vfd_diagnostics: Dict[str, VFDDiagnostic] = {}

    def set_control_mode(self, group_name: str, mode: ControlMode):
        """제어 모드 설정"""
        if group_name in self.groups:
            # 디버깅: 모드 변경 로그
            old_mode = self.groups[group_name].control_mode
            if old_mode != mode:
                print(f"[HMI] {group_name} 모드 변경: {old_mode.value} -> {mode.value}")
            self.groups[group_name].control_mode = mode

    def update_target_frequency(self, group_name: str, frequency: float):
        """목표 주파수 업데이트"""
        if group_name in self.groups:
            self.groups[group_name].target_frequency = frequency

    def update_actual_frequency(self, group_name: str, equipment_id: str, frequency: float):
        """실제 주파수 업데이트"""
        if group_name in self.groups:
            self.groups[group_name].actual_frequencies[equipment_id] = frequency

    def get_deviation_status(self, group_name: str) -> str:
        """편차 상태 반환 (Green/Yellow/Red)"""
        if group_name not in self.groups:
            return "Gray"

        deviation = self.groups[group_name].get_max_deviation()

        if deviation < 0.3:
            return "Green"
        elif deviation < 0.5:
            return "Yellow"
        else:
            return "Red"

    def start_force_60hz(self):
        """60Hz 강제 전환 시작"""
        if self.force_60hz_state == ForceMode60HzState.NORMAL:
            self.force_60hz_state = ForceMode60HzState.FORCING
            self.force_60hz_start_time = time.time()

            # 60Hz 강제 전환 알람 추가
            self.add_alarm(
                priority=AlarmPriority.CRITICAL,
                equipment="SYSTEM",
                message="60Hz 강제 전환 시작 - 30초 점진적 전환 중"
            )

    def update_force_60hz(self):
        """60Hz 강제 전환 상태 업데이트"""
        if self.force_60hz_state == ForceMode60HzState.FORCING:
            if self.force_60hz_start_time is None:
                return

            elapsed = time.time() - self.force_60hz_start_time

            if elapsed >= self.force_60hz_duration:
                # 60Hz 강제 전환 완료 (한 번만 실행)
                if not self.force_60hz_completed:
                    print(f"[HMI] 60Hz 강제 전환 완료 - 모든 그룹을 60Hz 고정으로 전환")
                    self.force_60hz_state = ForceMode60HzState.FORCED
                    self.force_60hz_completed = True

                    # 모든 그룹을 60Hz 고정으로 설정
                    for group_name, group in self.groups.items():
                        print(f"[HMI] 60Hz 강제 전환: {group_name} -> 60Hz 고정")
                        group.control_mode = ControlMode.FIXED_60HZ
                        group.target_frequency = 60.0

                    self.add_alarm(
                        priority=AlarmPriority.WARNING,
                        equipment="SYSTEM",
                        message="60Hz 강제 전환 완료 - 모든 장비 60Hz 고정 모드"
                    )

    def get_force_60hz_progress(self) -> float:
        """60Hz 강제 전환 진행률 반환 (0.0 ~ 1.0)"""
        if self.force_60hz_state != ForceMode60HzState.FORCING:
            return 0.0

        if self.force_60hz_start_time is None:
            return 0.0

        elapsed = time.time() - self.force_60hz_start_time
        return min(1.0, elapsed / self.force_60hz_duration)

    def get_force_60hz_target_frequency(self, original_target: float) -> float:
        """60Hz 강제 전환 시 점진적 주파수 계산"""
        if self.force_60hz_state != ForceMode60HzState.FORCING:
            return original_target

        progress = self.get_force_60hz_progress()

        # 원래 목표 주파수에서 60Hz로 점진적 증가
        return original_target + (60.0 - original_target) * progress

    def reset_force_60hz(self):
        """60Hz 강제 전환 해제"""
        self.force_60hz_state = ForceMode60HzState.NORMAL
        self.force_60hz_start_time = None
        self.force_60hz_completed = False  # 플래그 리셋

        self.add_alarm(
            priority=AlarmPriority.INFO,
            equipment="SYSTEM",
            message="60Hz 강제 전환 해제 - 정상 운전 재개 (각 그룹 제어 모드는 수동으로 변경하세요)"
        )

    def add_alarm(self, priority: AlarmPriority, equipment: str, message: str):
        """알람 추가"""
        alarm = Alarm(
            timestamp=datetime.now(),
            priority=priority,
            equipment=equipment,
            message=message
        )

        self.alarms.insert(0, alarm)  # 최신 알람을 앞에 추가

        # 최대 개수 제한
        if len(self.alarms) > self.max_alarms:
            self.alarms = self.alarms[:self.max_alarms]

    def acknowledge_alarm(self, index: int):
        """알람 확인"""
        if 0 <= index < len(self.alarms):
            self.alarms[index].acknowledged = True

    def get_active_alarms(self) -> List[Alarm]:
        """미확인 알람 반환"""
        return [alarm for alarm in self.alarms if not alarm.acknowledged]

    def get_alarms_by_priority(self, priority: AlarmPriority) -> List[Alarm]:
        """우선순위별 알람 반환"""
        return [alarm for alarm in self.alarms if alarm.priority == priority]

    def update_learning_progress(self,
                                temp_accuracy: float,
                                opt_accuracy: float,
                                energy_savings: float,
                                learning_hours: float):
        """학습 진행 상태 업데이트"""
        self.learning_progress["temperature_prediction_accuracy"] = temp_accuracy
        self.learning_progress["optimization_accuracy"] = opt_accuracy
        self.learning_progress["average_energy_savings"] = energy_savings
        self.learning_progress["total_learning_hours"] = learning_hours
        self.learning_progress["last_learning_time"] = datetime.now()

    def get_learning_progress(self) -> Dict:
        """학습 진행 상태 반환"""
        return self.learning_progress.copy()

    def update_gps_data(self, gps_data: GPSData):
        """GPS 데이터 업데이트"""
        self.current_environment = self.gps_processor.process_gps_data(gps_data)
        self.last_gps_update = datetime.now()

    def get_gps_info(self) -> Optional[EnvironmentClassification]:
        """현재 GPS 환경 정보 반환"""
        return self.current_environment

    def update_vfd_diagnostic(self, vfd_id: str, diagnostic: VFDDiagnostic):
        """VFD 진단 결과 업데이트"""
        self.current_vfd_diagnostics[vfd_id] = diagnostic

    def get_vfd_diagnostics(self) -> Dict[str, VFDDiagnostic]:
        """현재 VFD 진단 결과 반환"""
        return self.current_vfd_diagnostics.copy()

    def get_vfd_summary(self) -> Dict:
        """VFD 상태 요약"""
        summary = {
            "total": len(self.vfd_monitor.vfds),
            "normal": 0,
            "caution": 0,
            "warning": 0,
            "critical": 0
        }

        for diagnostic in self.current_vfd_diagnostics.values():
            if diagnostic.status_grade == VFDStatus.NORMAL:
                summary["normal"] += 1
            elif diagnostic.status_grade == VFDStatus.CAUTION:
                summary["caution"] += 1
            elif diagnostic.status_grade == VFDStatus.WARNING:
                summary["warning"] += 1
            elif diagnostic.status_grade == VFDStatus.CRITICAL:
                summary["critical"] += 1

        return summary

    def export_state(self) -> Dict:
        """현재 상태 내보내기 (로깅/저장용)"""
        return {
            "timestamp": datetime.now().isoformat(),
            "groups": {
                name: {
                    "control_mode": group.control_mode.value,
                    "target_frequency": group.target_frequency,
                    "actual_frequencies": group.actual_frequencies,
                    "avg_actual": group.get_avg_actual_frequency(),
                    "max_deviation": group.get_max_deviation(),
                    "deviation_status": self.get_deviation_status(name)
                }
                for name, group in self.groups.items()
            },
            "force_60hz": {
                "state": self.force_60hz_state.value,
                "progress": self.get_force_60hz_progress()
            },
            "active_alarms_count": len(self.get_active_alarms()),
            "learning_progress": self.learning_progress
        }
