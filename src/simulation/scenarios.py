"""
ESS AI System - 시뮬레이션 시나리오
5가지 Rule-based AI 제어 검증 시나리오:
1. 기본 제어 검증 (정상 조건)
2. 고부하 제어 검증 (Rule R4)
3. 냉각기 과열 보호 검증 (Rule S1)
4. 압력 안전 제어 검증 (Rule S3)
5. E/R 온도 제어 검증 (Rule S4)
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
    ER_VENTILATION = "er_ventilation"  # E/R 환기 불량


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
        self.time_multiplier: float = 1.0  # 시간 배율 (1.0 = 정상, 2.0 = 2배속, 5.0 = 5배속)

    def _create_scenarios(self) -> Dict[ScenarioType, ScenarioConfig]:
        """5가지 Rule-based AI 제어 검증 시나리오 생성"""
        scenarios = {}

        # 1. 기본 제어 검증
        scenarios[ScenarioType.NORMAL_OPERATION] = ScenarioConfig(
            name="기본 제어 검증",
            description="정상 조건에서 ML 예측 및 최적화 제어 검증 (열대 해역, 75% 엔진 부하)",
            scenario_type=ScenarioType.NORMAL_OPERATION,
            duration_minutes=30,
            temperature_profile=self._normal_temperature,
            pressure_profile=self._normal_pressure,
            load_profile=self._normal_load
        )

        # 2. 고부하 제어 검증
        scenarios[ScenarioType.HIGH_LOAD] = ScenarioConfig(
            name="고부하 제어 검증",
            description="Rule R4(엔진 부하) 검증 - 고속 항해 + 고온 환경 대응 (95% 부하)",
            scenario_type=ScenarioType.HIGH_LOAD,
            duration_minutes=20,
            temperature_profile=self._high_load_temperature,
            pressure_profile=self._normal_pressure,
            load_profile=self._high_load
        )

        # 3. 냉각기 과열 보호 검증
        scenarios[ScenarioType.COOLING_FAILURE] = ScenarioConfig(
            name="냉각기 과열 보호 검증",
            description="Rule S1(Cooler 과열 보호) 검증 - T2/T3 고온 시 안전 제어",
            scenario_type=ScenarioType.COOLING_FAILURE,
            duration_minutes=15,
            temperature_profile=self._cooling_failure_temperature,
            pressure_profile=self._normal_pressure,
            load_profile=self._normal_load
        )

        # 4. 압력 안전 제어 검증
        scenarios[ScenarioType.PRESSURE_DROP] = ScenarioConfig(
            name="압력 안전 제어 검증",
            description="Rule S3(압력 제약) 검증 - SW 펌프 압력 저하 시 보호 제어",
            scenario_type=ScenarioType.PRESSURE_DROP,
            duration_minutes=10,
            temperature_profile=self._normal_temperature,
            pressure_profile=self._pressure_drop,
            load_profile=self._normal_load
        )

        # 5. E/R 온도 제어 검증 (Rule S4 검증: T6 온도 전체 범위 제어 테스트)
        scenarios[ScenarioType.ER_VENTILATION] = ScenarioConfig(
            name="E/R 온도 제어 검증",
            description="T6 온도 변화에 따른 주파수 및 대수 제어 검증 (정상→고온→대수증가→정상복귀→저온→대수감소)",
            scenario_type=ScenarioType.ER_VENTILATION,
            duration_minutes=15,  # 전체 사이클 15분 (900초)
            temperature_profile=self._er_ventilation_temperature,
            pressure_profile=self._normal_pressure,
            load_profile=self._medium_load  # 중부하 (Rule R4 영향 제거)
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

    def _er_ventilation_temperature(self, t: float) -> Dict[str, float]:
        """
        E/R 환기 불량 시나리오 - T6 온도 기반 Rule-based 제어 검증
        
        === Rule R3 검증 시나리오 ===
        
        초기 상태: 3대 48Hz, T6 = 43°C (정상 범위)
        
        Phase 1 (0-120초, 2분): 정상 범위 유지 (42~44°C)
            - T6: 43°C 유지
            - 예상 제어: R3_T6_NORMAL_HOLD (48Hz 유지, 3대)
            - 목적: 정상 범위에서 안정 유지 확인
        
        Phase 2 (120-180초, 1분): 온도 상승 시작 (44→45.5°C)
            - T6: 44°C → 45.5°C (45°C 초과)
            - 예상 제어: S3_ER_HIGH_TEMP (강제 60Hz, 3대)
            - 목적: 긴급 고온 시 60Hz 강제 확인
        
        Phase 3 (180-300초, 2분): 고온 유지 (45~46°C)
            - T6: 45.5°C → 46.0°C 유지
            - 예상 제어: 60Hz 유지 → 10초 후 4대 증가
            - 목적: 대수 증가 로직 확인 (60Hz 10초 지속)
        
        Phase 4 (300-420초, 2분): 온도 하강 시작 (46→44°C)
            - T6: 46°C → 44°C (정상 범위 진입)
            - 예상 제어: R3_T6_NORMAL_DECREASING (60Hz → 48Hz 단계적 감소, 4대)
            - 목적: 정상 범위 복귀 시 목표 주파수 수렴 확인
        
        Phase 5 (420-540초, 2분): 정상 범위 유지 (43°C)
            - T6: 43°C 유지
            - 예상 제어: R3_T6_NORMAL_HOLD (48Hz 유지, 4대)
            - 목적: 4대 상태에서 안정 유지 확인
        
        Phase 6 (540-660초, 2분): 저온 진입 (43→38°C)
            - T6: 43°C → 38°C (매우 낮음 범위)
            - 예상 제어: R3_T6_LOW + R3_T6_VERY_LOW (48Hz → 40Hz 단계적 감소, 4대)
            - 목적: 저온 시 최소 주파수(40Hz)까지 감소 확인
        
        Phase 7 (660-780초, 2분): 최소 주파수 유지 (38°C)
            - T6: 38°C 유지
            - 예상 제어: 40Hz 10초 지속 → 3대 감소 (40Hz → 48Hz)
            - 목적: 대수 감소 로직 확인 (40Hz 이하 + 10초 지속)
        
        Phase 8 (780-900초, 2분): 안정 복귀 (38→42°C)
            - T6: 38°C → 42°C (대수 감소 후 주파수 재조정)
            - 예상 제어: R3_T6_VERY_LOW → R3_T6_NORMAL_INCREASING (48Hz 유지 → 정상 복귀)
            - 목적: 대수 감소 후 정상 범위 복귀 확인
        """
        noise = np.random.normal(0, 0.2)  # 노이즈 감소 (명확한 온도 추이)
        
        # Phase 1 (0-120초): 정상 범위 유지
        if t <= 120:
            t6_temp = 43.0
        
        # Phase 2 (120-180초): 온도 상승 → 45°C 초과
        elif t <= 180:
            t6_temp = 43.0 + ((t - 120) / 60.0) * 2.5  # 43 → 45.5°C
        
        # Phase 3 (180-300초): 고온 유지 (대수 증가 트리거)
        elif t <= 300:
            t6_temp = 45.5 + ((t - 180) / 120.0) * 0.5  # 45.5 → 46.0°C
        
        # Phase 4 (300-420초): 온도 하강 → 정상 범위 복귀
        elif t <= 420:
            t6_temp = 46.0 - ((t - 300) / 120.0) * 2.0  # 46 → 44°C
        
        # Phase 5 (420-540초): 정상 범위 유지
        elif t <= 540:
            t6_temp = 43.0
        
        # Phase 6 (540-660초): 저온 진입 (최소 주파수까지 감속 유도)
        elif t <= 660:
            t6_temp = 43.0 - ((t - 540) / 120.0) * 5.0  # 43 → 38°C
        
        # Phase 7 (660-780초): 최소 주파수 유지 (대수 감소 트리거)
        elif t <= 780:
            t6_temp = 38.0  # 38°C 고정 유지 → 40Hz 도달 → 10초 후 3대 감소
        
        # Phase 8 (780-900초): 안정 복귀
        elif t <= 900:
            t6_temp = 38.0 + ((t - 780) / 120.0) * 4.0  # 38 → 42°C
        
        # 시나리오 종료 후 (900초 초과): 정상 온도 유지
        else:
            t6_temp = 42.0  # 정상 범위 하한 유지
        
        return {
            'T1': 25.0 + noise,  # 해수 입구 (온대 해역 - Rule R5 영향 제거)
            'T2': 42.0 + noise,  # SW 출구 1 (정상)
            'T3': 43.0 + noise,  # SW 출구 2 (정상)
            'T4': 45.0 + noise,  # FW 입구 (정상)
            'T5': 33.0 + noise,  # FW 출구 (정상)
            'T6': t6_temp + noise,  # E/R 온도 (Rule R3 검증)
            'T7': 32.0 + noise   # 외기 (정상)
        }

    # ========== 압력 프로파일 ==========

    def _normal_pressure(self, t: float) -> float:
        """정상 압력"""
        noise = np.random.normal(0, 0.05)
        return 2.0 + noise

    def _pressure_drop(self, t: float) -> float:
        """압력 저하"""
        # 2분에 걸쳐 압력 하락 (2.0 bar → 0.7 bar)
        # 120초 동안 1.3 bar 하락
        pressure_drop = min(1.3, (t / 120.0) * 1.3)
        noise = np.random.normal(0, 0.05)
        return max(0.5, 2.0 - pressure_drop + noise)  # 최소 0.5 bar까지 하락

    # ========== 부하 프로파일 ==========

    def _normal_load(self, t: float) -> float:
        """정상 부하 (75%)"""
        noise = np.random.normal(0, 3.0)
        return 75.0 + noise
    
    def _medium_load(self, t: float) -> float:
        """중부하 (50%) - Rule R4 영향 없음 (30-70% 구간)"""
        noise = np.random.normal(0, 2.0)
        return 50.0 + noise

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
        try:
            print(f"🎬 시나리오 시작: {self.current_scenario.name}")
            print(f"   {self.current_scenario.description}")
        except UnicodeEncodeError:
            # Windows 터미널 인코딩 문제 대응
            print(f"[시나리오 시작] {self.current_scenario.name}")
            print(f"   {self.current_scenario.description}")

    def set_time_multiplier(self, multiplier: float) -> None:
        """시간 배율 설정"""
        self.time_multiplier = max(0.1, min(10.0, multiplier))  # 0.1배 ~ 10배 제한

    def get_time_multiplier(self) -> float:
        """현재 시간 배율 반환"""
        return self.time_multiplier

    def get_current_values(self) -> Dict[str, float]:
        """현재 센서 값 조회"""
        if self.current_scenario is None:
            # 기본값 (정상 운전)
            self.start_scenario(ScenarioType.NORMAL_OPERATION)

        # 경과 시간 계산 (시간 배율 적용)
        if self.scenario_start_time:
            real_elapsed = (datetime.now() - self.scenario_start_time).total_seconds()
            self.elapsed_seconds = real_elapsed * self.time_multiplier

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
