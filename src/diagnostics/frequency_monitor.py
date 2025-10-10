"""
주파수 편차 모니터링 및 알람
AI 목표 vs VFD 실제 주파수 비교
"""
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class DeviationCause(Enum):
    """편차 원인"""
    COMMUNICATION_DELAY = "communication_delay"  # VFD 통신 지연
    CONTROL_RESPONSE = "control_response"  # VFD 제어 응답 문제
    MECHANICAL_OVERLOAD = "mechanical_overload"  # 기계적 부하 과다
    SENSOR_ERROR = "sensor_error"  # 센서 오류 가능성
    UNKNOWN = "unknown"  # 원인 불명


@dataclass
class FrequencyDeviation:
    """주파수 편차 기록"""
    timestamp: datetime
    vfd_id: str
    target_frequency_hz: float  # AI 목표 주파수
    actual_frequency_hz: float  # VFD 실제 주파수
    deviation_hz: float  # 편차
    deviation_percent: float  # 편차율 (%)
    cause: DeviationCause  # 원인
    recommendation: str  # 대응 방안


@dataclass
class FrequencyAlarm:
    """주파수 알람"""
    alarm_id: str
    timestamp: datetime
    vfd_id: str
    severity: str  # "minor", "major", "critical"
    deviation: FrequencyDeviation
    acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]


class FrequencyMonitor:
    """
    주파수 편차 모니터링 시스템

    - AI 목표 주파수 vs VFD 실제 주파수 비교
    - 편차 0.5Hz 초과시 알람
    - 원인 자동 분석
    """

    def __init__(self, deviation_threshold_hz: float = 0.5):
        """
        Args:
            deviation_threshold_hz: 편차 임계값 (Hz)
        """
        self.deviation_threshold = deviation_threshold_hz

        # 편차 히스토리
        self.deviation_history: Dict[str, List[FrequencyDeviation]] = {}

        # 알람 리스트
        self.active_alarms: List[FrequencyAlarm] = []
        self.alarm_history: List[FrequencyAlarm] = []
        self.alarm_counter = 0

        # 통계
        self.total_checks = 0
        self.total_deviations = 0

    def check_frequency_deviation(
        self,
        vfd_id: str,
        target_freq: float,
        actual_freq: float,
        vfd_current_a: Optional[float] = None,
        vfd_torque_percent: Optional[float] = None,
        communication_delay_ms: Optional[float] = None
    ) -> Optional[FrequencyDeviation]:
        """
        주파수 편차 체크

        Args:
            vfd_id: VFD ID
            target_freq: AI 목표 주파수
            actual_freq: VFD 실제 주파수
            vfd_current_a: VFD 전류 (옵션)
            vfd_torque_percent: VFD 토크 (옵션)
            communication_delay_ms: 통신 지연 (옵션)

        Returns:
            FrequencyDeviation (편차 있는 경우)
        """
        self.total_checks += 1

        # 편차 계산
        deviation_hz = abs(actual_freq - target_freq)
        deviation_percent = (deviation_hz / target_freq) * 100.0 if target_freq > 0 else 0.0

        # 임계값 체크
        if deviation_hz <= self.deviation_threshold:
            return None  # 정상

        self.total_deviations += 1

        # 원인 분석
        cause = self._analyze_deviation_cause(
            vfd_id, deviation_hz, vfd_current_a, vfd_torque_percent, communication_delay_ms
        )

        # 대응 방안
        recommendation = self._generate_recommendation(cause, deviation_hz)

        deviation = FrequencyDeviation(
            timestamp=datetime.now(),
            vfd_id=vfd_id,
            target_frequency_hz=target_freq,
            actual_frequency_hz=actual_freq,
            deviation_hz=deviation_hz,
            deviation_percent=deviation_percent,
            cause=cause,
            recommendation=recommendation
        )

        # 히스토리 저장
        if vfd_id not in self.deviation_history:
            self.deviation_history[vfd_id] = []

        self.deviation_history[vfd_id].append(deviation)

        # 히스토리 크기 제한 (최근 500개)
        if len(self.deviation_history[vfd_id]) > 500:
            self.deviation_history[vfd_id] = self.deviation_history[vfd_id][-500:]

        # 알람 생성 (편차가 큰 경우)
        if deviation_hz > self.deviation_threshold * 2:  # 1.0Hz 이상
            self._create_alarm(deviation)

        return deviation

    def _analyze_deviation_cause(
        self,
        vfd_id: str,
        deviation_hz: float,
        vfd_current: Optional[float],
        vfd_torque: Optional[float],
        comm_delay: Optional[float]
    ) -> DeviationCause:
        """편차 원인 분석"""
        # 1. 통신 지연 체크
        if comm_delay is not None and comm_delay > 500:  # 500ms 이상
            return DeviationCause.COMMUNICATION_DELAY

        # 2. 기계적 부하 과다
        if vfd_torque is not None and vfd_torque > 110:  # 110% 이상
            return DeviationCause.MECHANICAL_OVERLOAD

        if vfd_current is not None:
            # 정격 전류 대비 과전류 (간단한 추정)
            if vfd_current > 200:  # 가정: 정격 200A
                return DeviationCause.MECHANICAL_OVERLOAD

        # 3. 제어 응답 문제 (히스토리 기반)
        if vfd_id in self.deviation_history:
            recent = self.deviation_history[vfd_id][-10:]
            if len(recent) >= 5:
                # 최근 10개 중 5개 이상 편차 = 제어 응답 문제
                return DeviationCause.CONTROL_RESPONSE

        # 4. 편차가 매우 큰 경우 - 센서 오류 의심
        if deviation_hz > 5.0:
            return DeviationCause.SENSOR_ERROR

        return DeviationCause.UNKNOWN

    def _generate_recommendation(
        self,
        cause: DeviationCause,
        deviation_hz: float
    ) -> str:
        """대응 방안 생성"""
        recommendations = {
            DeviationCause.COMMUNICATION_DELAY: (
                "Modbus 통신 상태 점검 필요. "
                "네트워크 케이블 및 통신 파라미터 확인"
            ),
            DeviationCause.CONTROL_RESPONSE: (
                "VFD 제어 파라미터 재설정 권장. "
                "가속/감속 시간 조정 필요"
            ),
            DeviationCause.MECHANICAL_OVERLOAD: (
                "기계 부하 점검 필요. "
                "펌프/팬 베어링, 임펠러 상태 확인"
            ),
            DeviationCause.SENSOR_ERROR: (
                "속도 피드백 센서 점검 필요. "
                "엔코더 또는 홀센서 확인"
            ),
            DeviationCause.UNKNOWN: (
                "편차 원인 모니터링 중. "
                "지속시 전문가 점검 권장"
            )
        }

        base_rec = recommendations.get(cause, "원인 분석 필요")

        # 편차 크기에 따른 추가 권고
        if deviation_hz > 2.0:
            base_rec += " | ⚠️ 즉시 조치 필요"
        elif deviation_hz > 1.0:
            base_rec += " | 조기 점검 권장"

        return base_rec

    def _create_alarm(self, deviation: FrequencyDeviation):
        """알람 생성"""
        self.alarm_counter += 1
        alarm_id = f"FREQ_ALARM_{self.alarm_counter:06d}"

        # 심각도 판정
        if deviation.deviation_hz > 3.0:
            severity = "critical"
        elif deviation.deviation_hz > 1.5:
            severity = "major"
        else:
            severity = "minor"

        alarm = FrequencyAlarm(
            alarm_id=alarm_id,
            timestamp=deviation.timestamp,
            vfd_id=deviation.vfd_id,
            severity=severity,
            deviation=deviation,
            acknowledged=False,
            acknowledged_by=None,
            acknowledged_at=None
        )

        self.active_alarms.append(alarm)
        self.alarm_history.append(alarm)

        print(f"\n🚨 주파수 편차 알람 발생")
        print(f"   알람 ID: {alarm_id}")
        print(f"   VFD: {deviation.vfd_id}")
        print(f"   심각도: {severity}")
        print(f"   편차: {deviation.deviation_hz:.2f}Hz ({deviation.deviation_percent:.1f}%)")
        print(f"   원인: {deviation.cause.value}")
        print(f"   권고: {deviation.recommendation}\n")

    def acknowledge_alarm(self, alarm_id: str, acknowledged_by: str):
        """알람 확인"""
        for alarm in self.active_alarms:
            if alarm.alarm_id == alarm_id:
                alarm.acknowledged = True
                alarm.acknowledged_by = acknowledged_by
                alarm.acknowledged_at = datetime.now()

                # 활성 알람에서 제거
                self.active_alarms.remove(alarm)
                return True

        return False

    def get_active_alarms(self) -> List[FrequencyAlarm]:
        """활성 알람 목록"""
        return self.active_alarms.copy()

    def get_deviation_statistics(self, vfd_id: Optional[str] = None) -> Dict:
        """편차 통계"""
        if vfd_id:
            # 특정 VFD
            if vfd_id not in self.deviation_history:
                return {
                    'vfd_id': vfd_id,
                    'total_deviations': 0,
                    'avg_deviation_hz': 0.0,
                    'max_deviation_hz': 0.0
                }

            deviations = self.deviation_history[vfd_id]
            return {
                'vfd_id': vfd_id,
                'total_deviations': len(deviations),
                'avg_deviation_hz': sum(d.deviation_hz for d in deviations) / len(deviations),
                'max_deviation_hz': max(d.deviation_hz for d in deviations),
                'most_common_cause': self._get_most_common_cause(deviations)
            }
        else:
            # 전체
            all_deviations = []
            for deviations in self.deviation_history.values():
                all_deviations.extend(deviations)

            if not all_deviations:
                return {
                    'total_checks': self.total_checks,
                    'total_deviations': 0,
                    'deviation_rate_percent': 0.0
                }

            return {
                'total_checks': self.total_checks,
                'total_deviations': self.total_deviations,
                'deviation_rate_percent': (self.total_deviations / self.total_checks) * 100.0,
                'avg_deviation_hz': sum(d.deviation_hz for d in all_deviations) / len(all_deviations),
                'max_deviation_hz': max(d.deviation_hz for d in all_deviations),
                'total_alarms': len(self.alarm_history),
                'active_alarms': len(self.active_alarms)
            }

    def _get_most_common_cause(self, deviations: List[FrequencyDeviation]) -> str:
        """가장 흔한 원인"""
        if not deviations:
            return "N/A"

        causes = [d.cause for d in deviations]
        most_common = max(set(causes), key=causes.count)
        return most_common.value

    def get_deviation_trend(self, vfd_id: str, recent_count: int = 20) -> List[float]:
        """편차 추이 (최근 N개)"""
        if vfd_id not in self.deviation_history:
            return []

        recent = self.deviation_history[vfd_id][-recent_count:]
        return [d.deviation_hz for d in recent]
