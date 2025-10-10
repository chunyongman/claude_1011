"""
ESS AI System - Edge AI - PLC 이중화 구조
주 제어 (Xavier NX) ↔ 백업 제어 (PLC)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from enum import Enum
import threading
import time
import logging


class ControlAuthority(Enum):
    """제어 권한"""
    EDGE_AI_PRIMARY = "edge_ai_primary"  # Edge AI 주 제어
    PLC_BACKUP = "plc_backup"  # PLC 백업 제어
    FAILSAFE = "failsafe"  # 안전 모드 (고정 제어)


class SystemHealth(Enum):
    """시스템 건전성"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    FAILED = "failed"


@dataclass
class HealthCheck:
    """건전성 확인"""
    component: str
    status: SystemHealth
    last_check: datetime
    error_message: Optional[str] = None


@dataclass
class RedundancyConfig:
    """이중화 설정"""
    communication_timeout_seconds: int = 10  # 통신 타임아웃
    failsafe_timeout_seconds: int = 10  # Fail-Safe 진입 시간
    health_check_interval_seconds: int = 5  # 건전성 확인 주기
    auto_recovery_enabled: bool = True  # 자동 복구 활성화
    recovery_stability_seconds: int = 30  # 복구 안정화 시간


@dataclass
class FailoverEvent:
    """Failover 이벤트"""
    timestamp: datetime
    from_authority: ControlAuthority
    to_authority: ControlAuthority
    reason: str
    recovery_time_seconds: Optional[float] = None


class RedundancyManager:
    """
    이중화 관리자
    - Edge AI 장애시 PLC 백업
    - 통신 타임아웃 감시
    - 자동 복구
    """

    def __init__(self, config: RedundancyConfig):
        self.config = config
        self.current_authority = ControlAuthority.EDGE_AI_PRIMARY
        self.system_health = SystemHealth.HEALTHY

        # 건전성 확인
        self.health_checks: Dict[str, HealthCheck] = {}

        # 통신 타임아웃 추적
        self.last_edge_ai_response: Optional[datetime] = datetime.now()
        self.last_plc_response: Optional[datetime] = datetime.now()

        # Failover 이력
        self.failover_history: List[FailoverEvent] = []

        # 모니터링 스레드
        self.monitoring_thread: Optional[threading.Thread] = None
        self.running = False

        # 로깅
        self.logger = logging.getLogger("RedundancyManager")
        self.logger.setLevel(logging.INFO)

    def start_monitoring(self) -> None:
        """모니터링 시작"""
        if self.running:
            return

        self.running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        self.logger.info("👁️ Redundancy monitoring started")

    def stop_monitoring(self) -> None:
        """모니터링 중지"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)
        self.logger.info("⏹️ Redundancy monitoring stopped")

    def _monitoring_loop(self) -> None:
        """모니터링 루프"""
        while self.running:
            try:
                # 건전성 확인
                self._check_system_health()

                # 통신 타임아웃 확인
                self._check_communication_timeout()

                # Fail-Safe 진입 필요 여부
                self._check_failsafe_condition()

                # 자동 복구 시도
                if self.config.auto_recovery_enabled:
                    self._attempt_auto_recovery()

            except Exception as e:
                self.logger.error(f"❌ Monitoring error: {e}")

            time.sleep(self.config.health_check_interval_seconds)

    def _check_system_health(self) -> None:
        """시스템 건전성 확인"""
        unhealthy_components = []

        for component, health_check in self.health_checks.items():
            if health_check.status not in [SystemHealth.HEALTHY, SystemHealth.DEGRADED]:
                unhealthy_components.append(component)

        # 전체 시스템 건전성 판단
        if len(unhealthy_components) == 0:
            self.system_health = SystemHealth.HEALTHY
        elif len(unhealthy_components) <= 1:
            self.system_health = SystemHealth.DEGRADED
        else:
            self.system_health = SystemHealth.CRITICAL

    def _check_communication_timeout(self) -> None:
        """통신 타임아웃 확인"""
        now = datetime.now()

        # Edge AI 통신 확인
        if self.last_edge_ai_response:
            edge_ai_timeout = (now - self.last_edge_ai_response).total_seconds()

            if edge_ai_timeout > self.config.communication_timeout_seconds:
                self.logger.warning(f"⚠️ Edge AI communication timeout: {edge_ai_timeout:.1f}s")
                self._trigger_failover_to_plc("Edge AI communication timeout")

        # PLC 통신 확인
        if self.last_plc_response:
            plc_timeout = (now - self.last_plc_response).total_seconds()

            if plc_timeout > self.config.communication_timeout_seconds:
                self.logger.error(f"❌ PLC communication timeout: {plc_timeout:.1f}s")
                self.update_component_health("PLC", SystemHealth.FAILED, "Communication timeout")

    def _check_failsafe_condition(self) -> None:
        """Fail-Safe 진입 조건 확인"""
        now = datetime.now()

        # Edge AI와 PLC 모두 응답 없음
        edge_ai_timeout = None
        plc_timeout = None

        if self.last_edge_ai_response:
            edge_ai_timeout = (now - self.last_edge_ai_response).total_seconds()

        if self.last_plc_response:
            plc_timeout = (now - self.last_plc_response).total_seconds()

        if (edge_ai_timeout and edge_ai_timeout > self.config.failsafe_timeout_seconds and
                plc_timeout and plc_timeout > self.config.failsafe_timeout_seconds):
            self.logger.critical("🚨 Both Edge AI and PLC failed - entering FAILSAFE mode")
            self._enter_failsafe_mode("Both controllers failed")

    def _attempt_auto_recovery(self) -> None:
        """자동 복구 시도"""
        if self.current_authority != ControlAuthority.EDGE_AI_PRIMARY:
            # PLC 백업 또는 Fail-Safe 모드인 경우

            # Edge AI가 복구되었는지 확인
            if self.last_edge_ai_response:
                recovery_time = (datetime.now() - self.last_edge_ai_response).total_seconds()

                if recovery_time < self.config.recovery_stability_seconds:
                    # Edge AI가 안정적으로 복구됨
                    edge_ai_health = self.health_checks.get("EdgeAI")

                    if edge_ai_health and edge_ai_health.status == SystemHealth.HEALTHY:
                        self._recover_to_edge_ai()

    def _trigger_failover_to_plc(self, reason: str) -> None:
        """PLC 백업으로 Failover"""
        if self.current_authority == ControlAuthority.PLC_BACKUP:
            return  # 이미 백업 모드

        self.logger.warning(f"⚠️ Failover to PLC: {reason}")

        event = FailoverEvent(
            timestamp=datetime.now(),
            from_authority=self.current_authority,
            to_authority=ControlAuthority.PLC_BACKUP,
            reason=reason
        )

        self.current_authority = ControlAuthority.PLC_BACKUP
        self.failover_history.append(event)

        # PLC에 제어 권한 전달 신호 전송
        self._notify_plc_takeover()

    def _enter_failsafe_mode(self, reason: str) -> None:
        """Fail-Safe 모드 진입"""
        if self.current_authority == ControlAuthority.FAILSAFE:
            return

        self.logger.critical(f"🚨 Entering FAILSAFE mode: {reason}")

        event = FailoverEvent(
            timestamp=datetime.now(),
            from_authority=self.current_authority,
            to_authority=ControlAuthority.FAILSAFE,
            reason=reason
        )

        self.current_authority = ControlAuthority.FAILSAFE
        self.system_health = SystemHealth.FAILED
        self.failover_history.append(event)

    def _recover_to_edge_ai(self) -> None:
        """Edge AI 주 제어로 복구"""
        if self.current_authority == ControlAuthority.EDGE_AI_PRIMARY:
            return

        self.logger.info(f"✅ Recovering to Edge AI primary control")

        recovery_start = None
        for event in reversed(self.failover_history):
            if event.from_authority == ControlAuthority.EDGE_AI_PRIMARY:
                recovery_start = event.timestamp
                break

        recovery_time = None
        if recovery_start:
            recovery_time = (datetime.now() - recovery_start).total_seconds()

        event = FailoverEvent(
            timestamp=datetime.now(),
            from_authority=self.current_authority,
            to_authority=ControlAuthority.EDGE_AI_PRIMARY,
            reason="Automatic recovery",
            recovery_time_seconds=recovery_time
        )

        self.current_authority = ControlAuthority.EDGE_AI_PRIMARY
        self.system_health = SystemHealth.HEALTHY
        self.failover_history.append(event)

    def _notify_plc_takeover(self) -> None:
        """PLC에 제어 권한 전달 통지"""
        # TODO: PLC로 Modbus 신호 전송
        self.logger.info("📤 Notifying PLC to take control")

    def update_edge_ai_heartbeat(self) -> None:
        """Edge AI Heartbeat 업데이트"""
        self.last_edge_ai_response = datetime.now()

    def update_plc_heartbeat(self) -> None:
        """PLC Heartbeat 업데이트"""
        self.last_plc_response = datetime.now()

    def update_component_health(
        self,
        component: str,
        status: SystemHealth,
        error_message: Optional[str] = None
    ) -> None:
        """컴포넌트 건전성 업데이트"""
        health_check = HealthCheck(
            component=component,
            status=status,
            last_check=datetime.now(),
            error_message=error_message
        )

        self.health_checks[component] = health_check

        if status in [SystemHealth.CRITICAL, SystemHealth.FAILED]:
            self.logger.error(f"❌ Component health critical: {component} - {error_message}")

    def get_current_authority(self) -> ControlAuthority:
        """현재 제어 권한"""
        return self.current_authority

    def is_edge_ai_in_control(self) -> bool:
        """Edge AI가 제어 중인지"""
        return self.current_authority == ControlAuthority.EDGE_AI_PRIMARY

    def is_failsafe_active(self) -> bool:
        """Fail-Safe 모드인지"""
        return self.current_authority == ControlAuthority.FAILSAFE

    def get_redundancy_status(self) -> Dict:
        """이중화 상태"""
        return {
            "current_authority": self.current_authority.value,
            "system_health": self.system_health.value,
            "last_edge_ai_response": self.last_edge_ai_response.isoformat() if self.last_edge_ai_response else None,
            "last_plc_response": self.last_plc_response.isoformat() if self.last_plc_response else None,
            "failover_count": len(self.failover_history),
            "component_health": {
                comp: {
                    "status": health.status.value,
                    "last_check": health.last_check.isoformat(),
                    "error": health.error_message
                }
                for comp, health in self.health_checks.items()
            }
        }

    def get_failover_history(self, limit: int = 10) -> List[Dict]:
        """Failover 이력"""
        recent_events = self.failover_history[-limit:]

        return [
            {
                "timestamp": event.timestamp.isoformat(),
                "from": event.from_authority.value,
                "to": event.to_authority.value,
                "reason": event.reason,
                "recovery_time_s": event.recovery_time_seconds
            }
            for event in recent_events
        ]


def create_redundancy_manager(
    communication_timeout_seconds: int = 10,
    auto_recovery: bool = True
) -> RedundancyManager:
    """이중화 관리자 생성"""
    config = RedundancyConfig(
        communication_timeout_seconds=communication_timeout_seconds,
        auto_recovery_enabled=auto_recovery
    )
    return RedundancyManager(config)
