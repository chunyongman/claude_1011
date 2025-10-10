"""
ESS AI System - 시뮬레이션 시나리오
4가지 주요 시나리오: 정상 운전, 고부하, 냉각 실패, 압력 저하
"""

from dataclasses import dataclass
from typing import Dict, Callable
from enum import Enum
import numpy as np
from datetime import datetime


class ScenarioType(Enum):
    """시나리오 타입"""
    NORMAL_OPERATION = "normal_operation"
    HIGH_LOAD = "high_load"
    COOLING_FAILURE = "cooling_failure"
    PRESSURE_DROP = "pressure_drop"


@dataclass
class ScenarioConfig:
    """시나리오 설정"""
    name: str
    description: str
    scenario_type: ScenarioType
    duration_minutes: int
    temperature_profile: Callable
    pressure_profile: Callable
    load_profile: Callable


class SimulationScenarios:
    """시뮬레이션 시나리오 생성기"""

    def __init__(self):
        self.scenarios = self._create_scenarios()
        self.current_scenario: Optional[ScenarioConfig] = None
        self.scenario_start_time: Optional[datetime] = None
        self.elapsed_seconds: float = 0.0

    def _create_scenarios(self) -> Dict[ScenarioType, ScenarioConfig]:
        """4가지 시나리오 생성"""
        scenarios = {}

        # 1. 정상 운전
        scenarios[ScenarioType.NORMAL_OPERATION] = ScenarioConfig(
            name="정상 운전",
            description="정상적인 항해 조건 (열대 해역, 75% 엔진 부하)",
            scenario_type=ScenarioType.NORMAL_OPERATION,
            duration_minutes=30,
            temperature_profile=self._normal_temperature,
            pressure_profile=self._normal_pressure,
            load_profile=self._normal_load
        )

        # 2. 고부하 운전
        scenarios[ScenarioType.HIGH_LOAD] = ScenarioConfig(
            name="고부하 운전",
            description="고속 항해 + 고온 환경 (95% 엔진 부하)",
            scenario_type=ScenarioType.HIGH_LOAD,
            duration_minutes=20,
            temperature_profile=self._high_load_temperature,
            pressure_profile=self._normal_pressure,
            load_profile=self._high_load
        )

        # 3. 냉각 실패
        scenarios[ScenarioType.COOLING_FAILURE] = ScenarioConfig(
            name="냉각 실패",
            description="냉각 성능 저하로 온도 상승",
            scenario_type=ScenarioType.COOLING_FAILURE,
            duration_minutes=15,
            temperature_profile=self._cooling_failure_temperature,
            pressure_profile=self._normal_pressure,
            load_profile=self._normal_load
        )

        # 4. 압력 저하
        scenarios[ScenarioType.PRESSURE_DROP] = ScenarioConfig(
            name="압력 저하",
            description="SW 펌프 압력 저하 시나리오",
            scenario_type=ScenarioType.PRESSURE_DROP,
            duration_minutes=10,
            temperature_profile=self._normal_temperature,
            pressure_profile=self._pressure_drop,
            load_profile=self._normal_load
        )

        return scenarios

    # ========== 온도 프로파일 ==========

    def _normal_temperature(self, t: float) -> Dict[str, float]:
        """
        정상 운전 온도
        t: 경과 시간 (초)
        """
        # 작은 변동 추가
        noise = np.random.normal(0, 0.5)

        return {
            'T1': 28.0 + noise,  # SW 입구
            'T2': 42.0 + noise,  # SW 출구 1
            'T3': 43.0 + noise,  # SW 출구 2
            'T4': 45.0 + noise,  # FW 입구
            'T5': 33.0 + noise,  # FW 출구
            'T6': 43.0 + noise,  # E/R 온도
            'T7': 32.0 + noise   # 외기
        }

    def _high_load_temperature(self, t: float) -> Dict[str, float]:
        """
        고부하 운전 온도
        온도가 점진적으로 상승
        """
        # 10분에 걸쳐 온도 상승
        temp_increase = min(5.0, (t / 600.0) * 5.0)
        noise = np.random.normal(0, 0.8)

        return {
            'T1': 30.0 + noise,
            'T2': 45.0 + temp_increase + noise,
            'T3': 46.0 + temp_increase + noise,
            'T4': 46.5 + temp_increase + noise,
            'T5': 35.0 + temp_increase * 0.5 + noise,
            'T6': 46.0 + temp_increase + noise,
            'T7': 35.0 + noise
        }

    def _cooling_failure_temperature(self, t: float) -> Dict[str, float]:
        """
        냉각 실패 온도
        급격한 온도 상승
        """
        # 5분에 걸쳐 급격한 온도 상승
        temp_spike = min(8.0, (t / 300.0) * 8.0)
        noise = np.random.normal(0, 1.0)

        return {
            'T1': 28.0 + noise,
            'T2': 42.0 + temp_spike + noise,  # 최대 50°C까지 상승
            'T3': 43.0 + temp_spike + noise,
            'T4': 45.0 + temp_spike * 0.5 + noise,
            'T5': 33.0 + temp_spike * 0.7 + noise,  # FW 출구도 상승
            'T6': 43.0 + temp_spike * 1.2 + noise,  # E/R 온도 급상승
            'T7': 32.0 + noise
        }

    # ========== 압력 프로파일 ==========

    def _normal_pressure(self, t: float) -> float:
        """정상 압력"""
        noise = np.random.normal(0, 0.05)
        return 2.0 + noise

    def _pressure_drop(self, t: float) -> float:
        """압력 저하"""
        # 3분에 걸쳐 압력 하락
        pressure_drop = min(0.8, (t / 180.0) * 0.8)
        noise = np.random.normal(0, 0.05)
        return max(1.0, 2.0 - pressure_drop + noise)

    # ========== 부하 프로파일 ==========

    def _normal_load(self, t: float) -> float:
        """정상 부하 (75%)"""
        noise = np.random.normal(0, 3.0)
        return 75.0 + noise

    def _high_load(self, t: float) -> float:
        """고부하 (95%)"""
        noise = np.random.normal(0, 2.0)
        return 95.0 + noise

    # ========== 시나리오 실행 ==========

    def start_scenario(self, scenario_type: ScenarioType) -> None:
        """시나리오 시작"""
        self.current_scenario = self.scenarios[scenario_type]
        self.scenario_start_time = datetime.now()
        self.elapsed_seconds = 0.0
        print(f"🎬 시나리오 시작: {self.current_scenario.name}")
        print(f"   {self.current_scenario.description}")

    def get_current_values(self) -> Dict[str, float]:
        """현재 센서 값 조회"""
        if self.current_scenario is None:
            # 기본값 (정상 운전)
            self.start_scenario(ScenarioType.NORMAL_OPERATION)

        # 경과 시간 계산
        if self.scenario_start_time:
            self.elapsed_seconds = (datetime.now() - self.scenario_start_time).total_seconds()

        # 시나리오별 값 생성
        temps = self.current_scenario.temperature_profile(self.elapsed_seconds)
        pressure = self.current_scenario.pressure_profile(self.elapsed_seconds)
        load = self.current_scenario.load_profile(self.elapsed_seconds)

        # GPS (고정값 - 열대 해역 예시)
        gps_lat = 14.5 + np.random.normal(0, 0.01)
        gps_lon = 120.5 + np.random.normal(0, 0.01)
        gps_speed = 18.5 + np.random.normal(0, 0.5)

        values = {
            **temps,
            'PX1': pressure,
            'engine_load': load,
            'gps_lat': gps_lat,
            'gps_lon': gps_lon,
            'gps_speed': gps_speed
        }

        return values

    def is_scenario_complete(self) -> bool:
        """시나리오 완료 여부"""
        if self.current_scenario is None:
            return False

        duration_seconds = self.current_scenario.duration_minutes * 60
        return self.elapsed_seconds >= duration_seconds

    def get_scenario_progress(self) -> float:
        """시나리오 진행률 (%)"""
        if self.current_scenario is None:
            return 0.0

        duration_seconds = self.current_scenario.duration_minutes * 60
        return min(100.0, (self.elapsed_seconds / duration_seconds) * 100.0)

    def get_available_scenarios(self) -> Dict[str, str]:
        """사용 가능한 시나리오 목록"""
        return {
            scenario_type.value: config.name
            for scenario_type, config in self.scenarios.items()
        }

    def get_scenario_info(self) -> Dict:
        """현재 시나리오 정보"""
        if self.current_scenario is None:
            return {}

        return {
            "name": self.current_scenario.name,
            "type": self.current_scenario.scenario_type.value,
            "description": self.current_scenario.description,
            "duration_minutes": self.current_scenario.duration_minutes,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "progress": f"{self.get_scenario_progress():.1f}%",
            "is_complete": self.is_scenario_complete()
        }


def create_simulation_scenarios() -> SimulationScenarios:
    """시뮬레이션 시나리오 생성"""
    return SimulationScenarios()


# 시나리오별 예상 동작
SCENARIO_EXPECTED_BEHAVIORS = {
    ScenarioType.NORMAL_OPERATION: {
        "expected_control": "펌프 50Hz, 팬 48Hz 정상 운전",
        "ai_action": "현재 상태 유지, 효율 최적화",
        "alert_level": "정상"
    },
    ScenarioType.HIGH_LOAD: {
        "expected_control": "펌프 증속 (55Hz), 팬 증속 (52Hz)",
        "ai_action": "부하 증가 감지, 선제적 냉각 강화",
        "alert_level": "주의"
    },
    ScenarioType.COOLING_FAILURE: {
        "expected_control": "펌프 최대 (60Hz), 전 팬 가동",
        "ai_action": "온도 급상승 감지, 긴급 냉각 강화",
        "alert_level": "경고"
    },
    ScenarioType.PRESSURE_DROP: {
        "expected_control": "펌프 증속 또는 대수 증가",
        "ai_action": "압력 저하 감지, 펌프 성능 보상",
        "alert_level": "주의"
    }
}
