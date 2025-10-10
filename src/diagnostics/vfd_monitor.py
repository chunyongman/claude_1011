"""
VFD 이상 징후 감지 시스템 (Danfoss VFD 기준)
10개 VFD 실시간 모니터링 및 상태 등급 판정
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import numpy as np


class VFDStatus(Enum):
    """VFD 상태 등급"""
    NORMAL = "normal"  # 정상
    CAUTION = "caution"  # 주의
    WARNING = "warning"  # 경고
    CRITICAL = "critical"  # 위험


class VFDType(Enum):
    """VFD 타입"""
    SW_PUMP = "sw_pump"
    FW_PUMP = "fw_pump"
    ER_FAN = "er_fan"


@dataclass
class DanfossStatusBits:
    """
    Danfoss VFD StatusBits

    각 비트는 True/False로 표현
    """
    trip: bool  # VFD 트립 발생
    error: bool  # 오류 발생
    warning: bool  # 경고 발생
    voltage_exceeded: bool  # 전압 초과
    torque_exceeded: bool  # 토크 초과
    thermal_exceeded: bool  # 열 초과
    control_ready: bool  # 제어 준비
    drive_ready: bool  # 드라이브 준비
    in_operation: bool  # 운전 중
    speed_equals_reference: bool  # 속도 일치
    bus_control: bool  # 버스 제어

    def get_severity_score(self) -> int:
        """
        심각도 점수 계산 (0-100)

        높을수록 심각
        """
        score = 0

        if self.trip:
            score += 50
        if self.error:
            score += 30
        if self.warning:
            score += 15
        if self.voltage_exceeded:
            score += 20
        if self.torque_exceeded:
            score += 20
        if self.thermal_exceeded:
            score += 25

        # 정상 상태 체크 (부정적)
        if not self.control_ready:
            score += 10
        if not self.drive_ready:
            score += 10
        if self.in_operation and not self.speed_equals_reference:
            score += 10

        return min(100, score)


@dataclass
class VFDInfo:
    """VFD 정보"""
    vfd_id: str
    vfd_type: VFDType
    rated_power_kw: float
    modbus_address: int


@dataclass
class VFDDiagnostic:
    """VFD 진단 결과"""
    timestamp: datetime
    vfd_id: str

    # StatusBits
    status_bits: DanfossStatusBits

    # 운전 데이터
    current_frequency_hz: float
    output_current_a: float
    output_voltage_v: float
    dc_bus_voltage_v: float
    motor_temperature_c: float
    heatsink_temperature_c: float

    # 진단 결과
    status_grade: VFDStatus
    severity_score: int  # 0-100
    anomaly_patterns: List[str]  # 이상 패턴 목록
    recommendation: str  # 권고사항

    # 통계
    cumulative_runtime_hours: float
    trip_count: int
    error_count: int
    warning_count: int


class VFDMonitor:
    """
    VFD 이상 징후 감지 시스템

    10개 VFD 모니터링:
    - SW펌프 1-3
    - FW펌프 1-3
    - E/R팬 1-4
    """

    def __init__(self):
        """초기화"""
        # VFD 정보
        self.vfds: Dict[str, VFDInfo] = self._initialize_vfds()

        # 진단 히스토리
        self.diagnostic_history: Dict[str, List[VFDDiagnostic]] = {
            vfd_id: [] for vfd_id in self.vfds.keys()
        }

        # 통계
        self.cumulative_runtime: Dict[str, float] = {
            vfd_id: 0.0 for vfd_id in self.vfds.keys()
        }
        self.trip_counts: Dict[str, int] = {
            vfd_id: 0 for vfd_id in self.vfds.keys()
        }
        self.error_counts: Dict[str, int] = {
            vfd_id: 0 for vfd_id in self.vfds.keys()
        }
        self.warning_counts: Dict[str, int] = {
            vfd_id: 0 for vfd_id in self.vfds.keys()
        }

        # 임계값
        self.temp_threshold_motor = 80.0  # °C
        self.temp_threshold_heatsink = 65.0  # °C
        self.voltage_range = (380.0, 420.0)  # V

    def _initialize_vfds(self) -> Dict[str, VFDInfo]:
        """VFD 정보 초기화"""
        vfds = {}

        # SW펌프 1-3
        for i in range(1, 4):
            vfd_id = f"SW_PUMP_{i}"
            vfds[vfd_id] = VFDInfo(
                vfd_id=vfd_id,
                vfd_type=VFDType.SW_PUMP,
                rated_power_kw=132.0,
                modbus_address=100 + i
            )

        # FW펌프 1-3
        for i in range(1, 4):
            vfd_id = f"FW_PUMP_{i}"
            vfds[vfd_id] = VFDInfo(
                vfd_id=vfd_id,
                vfd_type=VFDType.FW_PUMP,
                rated_power_kw=75.0,
                modbus_address=200 + i
            )

        # E/R팬 1-4
        for i in range(1, 5):
            vfd_id = f"ER_FAN_{i}"
            vfds[vfd_id] = VFDInfo(
                vfd_id=vfd_id,
                vfd_type=VFDType.ER_FAN,
                rated_power_kw=54.3,
                modbus_address=300 + i
            )

        return vfds

    def diagnose_vfd(
        self,
        vfd_id: str,
        status_bits: DanfossStatusBits,
        frequency_hz: float,
        output_current_a: float,
        output_voltage_v: float,
        dc_bus_voltage_v: float,
        motor_temp_c: float,
        heatsink_temp_c: float,
        runtime_seconds: float = 0.0
    ) -> VFDDiagnostic:
        """
        VFD 진단

        Returns:
            VFDDiagnostic
        """
        if vfd_id not in self.vfds:
            raise ValueError(f"Unknown VFD: {vfd_id}")

        # 이상 패턴 분석
        anomaly_patterns = self._analyze_anomaly_patterns(
            vfd_id, status_bits, motor_temp_c, heatsink_temp_c,
            output_voltage_v, dc_bus_voltage_v
        )

        # 심각도 점수
        severity_score = status_bits.get_severity_score()

        # 추가 심각도 (온도, 전압)
        if motor_temp_c > self.temp_threshold_motor:
            severity_score += 15
        if heatsink_temp_c > self.temp_threshold_heatsink:
            severity_score += 10
        if not (self.voltage_range[0] <= output_voltage_v <= self.voltage_range[1]):
            severity_score += 15

        severity_score = min(100, severity_score)

        # 상태 등급 판정
        status_grade = self._determine_status_grade(severity_score, anomaly_patterns)

        # 권고사항
        recommendation = self._generate_recommendation(
            status_grade, anomaly_patterns, status_bits
        )

        # 통계 업데이트
        if runtime_seconds > 0:
            self.cumulative_runtime[vfd_id] += runtime_seconds / 3600.0

        if status_bits.trip:
            self.trip_counts[vfd_id] += 1
        if status_bits.error:
            self.error_counts[vfd_id] += 1
        if status_bits.warning:
            self.warning_counts[vfd_id] += 1

        diagnostic = VFDDiagnostic(
            timestamp=datetime.now(),
            vfd_id=vfd_id,
            status_bits=status_bits,
            current_frequency_hz=frequency_hz,
            output_current_a=output_current_a,
            output_voltage_v=output_voltage_v,
            dc_bus_voltage_v=dc_bus_voltage_v,
            motor_temperature_c=motor_temp_c,
            heatsink_temperature_c=heatsink_temp_c,
            status_grade=status_grade,
            severity_score=severity_score,
            anomaly_patterns=anomaly_patterns,
            recommendation=recommendation,
            cumulative_runtime_hours=self.cumulative_runtime[vfd_id],
            trip_count=self.trip_counts[vfd_id],
            error_count=self.error_counts[vfd_id],
            warning_count=self.warning_counts[vfd_id]
        )

        # 히스토리 저장 (최근 1000개)
        self.diagnostic_history[vfd_id].append(diagnostic)
        if len(self.diagnostic_history[vfd_id]) > 1000:
            self.diagnostic_history[vfd_id] = self.diagnostic_history[vfd_id][-1000:]

        return diagnostic

    def _analyze_anomaly_patterns(
        self,
        vfd_id: str,
        status_bits: DanfossStatusBits,
        motor_temp: float,
        heatsink_temp: float,
        output_voltage: float,
        dc_bus_voltage: float
    ) -> List[str]:
        """이상 패턴 분석"""
        patterns = []

        # StatusBits 기반
        if status_bits.trip:
            patterns.append("VFD_TRIP")
        if status_bits.error:
            patterns.append("VFD_ERROR")
        if status_bits.warning:
            patterns.append("VFD_WARNING")
        if status_bits.voltage_exceeded:
            patterns.append("VOLTAGE_EXCEEDED")
        if status_bits.torque_exceeded:
            patterns.append("TORQUE_EXCEEDED")
        if status_bits.thermal_exceeded:
            patterns.append("THERMAL_EXCEEDED")

        # 온도 기반
        if motor_temp > self.temp_threshold_motor:
            patterns.append("MOTOR_OVERTEMP")
        elif motor_temp > self.temp_threshold_motor - 10:
            patterns.append("MOTOR_TEMP_HIGH")

        if heatsink_temp > self.temp_threshold_heatsink:
            patterns.append("HEATSINK_OVERTEMP")

        # 전압 기반
        if output_voltage < self.voltage_range[0]:
            patterns.append("VOLTAGE_LOW")
        elif output_voltage > self.voltage_range[1]:
            patterns.append("VOLTAGE_HIGH")

        # DC 버스 전압 (정상: 540V ± 10%)
        if dc_bus_voltage < 486 or dc_bus_voltage > 594:
            patterns.append("DC_BUS_ABNORMAL")

        # 준비 상태 체크
        if not status_bits.control_ready:
            patterns.append("CONTROL_NOT_READY")
        if not status_bits.drive_ready:
            patterns.append("DRIVE_NOT_READY")

        # 속도 불일치 (운전 중)
        if status_bits.in_operation and not status_bits.speed_equals_reference:
            patterns.append("SPEED_MISMATCH")

        # 통계적 이상 패턴 (히스토리 기반)
        stat_patterns = self._detect_statistical_anomalies(vfd_id)
        patterns.extend(stat_patterns)

        return patterns

    def _detect_statistical_anomalies(self, vfd_id: str) -> List[str]:
        """통계적 이상 패턴 감지"""
        patterns = []

        history = self.diagnostic_history[vfd_id]
        if len(history) < 30:
            return patterns

        # 최근 30개 데이터
        recent = history[-30:]

        # 온도 증가 추세
        motor_temps = [d.motor_temperature_c for d in recent]
        temp_trend = np.polyfit(range(len(motor_temps)), motor_temps, 1)[0]
        if temp_trend > 0.5:  # 0.5°C/샘플 이상 증가
            patterns.append("TEMP_RISING_TREND")

        # 경고 빈도 증가
        warning_rate = sum(1 for d in recent if d.status_bits.warning) / len(recent)
        if warning_rate > 0.3:  # 30% 이상
            patterns.append("FREQUENT_WARNINGS")

        return patterns

    def _determine_status_grade(
        self,
        severity_score: int,
        anomaly_patterns: List[str]
    ) -> VFDStatus:
        """
        상태 등급 판정

        점수 기준:
        - 0-20: 정상
        - 21-50: 주의
        - 51-75: 경고
        - 76-100: 위험
        """
        # 심각한 패턴 체크
        critical_patterns = {"VFD_TRIP", "VFD_ERROR", "THERMAL_EXCEEDED", "MOTOR_OVERTEMP"}
        if any(p in critical_patterns for p in anomaly_patterns):
            return VFDStatus.CRITICAL

        # 점수 기반
        if severity_score >= 76:
            return VFDStatus.CRITICAL
        elif severity_score >= 51:
            return VFDStatus.WARNING
        elif severity_score >= 21:
            return VFDStatus.CAUTION
        else:
            return VFDStatus.NORMAL

    def _generate_recommendation(
        self,
        status_grade: VFDStatus,
        anomaly_patterns: List[str],
        status_bits: DanfossStatusBits
    ) -> str:
        """권고사항 생성"""
        if status_grade == VFDStatus.NORMAL:
            return "정상 운전 중"

        recommendations = []

        if status_grade == VFDStatus.CRITICAL:
            recommendations.append("⚠️ 즉시 점검 필요")

        # 패턴별 권고
        if "VFD_TRIP" in anomaly_patterns:
            recommendations.append("VFD 트립 원인 확인 필요")
        if "MOTOR_OVERTEMP" in anomaly_patterns or "THERMAL_EXCEEDED" in anomaly_patterns:
            recommendations.append("모터 냉각 점검 및 부하 확인")
        if "HEATSINK_OVERTEMP" in anomaly_patterns:
            recommendations.append("히트싱크 청소 및 냉각팬 점검")
        if "VOLTAGE_HIGH" in anomaly_patterns or "VOLTAGE_LOW" in anomaly_patterns:
            recommendations.append("전원 공급 상태 점검")
        if "TORQUE_EXCEEDED" in anomaly_patterns:
            recommendations.append("기계 부하 과다, 점검 필요")
        if "SPEED_MISMATCH" in anomaly_patterns:
            recommendations.append("VFD 파라미터 및 통신 확인")
        if "TEMP_RISING_TREND" in anomaly_patterns:
            recommendations.append("온도 상승 추세 관찰 중, 주의")

        if not recommendations:
            if status_grade == VFDStatus.WARNING:
                recommendations.append("정기 점검 권장")
            elif status_grade == VFDStatus.CAUTION:
                recommendations.append("관찰 필요")

        return " | ".join(recommendations)

    def get_all_vfd_status(self) -> Dict[str, VFDDiagnostic]:
        """전체 VFD 최신 상태"""
        status = {}
        for vfd_id in self.vfds.keys():
            if self.diagnostic_history[vfd_id]:
                status[vfd_id] = self.diagnostic_history[vfd_id][-1]
        return status

    def get_vfd_status_summary(self) -> Dict:
        """VFD 상태 요약"""
        all_status = self.get_all_vfd_status()

        summary = {
            'total_vfds': len(self.vfds),
            'normal': 0,
            'caution': 0,
            'warning': 0,
            'critical': 0,
            'critical_vfds': []
        }

        for vfd_id, diagnostic in all_status.items():
            grade = diagnostic.status_grade
            if grade == VFDStatus.NORMAL:
                summary['normal'] += 1
            elif grade == VFDStatus.CAUTION:
                summary['caution'] += 1
            elif grade == VFDStatus.WARNING:
                summary['warning'] += 1
            elif grade == VFDStatus.CRITICAL:
                summary['critical'] += 1
                summary['critical_vfds'].append(vfd_id)

        return summary
