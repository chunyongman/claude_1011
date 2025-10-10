"""
통합 테스트 프레임워크
운영/시뮬레이션 공통 테스트
"""

import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.adapter.base_adapter import SensorAdapter, EquipmentAdapter, SensorData, ControlCommand
from src.simulation.physics_engine import PhysicsEngine, VoyagePattern
from src.adapter.sim_adapter import SimSensorAdapter, SimEquipmentAdapter


class TestScenario(Enum):
    """테스트 시나리오"""
    NORMAL_OPERATION = "정상운전"
    HIGH_LOAD = "고부하"
    COOLING_FAILURE = "냉각실패"
    PRESSURE_DROP = "압력저하"


class TestResult(Enum):
    """테스트 결과"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass
class PerformanceMetrics:
    """성능 지표"""
    # 온도 제어
    t5_target_achieved: float = 0.0  # T5 목표 달성률 (%)
    t6_target_achieved: float = 0.0  # T6 목표 달성률 (%)
    t5_avg_error: float = 0.0  # T5 평균 오차 (°C)
    t6_avg_error: float = 0.0  # T6 평균 오차 (°C)

    # 에너지 절감
    avg_energy_savings: float = 0.0  # 평균 에너지 절감률 (%)
    sw_pump_savings: float = 0.0  # SW 펌프 절감률
    fw_pump_savings: float = 0.0  # FW 펌프 절감률
    er_fan_savings: float = 0.0  # E/R 팬 절감률

    # 안전성
    safety_compliance: float = 100.0  # 안전 제약조건 준수율 (%)
    emergency_count: int = 0  # 긴급 상황 발생 횟수

    # 성능
    ai_response_time_avg: float = 0.0  # AI 응답시간 평균 (s)
    ai_response_time_max: float = 0.0  # AI 응답시간 최대 (s)

    # 장비 동기화
    sw_fw_sync_rate: float = 100.0  # SW/FW 펌프 동기화율 (%)


@dataclass
class TestCase:
    """테스트 케이스"""
    name: str
    scenario: TestScenario
    duration: int  # 테스트 시간 (초)
    success_criteria: Dict[str, Tuple[float, float]]  # {지표명: (최소값, 최대값)}
    result: TestResult = TestResult.PASS
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    failure_reason: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TestFramework:
    """통합 테스트 프레임워크"""

    def __init__(
        self,
        sensor_adapter: SensorAdapter,
        equipment_adapter: EquipmentAdapter,
        use_simulation: bool = True
    ):
        """
        초기화

        Args:
            sensor_adapter: 센서 어댑터
            equipment_adapter: 장비 어댑터
            use_simulation: 시뮬레이션 모드 사용 여부
        """
        self.sensor_adapter = sensor_adapter
        self.equipment_adapter = equipment_adapter
        self.use_simulation = use_simulation

        # 테스트 케이스 목록
        self.test_cases: List[TestCase] = []

        # 데이터 기록
        self.sensor_history: List[SensorData] = []
        self.command_history: List[ControlCommand] = []
        self.ai_response_times: List[float] = []

    def add_test_case(self, test_case: TestCase):
        """테스트 케이스 추가"""
        self.test_cases.append(test_case)

    def run_test_case(self, test_case: TestCase) -> TestResult:
        """
        테스트 케이스 실행

        Args:
            test_case: 테스트 케이스

        Returns:
            테스트 결과
        """
        print(f"\n{'='*80}")
        print(f"테스트 시작: {test_case.name}")
        print(f"시나리오: {test_case.scenario.value}")
        print(f"시간: {test_case.duration}초")
        print(f"{'='*80}")

        test_case.start_time = datetime.now()

        # 데이터 초기화
        self.sensor_history.clear()
        self.command_history.clear()
        self.ai_response_times.clear()

        # 시뮬레이션 리셋
        if self.use_simulation and isinstance(self.equipment_adapter, SimEquipmentAdapter):
            self.equipment_adapter.reset()

        # 시나리오별 설정
        self._configure_scenario(test_case.scenario)

        # 테스트 루프
        for t in range(test_case.duration):
            # AI 추론 시작 시간
            ai_start = time.time()

            # 센서 읽기
            sensors = self.sensor_adapter.read_sensors()
            self.sensor_history.append(sensors)

            # 제어 로직 (간단한 PID 제어 - 실제로는 통합 제어기 사용)
            command = self._simple_control_logic(sensors)
            self.command_history.append(command)

            # 제어 명령 전송
            self.equipment_adapter.send_command(command)

            # AI 추론 시간 기록
            ai_elapsed = time.time() - ai_start
            self.ai_response_times.append(ai_elapsed)

            # 진행률 표시 (10% 단위)
            if (t + 1) % (test_case.duration // 10) == 0:
                progress = (t + 1) / test_case.duration * 100
                print(f"  진행: {progress:.0f}% ({t+1}/{test_case.duration}초)")

        test_case.end_time = datetime.now()

        # 성능 지표 계산
        test_case.metrics = self._calculate_metrics()

        # 성공 기준 검증
        test_case.result, test_case.failure_reason = self._verify_success_criteria(
            test_case.metrics,
            test_case.success_criteria
        )

        # 결과 출력
        self._print_test_result(test_case)

        return test_case.result

    def _configure_scenario(self, scenario: TestScenario):
        """
        시나리오별 환경 설정

        Args:
            scenario: 테스트 시나리오
        """
        if not self.use_simulation:
            return

        if not isinstance(self.equipment_adapter, SimEquipmentAdapter):
            return

        physics_engine = self.equipment_adapter.physics_engine

        if scenario == TestScenario.NORMAL_OPERATION:
            # 정상 운전 (기본값)
            physics_engine.T1 = 25.0
            physics_engine.T6 = 43.0

        elif scenario == TestScenario.HIGH_LOAD:
            # 고부하: 외기온도 40°C
            physics_engine.T7 = 40.0
            physics_engine.T6 = 45.0

        elif scenario == TestScenario.COOLING_FAILURE:
            # 냉각 실패: T2/T3 초기값 높게 설정
            physics_engine.T2 = 46.0
            physics_engine.T3 = 46.0

        elif scenario == TestScenario.PRESSURE_DROP:
            # 압력 저하: PX1 초기값 낮게 설정
            physics_engine.PX1 = 1.2

    def _simple_control_logic(self, sensors: SensorData) -> ControlCommand:
        """
        간단한 제어 로직 (테스트용)

        실제로는 IntegratedController 사용

        Args:
            sensors: 센서 데이터

        Returns:
            제어 명령
        """
        # 기본 설정
        sw_pump_count = 2
        fw_pump_count = 2
        er_fan_count = 3

        # T5 기반 FW 펌프 주파수 (간단한 P 제어)
        t5_error = sensors.T5 - 35.0
        fw_freq = 48.0 + t5_error * 2.0  # Kp = 2.0
        fw_freq = max(40.0, min(60.0, fw_freq))

        # SW 펌프는 FW와 동기화
        sw_freq = fw_freq

        # T6 기반 E/R 팬 주파수
        t6_error = sensors.T6 - 43.0
        er_freq = 47.0 + t6_error * 1.5  # Kp = 1.5
        er_freq = max(40.0, min(60.0, er_freq))

        # 엔진 부하 기반 대수 제어
        if sensors.engine_load < 30:
            sw_pump_count = 1
            fw_pump_count = 1

        # 긴급 상황 대응
        if sensors.T2 >= 49.0 or sensors.T3 >= 49.0:
            # Cooler 과열
            sw_freq = 60.0
            fw_freq = 60.0
            sw_pump_count = 3
            fw_pump_count = 3

        if sensors.PX1 < 1.0:
            # 압력 부족
            sw_freq = min(sw_freq + 5.0, 60.0)

        if sensors.T6 > 50.0:
            # E/R 과열
            er_freq = 60.0
            er_fan_count = 4

        return ControlCommand(
            sw_pump_count=sw_pump_count,
            sw_pump_freq=sw_freq,
            fw_pump_count=fw_pump_count,
            fw_pump_freq=fw_freq,
            er_fan_count=er_fan_count,
            er_fan_freq=er_freq
        )

    def _calculate_metrics(self) -> PerformanceMetrics:
        """성능 지표 계산"""
        metrics = PerformanceMetrics()

        if not self.sensor_history:
            return metrics

        # T5 목표 달성률 (35 ± 0.5°C)
        t5_in_range = sum(1 for s in self.sensor_history if 34.5 <= s.T5 <= 35.5)
        metrics.t5_target_achieved = (t5_in_range / len(self.sensor_history)) * 100

        # T6 목표 달성률 (43 ± 1.0°C)
        t6_in_range = sum(1 for s in self.sensor_history if 42.0 <= s.T6 <= 44.0)
        metrics.t6_target_achieved = (t6_in_range / len(self.sensor_history)) * 100

        # 평균 오차
        metrics.t5_avg_error = sum(abs(s.T5 - 35.0) for s in self.sensor_history) / len(self.sensor_history)
        metrics.t6_avg_error = sum(abs(s.T6 - 43.0) for s in self.sensor_history) / len(self.sensor_history)

        # 에너지 절감률 (Affinity Laws)
        if self.command_history:
            sw_freqs = [c.sw_pump_freq for c in self.command_history]
            fw_freqs = [c.fw_pump_freq for c in self.command_history]
            er_freqs = [c.er_fan_freq for c in self.command_history]

            avg_sw_freq = sum(sw_freqs) / len(sw_freqs)
            avg_fw_freq = sum(fw_freqs) / len(fw_freqs)
            avg_er_freq = sum(er_freqs) / len(er_freqs)

            metrics.sw_pump_savings = (1 - (avg_sw_freq / 60.0) ** 3) * 100
            metrics.fw_pump_savings = (1 - (avg_fw_freq / 60.0) ** 3) * 100
            metrics.er_fan_savings = (1 - (avg_er_freq / 60.0) ** 3) * 100

            metrics.avg_energy_savings = (
                metrics.sw_pump_savings + metrics.fw_pump_savings + metrics.er_fan_savings
            ) / 3.0

        # 안전 제약조건 준수율
        safety_violations = sum(
            1 for s in self.sensor_history
            if s.T2 >= 49.0 or s.T3 >= 49.0 or s.T4 >= 48.0 or s.PX1 < 1.0 or s.T6 > 50.0
        )
        metrics.safety_compliance = (1 - safety_violations / len(self.sensor_history)) * 100 if self.sensor_history else 100.0
        metrics.emergency_count = safety_violations

        # AI 응답시간
        if self.ai_response_times:
            metrics.ai_response_time_avg = sum(self.ai_response_times) / len(self.ai_response_times)
            metrics.ai_response_time_max = max(self.ai_response_times)

        # SW/FW 동기화율
        if self.command_history:
            sync_count = sum(
                1 for c in self.command_history
                if c.sw_pump_count == c.fw_pump_count and abs(c.sw_pump_freq - c.fw_pump_freq) < 1.0
            )
            metrics.sw_fw_sync_rate = (sync_count / len(self.command_history)) * 100

        return metrics

    def _verify_success_criteria(
        self,
        metrics: PerformanceMetrics,
        criteria: Dict[str, Tuple[float, float]]
    ) -> Tuple[TestResult, str]:
        """
        성공 기준 검증

        Args:
            metrics: 성능 지표
            criteria: 성공 기준 {지표명: (최소값, 최대값)}

        Returns:
            (테스트 결과, 실패 이유)
        """
        failures = []

        for metric_name, (min_val, max_val) in criteria.items():
            metric_value = getattr(metrics, metric_name, None)

            if metric_value is None:
                failures.append(f"{metric_name}: 지표 없음")
                continue

            if not (min_val <= metric_value <= max_val):
                failures.append(
                    f"{metric_name}: {metric_value:.2f} (기준: {min_val:.2f}-{max_val:.2f})"
                )

        if failures:
            return TestResult.FAIL, "; ".join(failures)

        return TestResult.PASS, ""

    def _print_test_result(self, test_case: TestCase):
        """테스트 결과 출력"""
        print(f"\n{'='*80}")
        print(f"테스트 완료: {test_case.name}")
        print(f"{'='*80}")

        # 결과
        result_symbol = "[PASS]" if test_case.result == TestResult.PASS else "[FAIL]"
        print(f"\n{result_symbol} 결과: {test_case.result.value}")

        if test_case.failure_reason:
            print(f"  실패 이유: {test_case.failure_reason}")

        # 성능 지표
        m = test_case.metrics
        print(f"\n[성능 지표]")
        print(f"  온도 제어:")
        print(f"    T5 목표 달성률: {m.t5_target_achieved:.1f}%")
        print(f"    T6 목표 달성률: {m.t6_target_achieved:.1f}%")
        print(f"    T5 평균 오차: {m.t5_avg_error:.2f}°C")
        print(f"    T6 평균 오차: {m.t6_avg_error:.2f}°C")

        print(f"\n  에너지 절감:")
        print(f"    평균 절감률: {m.avg_energy_savings:.1f}%")
        print(f"    SW 펌프: {m.sw_pump_savings:.1f}%")
        print(f"    FW 펌프: {m.fw_pump_savings:.1f}%")
        print(f"    E/R 팬: {m.er_fan_savings:.1f}%")

        print(f"\n  안전성:")
        print(f"    안전 준수율: {m.safety_compliance:.1f}%")
        print(f"    긴급 상황: {m.emergency_count}회")

        print(f"\n  성능:")
        print(f"    AI 응답시간 평균: {m.ai_response_time_avg*1000:.1f}ms")
        print(f"    AI 응답시간 최대: {m.ai_response_time_max*1000:.1f}ms")

        print(f"\n  동기화:")
        print(f"    SW/FW 펌프 동기화율: {m.sw_fw_sync_rate:.1f}%")

        # 시간
        if test_case.start_time and test_case.end_time:
            duration = (test_case.end_time - test_case.start_time).total_seconds()
            print(f"\n[소요 시간] {duration:.1f}초")

    def run_all_tests(self) -> Dict[str, int]:
        """
        모든 테스트 케이스 실행

        Returns:
            결과 요약 {"PASS": 개수, "FAIL": 개수, "WARN": 개수}
        """
        print(f"\n{'='*80}")
        print(f"통합 테스트 프레임워크 - 전체 테스트 시작")
        print(f"테스트 케이스: {len(self.test_cases)}개")
        print(f"모드: {'시뮬레이션' if self.use_simulation else '운영'}")
        print(f"{'='*80}")

        results = {"PASS": 0, "FAIL": 0, "WARN": 0}

        for i, test_case in enumerate(self.test_cases, 1):
            print(f"\n[{i}/{len(self.test_cases)}] 테스트 케이스 실행...")
            result = self.run_test_case(test_case)
            results[result.value] += 1

        # 전체 결과 요약
        self._print_summary(results)

        return results

    def _print_summary(self, results: Dict[str, int]):
        """전체 결과 요약 출력"""
        print(f"\n{'='*80}")
        print(f"전체 테스트 결과 요약")
        print(f"{'='*80}")

        total = sum(results.values())
        pass_count = results["PASS"]
        fail_count = results["FAIL"]
        warn_count = results["WARN"]

        print(f"\n총 테스트: {total}개")
        print(f"  [PASS] {pass_count}개 ({pass_count/total*100:.1f}%)")
        print(f"  [FAIL] {fail_count}개 ({fail_count/total*100:.1f}%)")
        print(f"  [WARN] {warn_count}개 ({warn_count/total*100:.1f}%)")

        if fail_count == 0:
            print(f"\n모든 테스트 통과!")
        else:
            print(f"\n{fail_count}개 테스트 실패")

        # 테스트 케이스별 결과
        print(f"\n테스트 케이스별 결과:")
        for i, test_case in enumerate(self.test_cases, 1):
            symbol = "[O]" if test_case.result == TestResult.PASS else "[X]"
            print(f"  {i}. {symbol} {test_case.name} ({test_case.scenario.value})")
            if test_case.failure_reason:
                print(f"      -> {test_case.failure_reason}")
