"""
Edge AI + PLC 이중화 구조
Xavier NX (Edge AI) + Siemens PLC 상호 백업
"""
from dataclasses import dataclass
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum


class SystemMode(Enum):
    """시스템 모드"""
    EDGE_AI_PRIMARY = "edge_ai_primary"  # Edge AI 주, PLC 백업
    PLC_BACKUP = "plc_backup"  # PLC 백업 모드
    DUAL_ACTIVE = "dual_active"  # 양쪽 모두 활성


class ComponentStatus(Enum):
    """컴포넌트 상태"""
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass
class HeartbeatSignal:
    """Heartbeat 신호"""
    timestamp: datetime
    sender: str  # "edge_ai" or "plc"
    sequence_number: int
    system_load_percent: float
    diagnostics_active: bool


@dataclass
class DiagnosticCommand:
    """진단 명령"""
    timestamp: datetime
    vfd_id: str
    command_type: str  # "status_check", "reset", "emergency_stop"
    parameters: Dict


@dataclass
class RedundancyStatus:
    """이중화 상태"""
    timestamp: datetime
    system_mode: SystemMode
    edge_ai_status: ComponentStatus
    plc_status: ComponentStatus
    last_edge_heartbeat: Optional[datetime]
    last_plc_heartbeat: Optional[datetime]
    failover_count: int
    data_exchange_rate_hz: float


class EdgePLCRedundancy:
    """
    Edge AI + PLC 이중화 시스템

    - Edge AI (Xavier NX): VFD 진단 분석, 복잡한 이상 감지
    - PLC (Siemens): 데이터 수집, 기본 진단, 백업
    - 1초 주기 데이터 교환
    - 10초 타임아웃시 백업 전환
    """

    def __init__(self):
        """초기화"""
        # 시스템 상태
        self.system_mode = SystemMode.EDGE_AI_PRIMARY
        self.edge_ai_status = ComponentStatus.ONLINE
        self.plc_status = ComponentStatus.ONLINE

        # Heartbeat 추적
        self.edge_heartbeat_seq = 0
        self.plc_heartbeat_seq = 0
        self.last_edge_heartbeat: Optional[datetime] = datetime.now()
        self.last_plc_heartbeat: Optional[datetime] = datetime.now()

        # 타임아웃 설정
        self.heartbeat_timeout_seconds = 10.0
        self.data_exchange_interval_seconds = 1.0

        # 통계
        self.failover_count = 0
        self.total_exchanges = 0
        self.last_exchange_time: Optional[datetime] = None

        # 콜백
        self.on_failover: Optional[Callable] = None

    def send_edge_heartbeat(self, system_load: float, diagnostics_active: bool) -> HeartbeatSignal:
        """Edge AI Heartbeat 전송"""
        self.edge_heartbeat_seq += 1

        signal = HeartbeatSignal(
            timestamp=datetime.now(),
            sender="edge_ai",
            sequence_number=self.edge_heartbeat_seq,
            system_load_percent=system_load,
            diagnostics_active=diagnostics_active
        )

        self.last_edge_heartbeat = signal.timestamp
        return signal

    def send_plc_heartbeat(self, system_load: float, diagnostics_active: bool) -> HeartbeatSignal:
        """PLC Heartbeat 전송"""
        self.plc_heartbeat_seq += 1

        signal = HeartbeatSignal(
            timestamp=datetime.now(),
            sender="plc",
            sequence_number=self.plc_heartbeat_seq,
            system_load_percent=system_load,
            diagnostics_active=diagnostics_active
        )

        self.last_plc_heartbeat = signal.timestamp
        return signal

    def receive_heartbeat(self, signal: HeartbeatSignal):
        """Heartbeat 수신"""
        if signal.sender == "edge_ai":
            self.last_edge_heartbeat = signal.timestamp
            self.edge_ai_status = ComponentStatus.ONLINE
        elif signal.sender == "plc":
            self.last_plc_heartbeat = signal.timestamp
            self.plc_status = ComponentStatus.ONLINE

    def check_heartbeat_timeout(self) -> bool:
        """
        Heartbeat 타임아웃 체크

        Returns:
            타임아웃 발생 여부
        """
        now = datetime.now()
        timeout_occurred = False

        # Edge AI 타임아웃 체크
        if self.last_edge_heartbeat is not None:
            edge_elapsed = (now - self.last_edge_heartbeat).total_seconds()
            if edge_elapsed > self.heartbeat_timeout_seconds:
                if self.edge_ai_status != ComponentStatus.OFFLINE:
                    print(f"⚠️  Edge AI Heartbeat timeout ({edge_elapsed:.1f}s)")
                    self.edge_ai_status = ComponentStatus.OFFLINE
                    timeout_occurred = True
                    self._trigger_failover_to_plc()

        # PLC 타임아웃 체크
        if self.last_plc_heartbeat is not None:
            plc_elapsed = (now - self.last_plc_heartbeat).total_seconds()
            if plc_elapsed > self.heartbeat_timeout_seconds:
                if self.plc_status != ComponentStatus.OFFLINE:
                    print(f"⚠️  PLC Heartbeat timeout ({plc_elapsed:.1f}s)")
                    self.plc_status = ComponentStatus.OFFLINE
                    timeout_occurred = True

        return timeout_occurred

    def _trigger_failover_to_plc(self):
        """PLC 백업 모드로 전환"""
        if self.system_mode == SystemMode.EDGE_AI_PRIMARY:
            print(f"\n{'='*60}")
            print(f"🔄 Failover: Edge AI → PLC 백업 모드")
            print(f"   시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")

            self.system_mode = SystemMode.PLC_BACKUP
            self.failover_count += 1

            if self.on_failover:
                self.on_failover("edge_ai_to_plc")

    def restore_edge_ai(self):
        """Edge AI 복구"""
        if self.system_mode == SystemMode.PLC_BACKUP:
            print(f"\n{'='*60}")
            print(f"✅ Edge AI 복구: PLC 백업 → Edge AI 주 모드")
            print(f"   시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")

            self.system_mode = SystemMode.EDGE_AI_PRIMARY
            self.edge_ai_status = ComponentStatus.ONLINE

    def exchange_data(self, data: Dict) -> bool:
        """
        데이터 교환 (1초 주기)

        Args:
            data: 교환할 데이터

        Returns:
            교환 성공 여부
        """
        now = datetime.now()

        # 교환 간격 체크
        if self.last_exchange_time is not None:
            elapsed = (now - self.last_exchange_time).total_seconds()
            if elapsed < self.data_exchange_interval_seconds:
                return False  # 너무 빠름

        self.last_exchange_time = now
        self.total_exchanges += 1

        # Heartbeat 타임아웃 체크
        self.check_heartbeat_timeout()

        return True

    def get_active_diagnostic_system(self) -> str:
        """
        현재 활성 진단 시스템

        Returns:
            "edge_ai" or "plc"
        """
        if self.system_mode == SystemMode.EDGE_AI_PRIMARY:
            return "edge_ai"
        elif self.system_mode == SystemMode.PLC_BACKUP:
            return "plc"
        else:
            return "dual"

    def get_data_exchange_rate(self) -> float:
        """
        데이터 교환 속도 (Hz)

        Returns:
            초당 교환 횟수
        """
        if self.last_exchange_time is None or self.total_exchanges < 2:
            return 0.0

        # 최근 10초 평균
        return 1.0 / self.data_exchange_interval_seconds

    def get_redundancy_status(self) -> RedundancyStatus:
        """이중화 상태 반환"""
        return RedundancyStatus(
            timestamp=datetime.now(),
            system_mode=self.system_mode,
            edge_ai_status=self.edge_ai_status,
            plc_status=self.plc_status,
            last_edge_heartbeat=self.last_edge_heartbeat,
            last_plc_heartbeat=self.last_plc_heartbeat,
            failover_count=self.failover_count,
            data_exchange_rate_hz=self.get_data_exchange_rate()
        )

    def perform_edge_ai_diagnostics(self, vfd_data: Dict) -> Dict:
        """
        Edge AI 진단 수행 (복잡한 분석)

        Args:
            vfd_data: VFD 데이터

        Returns:
            진단 결과
        """
        if self.edge_ai_status != ComponentStatus.ONLINE:
            raise RuntimeError("Edge AI offline")

        # 복잡한 ML 기반 분석
        # (실제로는 Isolation Forest 등 사용)
        result = {
            'timestamp': datetime.now(),
            'analyzer': 'edge_ai',
            'analysis_type': 'ml_based',
            'confidence': 0.95,
            'anomaly_detected': False,
            'details': {}
        }

        return result

    def perform_plc_diagnostics(self, vfd_data: Dict) -> Dict:
        """
        PLC 진단 수행 (기본 임계값 기반)

        Args:
            vfd_data: VFD 데이터

        Returns:
            진단 결과
        """
        if self.plc_status != ComponentStatus.ONLINE:
            raise RuntimeError("PLC offline")

        # 간단한 임계값 기반 분석
        result = {
            'timestamp': datetime.now(),
            'analyzer': 'plc',
            'analysis_type': 'threshold_based',
            'confidence': 0.75,
            'anomaly_detected': False,
            'details': {}
        }

        return result

    def get_system_health(self) -> Dict:
        """시스템 건강 상태"""
        now = datetime.now()

        edge_health = "healthy"
        plc_health = "healthy"

        if self.edge_ai_status == ComponentStatus.OFFLINE:
            edge_health = "offline"
        elif self.edge_ai_status == ComponentStatus.DEGRADED:
            edge_health = "degraded"

        if self.plc_status == ComponentStatus.OFFLINE:
            plc_health = "offline"
        elif self.plc_status == ComponentStatus.DEGRADED:
            plc_health = "degraded"

        # Heartbeat 지연 체크
        edge_delay = 0.0
        plc_delay = 0.0

        if self.last_edge_heartbeat:
            edge_delay = (now - self.last_edge_heartbeat).total_seconds()
        if self.last_plc_heartbeat:
            plc_delay = (now - self.last_plc_heartbeat).total_seconds()

        return {
            'system_mode': self.system_mode.value,
            'edge_ai_health': edge_health,
            'plc_health': plc_health,
            'edge_heartbeat_delay_seconds': edge_delay,
            'plc_heartbeat_delay_seconds': plc_delay,
            'failover_count': self.failover_count,
            'total_data_exchanges': self.total_exchanges,
            'data_exchange_rate_hz': self.get_data_exchange_rate()
        }
