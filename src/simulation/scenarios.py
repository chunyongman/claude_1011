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

        # 2. SW 펌프 제어 검증 (T5 기반 ML 예측 주도 + Rule 보정)
        scenarios[ScenarioType.HIGH_LOAD] = ScenarioConfig(
            name="SW 펌프 제어 검증",
            description="🤖 ML 온도 예측 (선제 대응) + Rule R1 보정 (목표 가속) - 에너지 절감 핵심 기능 검증",
            scenario_type=ScenarioType.HIGH_LOAD,
            duration_minutes=10,  # 10분 (600초)
            temperature_profile=self._sw_pump_control_temperature,
            pressure_profile=self._normal_pressure,
            load_profile=self._medium_load  # 중부하 (Rule R4 영향 제거)
        )

        # 3. FW 펌프 제어 검증 (T4 기반 ML 예측 주도 + Rule 보정)
        scenarios[ScenarioType.COOLING_FAILURE] = ScenarioConfig(
            name="FW 펌프 제어 검증",
            description="🤖 ML 온도 예측 (선제 대응) + Rule R2 보정 (목표 가속) - 에너지 절감 핵심 기능 검증",
            scenario_type=ScenarioType.COOLING_FAILURE,
            duration_minutes=10,
            temperature_profile=self._fw_pump_control_temperature,
            pressure_profile=self._normal_pressure,
            load_profile=self._medium_load  # 중부하 (Rule R4 영향 제거)
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

        # 5. E/R 온도 제어 검증 (Rule S5 검증: T6 온도 전체 범위 + 모든 대수 변화 확인)
        scenarios[ScenarioType.ER_VENTILATION] = ScenarioConfig(
            name="E/R 온도 제어 검증",
            description="T6 온도 피드백 제어 + 전체 대수 변화 검증 (V3 | 3→4대 증설 / 4→3→2대 감소 전체 확인)",
            scenario_type=ScenarioType.ER_VENTILATION,
            duration_minutes=17,  # 전체 사이클 16.5분 (990초) → 17분으로 반올림
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

    def _sw_pump_control_temperature(self, t: float) -> Dict[str, float]:
        """
        SW 펌프 제어 검증 시나리오 - T5 온도 기반 ML 예측 주도 + Rule R1 보정
        
        === 🎯 핵심 가치: 선제적 온도 예측 제어로 에너지 절감 ===
        
        1️⃣ ML Predictive Control (주도) 🤖
           - Temperature Predictor: 30초 후 T5 온도 예측
           - Random Forest: 예측 온도 기반 최적 주파수 추천
           - 목적: 온도가 오르기 **전에** 미리 주파수 조정 (선제 대응)
           - **이것이 기존 ESS 대비 핵심 차별점!**
        
        2️⃣ Rule R1 강화 보정 (보조)
           - ML 예측 주파수에 현재 온도 기반 보정 추가
           - T5 > 38°C: +6Hz | 36~38°C: +4Hz (60Hz 빠른 도달)
           - T5 < 32°C: -6Hz | 32~34°C: -3Hz (40Hz 빠른 도달)
           - 목적: ML 예측을 현재 상태로 강화하여 목표 가속
        
        3️⃣ Safety Layer (극한 상황만)
           - S4: T5 극한 보호 (>40°C 또는 <30°C만 개입)
           - S1, S2, S3: 기타 안전 제약
        
        === 시나리오 타임라인 (10분, 600초) ===
        
        초기 상태: SW 펌프 48Hz, T5 = 35°C (정상 범위)
        
        Phase 1 (0-90초, 1.5분): 정상 범위 유지 (34~36°C)
            - T5: 35°C 유지
            - 예상 제어: ML + Rule 협업 → 48Hz 유지
            - 목적: 정상 범위에서 안정 유지 확인
        
        Phase 2 (90-180초, 1.5분): 온도 급상승 → 매우 높음
            - T5: 35°C → 40°C (극심한 고온)
            - 예상 제어: 
              * ML: "급격한 온도 상승 예측" → 선제적 주파수 대폭 증가
              * Rule R1: T5 > 37°C → +4Hz 추가
            - 목적: 최대 주파수 60Hz 도달 확인
        
        Phase 3 (180-270초, 1.5분): 극고온 유지
            - T5: 40°C 유지
            - 예상 제어: 최대 주파수 유지 (60Hz)
            - 목적: 극한 상황에서 최대 냉각 확인
        
        Phase 4 (270-360초, 1.5분): 온도 하강 → 정상 복귀
            - T5: 40°C → 35°C (정상 범위)
            - 예상 제어:
              * ML: "온도 하강 예측" → 선제적 주파수 감소
              * Rule R1: T5 정상 범위 → 보정 최소화
            - 목적: ML 주도의 부드러운 정상 복귀 (60Hz → 48Hz)
        
        Phase 5 (360-420초, 1분): 정상 범위 유지
            - T5: 35°C 유지
            - 예상 제어: ML 최적화 → 48Hz 안정 유지
            - 목적: 안정 상태 확인
        
        Phase 6 (420-510초, 1.5분): 온도 급하강 → 매우 낮음
            - T5: 35°C → 30°C (극저온)
            - 예상 제어:
              * ML: "급격한 온도 하강 예측" → 선제적 주파수 대폭 감소
              * Rule R1: T5 < 34°C → -2Hz 추가 (에너지 절감)
            - 목적: 최소 주파수 40Hz 도달 확인
        
        Phase 7 (510-600초, 1.5분): 정상 복귀
            - T5: 30°C → 35°C
            - 예상 제어:
              * ML: "온도 상승 예측" → 선제적 주파수 증가
              * Rule R1: T5 정상 진입 → 보정 최소화
            - 목적: 전체 사이클 완료 (40Hz → 48Hz)
        """
        noise = np.random.normal(0, 0.2)
        
        # Phase 1 (0-90초): 정상 범위 유지
        if t <= 90:
            t5_temp = 35.0
        
        # Phase 2 (90-180초): 온도 급상승 → 매우 높음 (60Hz 도달 목표)
        elif t <= 180:
            t5_temp = 35.0 + ((t - 90) / 90.0) * 5.0  # 35 → 40°C
        
        # Phase 3 (180-270초): 극고온 유지
        elif t <= 270:
            t5_temp = 40.0
        
        # Phase 4 (270-360초): 온도 하강 → 정상 복귀
        elif t <= 360:
            t5_temp = 40.0 - ((t - 270) / 90.0) * 5.0  # 40 → 35°C
        
        # Phase 5 (360-420초): 정상 범위 유지
        elif t <= 420:
            t5_temp = 35.0
        
        # Phase 6 (420-510초): 온도 급하강 → 매우 낮음 (40Hz 도달 목표)
        elif t <= 510:
            t5_temp = 35.0 - ((t - 420) / 90.0) * 5.0  # 35 → 30°C
        
        # Phase 7 (510-600초): 정상 복귀
        elif t <= 600:
            t5_temp = 30.0 + ((t - 510) / 90.0) * 5.0  # 30 → 35°C
        
        # 시나리오 종료 후 (600초 초과): 정상 온도 유지
        else:
            t5_temp = 35.0
        
        return {
            'T1': 25.0 + noise,  # 해수 입구 (온대 해역 - Rule R5 영향 제거)
            'T2': 42.0 + noise,  # SW 출구 1 (정상)
            'T3': 43.0 + noise,  # SW 출구 2 (정상)
            'T4': 45.0 + noise,  # FW 입구 (정상)
            'T5': t5_temp + noise,  # FW 출구 (Rule R1 검증)
            'T6': 43.0 + noise,  # E/R 온도 (정상)
            'T7': 32.0 + noise   # 외기 (정상)
        }

    def _fw_pump_control_temperature(self, t: float) -> Dict[str, float]:
        """
        FW 펌프 제어 검증 시나리오 - T4 온도 기반 ML 예측 + Rule R2 3단계 제어
        
        === 🎯 핵심 가치: 극한 에너지 절감 + 선제적 온도 예측 제어 ===
        
        1️⃣ Phase 1: 에너지 절감 모드 (T4 < 48°C & 예측 < 48°C)
           - T4 < 46°C: 무조건 40Hz 운전 (최대 에너지 절감)
           - T4 < 47°C: 42Hz 운전 (안전 마진)
           - T4 < 48°C: 46Hz 운전 (대기)
           - **목적: 48°C 안전하면 최대한 주파수를 낮춰서 에너지 절감!**
        
        2️⃣ Phase 2: 선제 대응 모드 (현재 T4 < 48°C BUT 예측 T4 ≥ 48°C)
           - ML이 30초 후 48°C 초과 예측 → 지금 선제적으로 증속
           - 예측 초과 정도에 따라 50Hz, 52Hz, 56Hz로 증속
           - **목적: 온도 상승 억제 (온도가 오르기 전에 미리 대응)**
        
        3️⃣ Phase 3: 긴급 모드 (실제 T4 ≥ 48°C)
           - Safety Layer S2에서 강제 60Hz 긴급 냉각
           - **목적: 48°C 초과 시 즉각 최대 냉각**
        
        === 시나리오 타임라인 (10분, 600초) ===
        
        초기 상태: FW 펌프 48Hz, T4 = 43°C (정상 범위)
        
        Phase 1 (0-90초, 1.5분): 에너지 절감 모드 (43°C 유지)
            - T4: 43°C 유지 (48°C까지 5°C 여유)
            - 예상 제어: R2 Phase 1 → 40Hz 급속 감속 (극한 에너지 절감)
            - 목적: 48°C 안전하면 최대한 주파수 낮춤 확인
        
        Phase 2 (90-180초, 1.5분): 선제 대응 모드 (43°C → 48°C)
            - T4: 43°C → 48°C (급격한 온도 상승)
            - 예상 제어: 
              * ML: "48°C 초과 예측" → 선제적 증속 (R2 Phase 2)
              * 예측 초과 정도에 따라 50Hz → 52Hz → 56Hz
            - 목적: 온도가 오르기 전에 미리 증속하여 상승 억제
        
        Phase 3 (180-270초, 1.5분): 긴급 모드 (48°C 도달)
            - T4: 48°C 유지 (임계값 초과)
            - 예상 제어: Safety Layer S2 → 강제 60Hz (R2 Phase 3)
            - 목적: 48°C 초과 시 즉각 최대 냉각 확인
        
        Phase 4 (270-360초, 1.5분): 선제 대응 → 에너지 절감 전환
            - T4: 48°C → 43°C (온도 하강)
            - 예상 제어:
              * ML: "온도 하강 예측" → 선제적 감속
              * 48°C 미만 진입 → R2 Phase 2 → Phase 1 전환
            - 목적: 60Hz → 50Hz대 → 40Hz로 단계적 절감 전환
        
        Phase 5 (360-420초, 1분): 에너지 절감 모드 복귀
            - T4: 43°C 유지
            - 예상 제어: R2 Phase 1 → 40Hz 안정 유지
            - 목적: 에너지 절감 모드 안정성 확인
        
        Phase 6 (420-510초, 1.5분): 극한 에너지 절감 (43°C → 38°C)
            - T4: 43°C → 38°C (온도 추가 하강)
            - 예상 제어: R2 Phase 1 유지 → 40Hz 지속 (최소 주파수)
            - 목적: 저온에서도 40Hz 유지 (과도 감속 방지)
        
        Phase 7 (510-600초, 1.5분): 정상 복귀
            - T4: 38°C → 43°C (온도 상승)
            - 예상 제어: R2 Phase 1 유지 → 40Hz에서 점진적 증속
            - 목적: 전체 사이클 완료 (40Hz 안정 운전)
        """
        noise = np.random.normal(0, 0.2)
        
        # Phase 1 (0-90초): 정상 범위 유지
        if t <= 90:
            t4_temp = 43.0
        
        # Phase 2 (90-180초): 온도 급상승 → 매우 높음 (60Hz 도달 목표)
        elif t <= 180:
            t4_temp = 43.0 + ((t - 90) / 90.0) * 5.0  # 43 → 48°C
        
        # Phase 3 (180-270초): 극고온 유지
        elif t <= 270:
            t4_temp = 48.0
        
        # Phase 4 (270-360초): 온도 하강 → 정상 복귀
        elif t <= 360:
            t4_temp = 48.0 - ((t - 270) / 90.0) * 5.0  # 48 → 43°C
        
        # Phase 5 (360-420초): 정상 범위 유지
        elif t <= 420:
            t4_temp = 43.0
        
        # Phase 6 (420-510초): 온도 급하강 → 매우 낮음 (40Hz 도달 목표)
        elif t <= 510:
            t4_temp = 43.0 - ((t - 420) / 90.0) * 5.0  # 43 → 38°C
        
        # Phase 7 (510-600초): 정상 복귀
        elif t <= 600:
            t4_temp = 38.0 + ((t - 510) / 90.0) * 5.0  # 38 → 43°C
        
        # 시나리오 종료 후 (600초 초과): 정상 온도 유지
        else:
            t4_temp = 43.0
        
        return {
            'T1': 25.0 + noise,  # 해수 입구 (온대 해역 - Rule R5 영향 제거)
            'T2': 42.0 + noise,  # SW 출구 1 (정상)
            'T3': 43.0 + noise,  # SW 출구 2 (정상)
            'T4': t4_temp + noise,  # FW 입구 (Rule R2 검증)
            'T5': 35.0 + noise,  # FW 출구 (정상)
            'T6': 43.0 + noise,  # E/R 온도 (정상)
            'T7': 32.0 + noise   # 외기 (정상)
        }

    def _er_ventilation_temperature(self, t: float) -> Dict[str, float]:
        """
        E/R 온도 제어 검증 시나리오 - T6 온도 피드백 제어 + 전체 대수 변화 (V3 설정)
        
        === 🎯 V3 설정: 목표 43°C, 극한 47°C, 갭 4.0°C ===
        
        초기 상태: 3대 48Hz, T6 = 43°C (목표 온도)
        
        Phase 1 (0-60초, 1분): 정상 유지 (43°C)
            - T6: 43°C 유지
            - 예상: 48Hz, 3대 안정
        
        Phase 2 (60-150초, 1.5분): 온도 상승 → 60Hz (43→44.5°C)
            - T6: 43°C → 44.5°C (정상 고온)
            - 예상: 피드백 제어로 60Hz 도달, 3대
            - 목적: 정상 범위 60Hz 10초 대기 증설 확인 (Priority 4)
        
        Phase 3 (150-210초, 1분): 60Hz 유지 → 정상 대수 증설
            - T6: 44.5°C 유지 (정상 고온, Priority 4 조건)
            - 예상: 60Hz 10초 지속 → 3대 → 4대 증설 (Priority 4)
            - 주파수: 60Hz → 52Hz (부하 분산) → 쿨다운 30초
            - 목적: ⭐ 정상 10초 대기 대수 증설 확인 (45°C 미만!)
        
        Phase 4 (210-300초, 1.5분): 고온 진입 → Priority 3 테스트
            - T6: 44.5°C → 45.5°C (고온!)
            - 예상: Priority 3 발동! (45°C 이상 → 5초 대기 증설)
            - 만약 아직 3대면 → 5초 후 4대, 이미 4대면 유지
            - 목적: ⭐ 고온 5초 대기 증설 확인 (주파수 무관!)
        
        Phase 5 (300-390초, 1.5분): 극한 근접 → Priority 2 테스트
            - T6: 45.5°C → 46°C (극한 근접)
            - ML 예측: 47°C 예상!
            - 예상: Priority 2 발동! (극한 예상 → 즉시 증설)
            - 만약 아직 3대면 → 4대, 이미 4대면 유지
            - 목적: ⭐ ML 예측 기반 선제 대응 확인
        
        Phase 6 (390-480초, 1.5분): 온도 하강 (46→43°C)
            - T6: 46°C → 43°C (목표 복귀)
            - 예상: 피드백 제어 감속, 4대 유지
        
        Phase 7 (480-570초, 1.5분): 저온 진입 (43→38°C)
            - T6: 43°C → 38°C (저온!)
            - 예상: 40Hz 도달, 4대 유지
        
        Phase 8 (570-660초, 1.5분): 저온 유지 → 4대→3대 감소
            - T6: 38°C 유지 (저온 지속)
            - 예상: 40Hz 10초 지속 → 4대 → 3대 감소
            - 주파수: 40Hz → 48Hz
            - 목적: ⭐ 4대→3대 감소 확인 (38°C에서 확실한 40Hz)
        
        Phase 9 (660-720초, 1분): 정상 복귀 (38→41.5°C)
            - T6: 38°C → 41.5°C (약간 상승)
            - 예상: 48Hz 유지, 3대
        
        Phase 10 (720-810초, 1.5분): 극저온 재진입 (41.5→36°C)
            - T6: 41.5°C → 36°C (매우 낮음)
            - 예상: 40Hz 재도달, 3대
        
        Phase 11 (810-900초, 1.5분): 극저온 유지 → 3대→2대 감소
            - T6: 36°C 유지 (극저온 지속)
            - 예상: 40Hz 10초 지속 → 3대 → 2대 감소
            - 주파수: 40Hz → 48Hz
            - 목적: ⭐ 3대→2대 감소 확인 (36°C에서 확실한 40Hz)
        
        Phase 12 (900-990초, 1.5분): 최종 정상 복귀 (36→43°C)
            - T6: 36°C → 43°C (목표 복귀)
            - 예상: 피드백 제어, 2대 유지
        """
        noise = np.random.normal(0, 0.2)
        
        # Phase 1 (0-60초): 정상 유지
        if t <= 60:
            t6_temp = 43.0
        
        # Phase 2 (60-150초): 온도 상승 → 60Hz (정상 고온)
        elif t <= 150:
            t6_temp = 43.0 + ((t - 60) / 90.0) * 1.5  # 43 → 44.5°C (Priority 4 조건)
        
        # Phase 3 (150-210초): 60Hz 유지 (정상 대수 증설: 3→4대, Priority 4)
        elif t <= 210:
            t6_temp = 44.5  # 44.5°C 유지 → 60Hz 10초 → 4대 증설 (45°C 미만!)
        
        # Phase 4 (210-300초): 고온 진입 (Priority 3 테스트)
        elif t <= 300:
            t6_temp = 44.5 + ((t - 210) / 90.0) * 1.0  # 44.5 → 45.5°C (고온!)
        
        # Phase 5 (300-390초): 극한 근접 (Priority 2 테스트)
        elif t <= 390:
            t6_temp = 45.5 + ((t - 300) / 90.0) * 0.5  # 45.5 → 46°C
        
        # Phase 6 (390-480초): 온도 하강
        elif t <= 480:
            t6_temp = 46.0 - ((t - 390) / 90.0) * 3.0  # 46 → 43°C
        
        # Phase 7 (480-570초): 저온 진입
        elif t <= 570:
            t6_temp = 43.0 - ((t - 480) / 90.0) * 5.0  # 43 → 38°C
        
        # Phase 8 (570-660초): 저온 유지 (대수 감소: 4→3대)
        elif t <= 660:
            t6_temp = 38.0  # 38°C 유지 → 40Hz 10초 → 3대 감소
        
        # Phase 9 (660-720초): 정상 복귀
        elif t <= 720:
            t6_temp = 38.0 + ((t - 660) / 60.0) * 3.5  # 38 → 41.5°C
        
        # Phase 10 (720-810초): 극저온 재진입
        elif t <= 810:
            t6_temp = 41.5 - ((t - 720) / 90.0) * 5.5  # 41.5 → 36°C
        
        # Phase 11 (810-900초): 극저온 유지 (대수 감소: 3→2대)
        elif t <= 900:
            t6_temp = 36.0  # 36°C 유지 → 40Hz 10초 → 2대 감소
        
        # Phase 12 (900-990초): 최종 정상 복귀
        elif t <= 990:
            t6_temp = 36.0 + ((t - 900) / 90.0) * 7.0  # 36 → 43°C
        
        # 시나리오 종료 후 (990초 초과): 목표 온도 유지
        else:
            t6_temp = 43.0  # 목표 온도 유지
        
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
