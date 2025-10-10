"""
ESS AI System - 실시간 데이터 수집 및 버퍼링
2초 주기 데이터 수집, 10분 버퍼링 (300 포인트)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Deque
from collections import deque
import threading
import time
import logging
import numpy as np

from ..models.sensor_data import (
    SensorReading, SystemSensorData, CoolingSystemTemperatures,
    VentilationSystemTemperatures, PressureData, OperatingConditions
)
from ..communication.modbus_client import ModbusTCPClient


@dataclass
class DataCollectionStats:
    """데이터 수집 통계"""
    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    missing_data_count: int = 0
    interpolated_count: int = 0
    outlier_count: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    def get_collection_rate(self) -> float:
        """수집률 (%))"""
        if self.total_cycles == 0:
            return 0.0
        return (self.successful_cycles / self.total_cycles) * 100.0

    def get_data_quality_score(self) -> float:
        """데이터 품질 점수"""
        if self.total_cycles == 0:
            return 0.0

        # 수집률 + 이상치 비율 고려
        collection_score = self.get_collection_rate()
        outlier_penalty = (self.outlier_count / max(self.total_cycles, 1)) * 100.0
        quality = collection_score - outlier_penalty

        return max(0.0, min(100.0, quality))


@dataclass
class DataBuffer:
    """
    데이터 버퍼
    최근 10분 데이터 저장 (2초 주기 × 300개)
    """
    max_size: int = 300  # 10분 = 600초 ÷ 2초 = 300개
    buffer: Deque[SystemSensorData] = field(default_factory=deque)

    def add(self, data: SystemSensorData) -> None:
        """데이터 추가"""
        self.buffer.append(data)
        if len(self.buffer) > self.max_size:
            self.buffer.popleft()

    def get_latest(self) -> Optional[SystemSensorData]:
        """최신 데이터"""
        if len(self.buffer) == 0:
            return None
        return self.buffer[-1]

    def get_last_n(self, n: int) -> List[SystemSensorData]:
        """최근 N개 데이터"""
        return list(self.buffer)[-n:]

    def get_time_range(self, minutes: int) -> List[SystemSensorData]:
        """최근 N분 데이터"""
        if len(self.buffer) == 0:
            return []

        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [d for d in self.buffer if d.timestamp >= cutoff_time]

    def get_size(self) -> int:
        """버퍼 크기"""
        return len(self.buffer)

    def is_full(self) -> bool:
        """버퍼가 꽉 찼는지"""
        return len(self.buffer) >= self.max_size

    def clear(self) -> None:
        """버퍼 클리어"""
        self.buffer.clear()


class RealTimeDataCollector:
    """
    실시간 데이터 수집기
    - 2초 주기 데이터 수집
    - 10분 버퍼링
    - 데이터 품질 관리
    """

    def __init__(
        self,
        modbus_client: ModbusTCPClient,
        cycle_time_seconds: float = 2.0
    ):
        self.modbus_client = modbus_client
        self.cycle_time = cycle_time_seconds

        # 데이터 버퍼
        self.buffer = DataBuffer()

        # 통계
        self.stats = DataCollectionStats()

        # 수집 스레드
        self.collection_thread: Optional[threading.Thread] = None
        self.running = False

        # 이전 데이터 (결측값 보간용)
        self.previous_data: Optional[Dict[str, float]] = None

        # 로깅
        self.logger = logging.getLogger("DataCollector")
        self.logger.setLevel(logging.INFO)

    def start(self) -> None:
        """데이터 수집 시작"""
        if self.running:
            self.logger.warning("⚠️ Data collection already running")
            return

        self.running = True
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        self.logger.info(f"▶️ Data collection started (cycle: {self.cycle_time}s)")

    def stop(self) -> None:
        """데이터 수집 중지"""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=5.0)
        self.logger.info("⏹️ Data collection stopped")

    def _collection_loop(self) -> None:
        """데이터 수집 루프"""
        while self.running:
            cycle_start = time.time()

            try:
                # 센서 데이터 읽기
                sensor_data = self._read_all_sensors()

                if sensor_data:
                    # 버퍼에 추가
                    self.buffer.add(sensor_data)
                    self.stats.successful_cycles += 1

                    # 이전 데이터 업데이트
                    self.previous_data = self._extract_raw_values(sensor_data)
                else:
                    self.stats.failed_cycles += 1
                    self.logger.warning(f"⚠️ Failed to read sensor data (cycle {self.stats.total_cycles})")

                self.stats.total_cycles += 1

            except Exception as e:
                self.logger.error(f"❌ Collection error: {e}")
                self.stats.failed_cycles += 1
                self.stats.total_cycles += 1

            # 주기 유지
            elapsed = time.time() - cycle_start
            sleep_time = max(0, self.cycle_time - elapsed)

            if elapsed > self.cycle_time:
                self.logger.warning(f"⚠️ Cycle time exceeded: {elapsed:.2f}s > {self.cycle_time}s")

            time.sleep(sleep_time)

    def _read_all_sensors(self) -> Optional[SystemSensorData]:
        """모든 센서 데이터 읽기"""
        try:
            # Modbus로부터 센서 값 읽기 (시뮬레이션)
            raw_data = self._read_sensors_from_plc()

            if raw_data is None:
                return None

            # 결측값 처리
            raw_data = self._handle_missing_values(raw_data)

            # SystemSensorData 생성
            sensor_data = self._create_sensor_data(raw_data)

            return sensor_data

        except Exception as e:
            self.logger.error(f"❌ Sensor read error: {e}")
            return None

    def _read_sensors_from_plc(self) -> Optional[Dict[str, float]]:
        """PLC로부터 센서 데이터 읽기"""
        # 시뮬레이션 모드에서는 임의 값 생성
        if self.modbus_client.simulation_mode:
            import random
            return {
                'T1': 28.0 + random.uniform(-1.0, 1.0),
                'T2': 42.0 + random.uniform(-2.0, 2.0),
                'T3': 43.0 + random.uniform(-2.0, 2.0),
                'T4': 45.0 + random.uniform(-1.5, 1.5),
                'T5': 33.0 + random.uniform(-1.0, 1.0),
                'T6': 43.0 + random.uniform(-1.0, 1.0),
                'T7': 32.0 + random.uniform(-2.0, 2.0),
                'PX1': 2.0 + random.uniform(-0.2, 0.2),
                'engine_load': 75.0 + random.uniform(-10.0, 10.0),
                'gps_lat': 14.5,
                'gps_lon': 120.5,
                'gps_speed': 18.5 + random.uniform(-1.0, 1.0)
            }

        # 실제 PLC 읽기
        # TODO: Modbus 레지스터 읽기 구현
        return None

    def _handle_missing_values(self, data: Dict[str, float]) -> Dict[str, float]:
        """결측값 처리"""
        for key, value in data.items():
            if value is None or np.isnan(value):
                # 이전 값 사용
                if self.previous_data and key in self.previous_data:
                    data[key] = self.previous_data[key]
                    self.stats.interpolated_count += 1
                    self.logger.warning(f"⚠️ Interpolated missing value for {key}")
                else:
                    # 기본값 사용
                    data[key] = self._get_default_value(key)
                    self.stats.missing_data_count += 1

        return data

    def _get_default_value(self, sensor_id: str) -> float:
        """기본값 반환"""
        defaults = {
            'T1': 28.0, 'T2': 42.0, 'T3': 43.0, 'T4': 45.0,
            'T5': 33.0, 'T6': 43.0, 'T7': 32.0, 'PX1': 2.0,
            'engine_load': 50.0, 'gps_lat': 0.0, 'gps_lon': 0.0,
            'gps_speed': 0.0
        }
        return defaults.get(sensor_id, 0.0)

    def _extract_raw_values(self, sensor_data: SystemSensorData) -> Dict[str, float]:
        """센서 데이터에서 원시 값 추출"""
        return {
            'T1': sensor_data.cooling.T1.value,
            'T2': sensor_data.cooling.T2.value,
            'T3': sensor_data.cooling.T3.value,
            'T4': sensor_data.cooling.T4.value,
            'T5': sensor_data.cooling.T5.value,
            'T6': sensor_data.ventilation.T6.value,
            'T7': sensor_data.ventilation.T7.value,
            'PX1': sensor_data.pressure.PX1.value,
            'engine_load': sensor_data.operating.engine_load,
            'gps_lat': sensor_data.operating.gps_latitude,
            'gps_lon': sensor_data.operating.gps_longitude,
            'gps_speed': sensor_data.operating.gps_speed
        }

    def _create_sensor_data(self, raw_data: Dict[str, float]) -> SystemSensorData:
        """센서 데이터 객체 생성"""
        now = datetime.now()

        cooling = CoolingSystemTemperatures(
            T1=SensorReading(raw_data['T1'], now),
            T2=SensorReading(raw_data['T2'], now),
            T3=SensorReading(raw_data['T3'], now),
            T4=SensorReading(raw_data['T4'], now),
            T5=SensorReading(raw_data['T5'], now)
        )

        ventilation = VentilationSystemTemperatures(
            T6=SensorReading(raw_data['T6'], now),
            T7=SensorReading(raw_data['T7'], now)
        )

        pressure = PressureData(
            PX1=SensorReading(raw_data['PX1'], now)
        )

        operating = OperatingConditions(
            engine_load=raw_data['engine_load'],
            gps_latitude=raw_data['gps_lat'],
            gps_longitude=raw_data['gps_lon'],
            gps_speed=raw_data['gps_speed'],
            utc_time=now
        )

        return SystemSensorData(
            cooling=cooling,
            ventilation=ventilation,
            pressure=pressure,
            operating=operating,
            timestamp=now
        )

    def get_latest_data(self) -> Optional[SystemSensorData]:
        """최신 데이터 조회"""
        return self.buffer.get_latest()

    def get_recent_data(self, minutes: int = 10) -> List[SystemSensorData]:
        """최근 N분 데이터 조회"""
        return self.buffer.get_time_range(minutes)

    def get_buffer_status(self) -> Dict:
        """버퍼 상태"""
        return {
            "size": self.buffer.get_size(),
            "max_size": self.buffer.max_size,
            "is_full": self.buffer.is_full(),
            "coverage_minutes": (self.buffer.get_size() * self.cycle_time) / 60.0
        }

    def get_collection_stats(self) -> Dict:
        """수집 통계"""
        return {
            "total_cycles": self.stats.total_cycles,
            "successful_cycles": self.stats.successful_cycles,
            "failed_cycles": self.stats.failed_cycles,
            "collection_rate": f"{self.stats.get_collection_rate():.2f}%",
            "missing_data_count": self.stats.missing_data_count,
            "interpolated_count": self.stats.interpolated_count,
            "outlier_count": self.stats.outlier_count,
            "data_quality_score": f"{self.stats.get_data_quality_score():.2f}",
            "running_time": str(datetime.now() - self.stats.start_time).split('.')[0]
        }

    def get_status_summary(self) -> str:
        """상태 요약"""
        stats = self.get_collection_stats()
        buffer = self.get_buffer_status()

        summary = []
        summary.append(f"📊 Data Collection Status")
        summary.append(f"  Running: {'✅ Yes' if self.running else '❌ No'}")
        summary.append(f"  Cycle Time: {self.cycle_time}s")
        summary.append(f"  Collection Rate: {stats['collection_rate']}")
        summary.append(f"  Data Quality: {stats['data_quality_score']}")
        summary.append(f"  Buffer: {buffer['size']}/{buffer['max_size']} ({buffer['coverage_minutes']:.1f} min)")
        summary.append(f"  Total Cycles: {stats['total_cycles']}")
        summary.append(f"  Running Time: {stats['running_time']}")

        return "\n".join(summary)


def create_data_collector(
    modbus_client: ModbusTCPClient,
    cycle_time_seconds: float = 2.0
) -> RealTimeDataCollector:
    """데이터 수집기 생성"""
    return RealTimeDataCollector(modbus_client, cycle_time_seconds)
