"""
ESS AI System - Modbus TCP 통신 시스템
Xavier NX ↔ Siemens PLC 통신 (2초 주기)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import time
import threading
import logging


class ConnectionStatus(Enum):
    """연결 상태"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    BACKUP_MODE = "backup_mode"


class CommunicationMode(Enum):
    """통신 모드"""
    PRIMARY = "primary"  # Edge AI 주 제어
    BACKUP = "backup"  # PLC 백업 제어
    FAILSAFE = "failsafe"  # 안전 모드


@dataclass
class ModbusConfig:
    """Modbus TCP 설정"""
    plc_ip: str = "192.168.1.10"
    plc_port: int = 502
    timeout_seconds: int = 5
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    heartbeat_interval_seconds: int = 10
    failsafe_timeout_seconds: int = 10
    cycle_time_seconds: float = 2.0  # AI 추론 주기


@dataclass
class ConnectionStats:
    """연결 통계"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    reconnection_count: int = 0
    last_successful_read: Optional[datetime] = None
    last_error: Optional[str] = None
    uptime_start: datetime = field(default_factory=datetime.now)

    def get_success_rate(self) -> float:
        """성공률 계산"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100.0

    def get_uptime_hours(self) -> float:
        """가동 시간 (시간)"""
        return (datetime.now() - self.uptime_start).total_seconds() / 3600.0


class ModbusTCPClient:
    """
    Modbus TCP 클라이언트
    Siemens PLC와 통신 (S7 프로토콜 기반)
    """

    def __init__(self, config: ModbusConfig, simulation_mode: bool = True):
        self.config = config
        self.simulation_mode = simulation_mode
        self.status = ConnectionStatus.DISCONNECTED
        self.mode = CommunicationMode.PRIMARY
        self.stats = ConnectionStats()

        # Modbus 클라이언트 (실제 환경에서는 pymodbus 사용)
        self.client = None
        self.connected = False

        # Heartbeat
        self.last_heartbeat: Optional[datetime] = None
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.running = False

        # 로깅
        self.logger = logging.getLogger("ModbusTCP")
        self.logger.setLevel(logging.INFO)

    def connect(self) -> bool:
        """PLC 연결"""
        self.status = ConnectionStatus.CONNECTING
        self.logger.info(f"Connecting to PLC {self.config.plc_ip}:{self.config.plc_port}...")

        if self.simulation_mode:
            # 시뮬레이션 모드
            time.sleep(0.5)
            self.connected = True
            self.status = ConnectionStatus.CONNECTED
            self.last_heartbeat = datetime.now()
            self.logger.info("✅ Connected (Simulation Mode)")
            return True

        # 실제 PLC 연결
        try:
            # TODO: pymodbus 클라이언트 연결
            # from pymodbus.client import ModbusTcpClient
            # self.client = ModbusTcpClient(
            #     host=self.config.plc_ip,
            #     port=self.config.plc_port,
            #     timeout=self.config.timeout_seconds
            # )
            # self.connected = self.client.connect()

            self.connected = False  # 실제 PLC 미연결
            self.status = ConnectionStatus.FAILED
            self.logger.warning("⚠️ Real PLC not available - switching to simulation mode")
            self.simulation_mode = True
            return self.connect()

        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            self.status = ConnectionStatus.FAILED
            self.stats.last_error = str(e)
            return False

    def disconnect(self) -> None:
        """연결 해제"""
        self.running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=2.0)

        if self.client and hasattr(self.client, 'close'):
            self.client.close()

        self.connected = False
        self.status = ConnectionStatus.DISCONNECTED
        self.logger.info("🔌 Disconnected from PLC")

    def read_holding_registers(self, address: int, count: int) -> Optional[List[int]]:
        """
        Holding Register 읽기
        Siemens PLC의 데이터 블록 읽기
        """
        self.stats.total_requests += 1

        if not self.connected:
            self.stats.failed_requests += 1
            return None

        if self.simulation_mode:
            # 시뮬레이션 데이터 생성
            import random
            data = [int(random.uniform(0, 1000)) for _ in range(count)]
            self.stats.successful_requests += 1
            self.stats.last_successful_read = datetime.now()
            return data

        try:
            # 실제 Modbus 읽기
            # result = self.client.read_holding_registers(address, count)
            # if result.isError():
            #     raise Exception(f"Modbus read error: {result}")
            # self.stats.successful_requests += 1
            # self.stats.last_successful_read = datetime.now()
            # return result.registers

            self.stats.failed_requests += 1
            return None

        except Exception as e:
            self.logger.error(f"❌ Read error at address {address}: {e}")
            self.stats.failed_requests += 1
            self.stats.last_error = str(e)
            return None

    def write_register(self, address: int, value: int) -> bool:
        """단일 레지스터 쓰기"""
        self.stats.total_requests += 1

        if not self.connected:
            self.stats.failed_requests += 1
            return False

        if self.simulation_mode:
            # 시뮬레이션 쓰기
            self.logger.debug(f"📤 [SIM] Write to {address}: {value}")
            self.stats.successful_requests += 1
            return True

        try:
            # 실제 Modbus 쓰기
            # result = self.client.write_register(address, value)
            # if result.isError():
            #     raise Exception(f"Modbus write error: {result}")
            # self.stats.successful_requests += 1
            # return True

            self.stats.failed_requests += 1
            return False

        except Exception as e:
            self.logger.error(f"❌ Write error at address {address}: {e}")
            self.stats.failed_requests += 1
            self.stats.last_error = str(e)
            return False

    def write_multiple_registers(self, address: int, values: List[int]) -> bool:
        """다중 레지스터 쓰기"""
        self.stats.total_requests += 1

        if not self.connected:
            self.stats.failed_requests += 1
            return False

        if self.simulation_mode:
            self.logger.debug(f"📤 [SIM] Write to {address}: {len(values)} registers")
            self.stats.successful_requests += 1
            return True

        try:
            # 실제 Modbus 쓰기
            # result = self.client.write_registers(address, values)
            # if result.isError():
            #     raise Exception(f"Modbus write error: {result}")
            # self.stats.successful_requests += 1
            # return True

            self.stats.failed_requests += 1
            return False

        except Exception as e:
            self.logger.error(f"❌ Write error at address {address}: {e}")
            self.stats.failed_requests += 1
            self.stats.last_error = str(e)
            return False

    def reconnect(self) -> bool:
        """재연결 시도"""
        self.status = ConnectionStatus.RECONNECTING
        self.logger.info("🔄 Attempting to reconnect...")

        for attempt in range(self.config.retry_attempts):
            self.logger.info(f"  Retry {attempt + 1}/{self.config.retry_attempts}")

            if self.connect():
                self.stats.reconnection_count += 1
                self.logger.info("✅ Reconnection successful")
                return True

            time.sleep(self.config.retry_delay_seconds)

        self.logger.error("❌ Reconnection failed - switching to backup mode")
        self.status = ConnectionStatus.BACKUP_MODE
        self.mode = CommunicationMode.BACKUP
        return False

    def check_heartbeat(self) -> bool:
        """Heartbeat 확인"""
        if self.last_heartbeat is None:
            return False

        elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
        return elapsed < self.config.heartbeat_interval_seconds

    def send_heartbeat(self) -> bool:
        """Heartbeat 전송"""
        # Heartbeat 신호를 특정 레지스터에 쓰기
        success = self.write_register(9999, 1)  # Heartbeat 주소 (예시)
        if success:
            self.last_heartbeat = datetime.now()
        return success

    def start_heartbeat_monitor(self) -> None:
        """Heartbeat 모니터링 시작"""
        def heartbeat_loop():
            while self.running:
                if not self.check_heartbeat():
                    self.logger.warning("⚠️ Heartbeat timeout - attempting reconnection")
                    self.reconnect()

                time.sleep(self.config.heartbeat_interval_seconds)

        self.running = True
        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        self.logger.info("💓 Heartbeat monitor started")

    def switch_to_backup_mode(self) -> None:
        """백업 모드로 전환"""
        self.mode = CommunicationMode.BACKUP
        self.logger.warning("⚠️ Switched to BACKUP mode - PLC takes control")

    def switch_to_primary_mode(self) -> None:
        """주 모드로 복귀"""
        self.mode = CommunicationMode.PRIMARY
        self.logger.info("✅ Switched to PRIMARY mode - Edge AI takes control")

    def enter_failsafe_mode(self) -> None:
        """Fail-Safe 모드 진입"""
        self.mode = CommunicationMode.FAILSAFE
        self.logger.critical("🚨 FAILSAFE MODE - System in safe state")

    def get_connection_info(self) -> Dict:
        """연결 정보"""
        return {
            "status": self.status.value,
            "mode": self.mode.value,
            "simulation": self.simulation_mode,
            "plc_ip": self.config.plc_ip,
            "plc_port": self.config.plc_port,
            "connected": self.connected,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "stats": {
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "success_rate": f"{self.stats.get_success_rate():.2f}%",
                "reconnection_count": self.stats.reconnection_count,
                "uptime_hours": f"{self.stats.get_uptime_hours():.2f}h",
                "last_error": self.stats.last_error
            }
        }


def create_modbus_client(
    plc_ip: str = "192.168.1.10",
    plc_port: int = 502,
    simulation_mode: bool = True
) -> ModbusTCPClient:
    """Modbus 클라이언트 생성"""
    config = ModbusConfig(plc_ip=plc_ip, plc_port=plc_port)
    return ModbusTCPClient(config, simulation_mode)
