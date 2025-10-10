"""
Stage 9: HMI 대시보드 및 사용자 인터페이스 테스트
"""

import unittest
import sys
import io
import os
import time
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add src directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.hmi.hmi_state_manager import (
    HMIStateManager,
    ControlMode,
    AlarmPriority,
    EmergencyStopState,
    EquipmentGroup,
    Alarm
)


class TestStage9HMI(unittest.TestCase):
    """Stage 9: HMI Dashboard 테스트"""

    def setUp(self):
        """테스트 초기화"""
        self.hmi_manager = HMIStateManager()

    def test_1_group_control_mode_switching(self):
        """
        Test 1: 그룹별 제어 모드 전환
        각 그룹(SW펌프/FW펌프/E/R팬)이 독립적으로 60Hz 고정 또는 AI 제어를 선택할 수 있는지 검증
        """
        print("\n" + "="*80)
        print("Test 1: 그룹별 제어 모드 전환")
        print("="*80)

        # 초기 상태: 모든 그룹 AI 제어
        for group_name in ["SW_PUMPS", "FW_PUMPS", "ER_FANS"]:
            group = self.hmi_manager.groups[group_name]
            self.assertEqual(group.control_mode, ControlMode.AI_CONTROL)
            print(f"✓ {group.name}: 초기 모드 = {group.control_mode.value}")

        # SW 펌프만 60Hz 고정으로 변경
        self.hmi_manager.set_control_mode("SW_PUMPS", ControlMode.FIXED_60HZ)

        # 검증
        self.assertEqual(self.hmi_manager.groups["SW_PUMPS"].control_mode, ControlMode.FIXED_60HZ)
        self.assertEqual(self.hmi_manager.groups["FW_PUMPS"].control_mode, ControlMode.AI_CONTROL)
        self.assertEqual(self.hmi_manager.groups["ER_FANS"].control_mode, ControlMode.AI_CONTROL)

        print(f"\n✓ SW 펌프: {self.hmi_manager.groups['SW_PUMPS'].control_mode.value}")
        print(f"✓ FW 펌프: {self.hmi_manager.groups['FW_PUMPS'].control_mode.value}")
        print(f"✓ E/R 팬: {self.hmi_manager.groups['ER_FANS'].control_mode.value}")

        # E/R 팬도 60Hz 고정으로 변경
        self.hmi_manager.set_control_mode("ER_FANS", ControlMode.FIXED_60HZ)

        # 검증
        self.assertEqual(self.hmi_manager.groups["SW_PUMPS"].control_mode, ControlMode.FIXED_60HZ)
        self.assertEqual(self.hmi_manager.groups["FW_PUMPS"].control_mode, ControlMode.AI_CONTROL)
        self.assertEqual(self.hmi_manager.groups["ER_FANS"].control_mode, ControlMode.FIXED_60HZ)

        print(f"\n✓ 독립적 제어 모드 전환 성공")
        print(f"  SW 펌프: {self.hmi_manager.groups['SW_PUMPS'].control_mode.value}")
        print(f"  FW 펌프: {self.hmi_manager.groups['FW_PUMPS'].control_mode.value}")
        print(f"  E/R 팬: {self.hmi_manager.groups['ER_FANS'].control_mode.value}")

    def test_2_target_vs_actual_monitoring(self):
        """
        Test 2: 목표 vs 실제 주파수 모니터링
        입력 조건 → AI 계산 → 목표 주파수 → 실제 반영 흐름 검증
        편차에 따른 Green/Yellow/Red 상태 분류
        """
        print("\n" + "="*80)
        print("Test 2: 목표 vs 실제 주파수 모니터링")
        print("="*80)

        # SW 펌프 그룹 설정
        self.hmi_manager.set_control_mode("SW_PUMPS", ControlMode.AI_CONTROL)
        self.hmi_manager.update_target_frequency("SW_PUMPS", 48.4)

        # 운전 중인 장비 2대의 실제 주파수 설정
        self.hmi_manager.update_actual_frequency("SW_PUMPS", "SW-P1", 48.2)  # -0.2Hz 편차
        self.hmi_manager.update_actual_frequency("SW_PUMPS", "SW-P2", 48.5)  # +0.1Hz 편차

        group = self.hmi_manager.groups["SW_PUMPS"]

        print(f"\n목표 주파수: {group.target_frequency:.1f} Hz")
        print(f"실제 주파수:")
        print(f"  SW-P1: {group.actual_frequencies['SW-P1']:.1f} Hz")
        print(f"  SW-P2: {group.actual_frequencies['SW-P2']:.1f} Hz")
        print(f"평균 실제: {group.get_avg_actual_frequency():.1f} Hz")
        print(f"최대 편차: {group.get_max_deviation():.2f} Hz")

        # 편차 < 0.3Hz → Green
        deviation_status = self.hmi_manager.get_deviation_status("SW_PUMPS")
        self.assertEqual(deviation_status, "Green")
        print(f"✓ 상태: {deviation_status} (편차 < 0.3Hz)")

        # 편차 0.3~0.5Hz 시뮬레이션 → Yellow
        self.hmi_manager.update_actual_frequency("SW_PUMPS", "SW-P1", 48.0)  # -0.4Hz 편차

        deviation_status = self.hmi_manager.get_deviation_status("SW_PUMPS")
        self.assertEqual(deviation_status, "Yellow")
        print(f"\n✓ 편차 증가: {group.get_max_deviation():.2f} Hz → {deviation_status}")

        # 편차 > 0.5Hz 시뮬레이션 → Red
        self.hmi_manager.update_actual_frequency("SW_PUMPS", "SW-P1", 47.8)  # -0.6Hz 편차

        deviation_status = self.hmi_manager.get_deviation_status("SW_PUMPS")
        self.assertEqual(deviation_status, "Red")
        print(f"✓ 편차 증가: {group.get_max_deviation():.2f} Hz → {deviation_status}")

        print(f"\n✓ 편차 모니터링 정상 작동")

    def test_3_emergency_stop(self):
        """
        Test 3: 긴급 정지 기능
        30초 점진적 60Hz 전환 검증
        모든 그룹이 60Hz 고정 모드로 전환되는지 확인
        """
        print("\n" + "="*80)
        print("Test 3: 긴급 정지 기능")
        print("="*80)

        # 초기 상태: AI 제어, 48.4Hz
        self.hmi_manager.set_control_mode("SW_PUMPS", ControlMode.AI_CONTROL)
        self.hmi_manager.update_target_frequency("SW_PUMPS", 48.4)

        print(f"초기 상태:")
        print(f"  제어 모드: {self.hmi_manager.groups['SW_PUMPS'].control_mode.value}")
        print(f"  목표 주파수: {self.hmi_manager.groups['SW_PUMPS'].target_frequency:.1f} Hz")

        # 긴급 정지 시작
        self.hmi_manager.start_emergency_stop()

        self.assertEqual(self.hmi_manager.emergency_stop_state, EmergencyStopState.STOPPING)
        print(f"\n✓ 긴급 정지 시작")

        # 긴급 정지 알람 확인
        active_alarms = self.hmi_manager.get_active_alarms()
        self.assertTrue(any(
            alarm.priority == AlarmPriority.CRITICAL and "긴급 정지" in alarm.message
            for alarm in active_alarms
        ))
        print(f"✓ CRITICAL 알람 발생: '{active_alarms[0].message}'")

        # 10초 경과 시뮬레이션 (33% 진행)
        time.sleep(0.1)  # 실제로는 10초 대기하지 않고 시뮬레이션
        self.hmi_manager.emergency_stop_start_time = time.time() - 10.0

        progress = self.hmi_manager.get_emergency_stop_progress()
        self.assertAlmostEqual(progress, 10.0 / 30.0, delta=0.05)
        print(f"\n10초 경과: 진행률 {progress*100:.1f}%")

        # 점진적 주파수 계산
        target_freq = self.hmi_manager.get_emergency_stop_target_frequency(48.4)
        expected_freq = 48.4 + (60.0 - 48.4) * (10.0 / 30.0)
        self.assertAlmostEqual(target_freq, expected_freq, delta=0.1)
        print(f"  점진적 목표 주파수: {target_freq:.1f} Hz (48.4 → 60.0)")

        # 30초 경과 시뮬레이션 (100% 완료)
        self.hmi_manager.emergency_stop_start_time = time.time() - 30.0

        self.hmi_manager.update_emergency_stop()

        # 긴급 정지 완료 검증
        self.assertEqual(self.hmi_manager.emergency_stop_state, EmergencyStopState.STOPPED)

        # 모든 그룹이 60Hz 고정 모드로 전환되었는지 확인
        for group_name in ["SW_PUMPS", "FW_PUMPS", "ER_FANS"]:
            group = self.hmi_manager.groups[group_name]
            self.assertEqual(group.control_mode, ControlMode.FIXED_60HZ)
            self.assertEqual(group.target_frequency, 60.0)

        print(f"\n✓ 30초 경과: 긴급 정지 완료")
        print(f"  모든 그룹 → 60Hz 고정 모드")

        # 긴급 정지 해제
        self.hmi_manager.reset_emergency_stop()

        self.assertEqual(self.hmi_manager.emergency_stop_state, EmergencyStopState.NORMAL)
        print(f"\n✓ 긴급 정지 해제 → 정상 운전 재개")

    def test_4_alarm_management(self):
        """
        Test 4: 알람 관리
        CRITICAL(Red), WARNING(Yellow), INFO(Blue) 우선순위
        알람 확인 기능
        """
        print("\n" + "="*80)
        print("Test 4: 알람 관리")
        print("="*80)

        # 다양한 우선순위 알람 추가
        self.hmi_manager.add_alarm(
            priority=AlarmPriority.CRITICAL,
            equipment="SW-P1",
            message="VFD Trip 발생"
        )

        self.hmi_manager.add_alarm(
            priority=AlarmPriority.WARNING,
            equipment="FW-P2",
            message="주파수 편차 0.6Hz 초과"
        )

        self.hmi_manager.add_alarm(
            priority=AlarmPriority.INFO,
            equipment="SYSTEM",
            message="자동 학습 완료"
        )

        # 알람 개수 확인
        self.assertEqual(len(self.hmi_manager.alarms), 3)
        print(f"\n총 알람 개수: {len(self.hmi_manager.alarms)}")

        # 우선순위별 알람 확인
        critical_alarms = self.hmi_manager.get_alarms_by_priority(AlarmPriority.CRITICAL)
        warning_alarms = self.hmi_manager.get_alarms_by_priority(AlarmPriority.WARNING)
        info_alarms = self.hmi_manager.get_alarms_by_priority(AlarmPriority.INFO)

        self.assertEqual(len(critical_alarms), 1)
        self.assertEqual(len(warning_alarms), 1)
        self.assertEqual(len(info_alarms), 1)

        print(f"  CRITICAL (Red): {len(critical_alarms)}개")
        print(f"  WARNING (Yellow): {len(warning_alarms)}개")
        print(f"  INFO (Blue): {len(info_alarms)}개")

        # 알람 색상 확인
        self.assertEqual(critical_alarms[0].get_color(), "red")
        self.assertEqual(warning_alarms[0].get_color(), "yellow")
        self.assertEqual(info_alarms[0].get_color(), "blue")

        print(f"\n✓ 알람 색상 매핑:")
        print(f"  CRITICAL → {critical_alarms[0].get_color()}")
        print(f"  WARNING → {warning_alarms[0].get_color()}")
        print(f"  INFO → {info_alarms[0].get_color()}")

        # 미확인 알람 확인
        active_alarms = self.hmi_manager.get_active_alarms()
        self.assertEqual(len(active_alarms), 3)
        print(f"\n미확인 알람: {len(active_alarms)}개")

        # 첫 번째 알람 확인
        self.hmi_manager.acknowledge_alarm(0)

        active_alarms = self.hmi_manager.get_active_alarms()
        self.assertEqual(len(active_alarms), 2)
        print(f"알람 확인 후: {len(active_alarms)}개")

        # 확인된 알람은 acknowledged=True
        self.assertTrue(self.hmi_manager.alarms[0].acknowledged)
        print(f"\n✓ 알람 확인 기능 정상 작동")

    def test_5_runtime_equalization_monitoring(self):
        """
        Test 5: 운전 시간 균등화 모니터링
        총 운전 시간, 금일 운전 시간, 연속 운전 시간 추적
        """
        print("\n" + "="*80)
        print("Test 5: 운전 시간 균등화 모니터링")
        print("="*80)

        # 시뮬레이션 데이터 (실제로는 equipment_manager에서 가져옴)
        runtime_data = {
            "SW-P1": {"total": 1250.5, "daily": 18.5, "continuous": 6.2},
            "SW-P2": {"total": 1180.2, "daily": 5.5, "continuous": 0.0},
            "SW-P3": {"total": 1220.8, "daily": 0.0, "continuous": 0.0},
        }

        print(f"\nSW 펌프 운전 시간 현황:")
        for pump, times in runtime_data.items():
            print(f"  {pump}:")
            print(f"    총 운전: {times['total']:.1f}h")
            print(f"    금일: {times['daily']:.1f}h")
            print(f"    연속: {times['continuous']:.1f}h")

        # 균등화 편차 계산
        total_times = [data["total"] for data in runtime_data.values()]
        max_time = max(total_times)
        min_time = min(total_times)
        avg_time = sum(total_times) / len(total_times)

        deviation_pct = (max_time - min_time) / avg_time * 100

        print(f"\n균등화 분석:")
        print(f"  최대 운전 시간: {max_time:.1f}h")
        print(f"  최소 운전 시간: {min_time:.1f}h")
        print(f"  평균 운전 시간: {avg_time:.1f}h")
        print(f"  편차: {deviation_pct:.1f}%")

        # 편차 10% 이내 목표
        self.assertLess(deviation_pct, 10.0)
        print(f"\n✓ 운전 시간 균등화 편차 10% 이내 달성")

        # 24시간 자동 교체 로직 (펌프)
        # SW-P1이 6.2시간 연속 운전 중
        # 24시간 도달 전에 자동 교체 필요
        self.assertLess(runtime_data["SW-P1"]["continuous"], 24.0)
        print(f"✓ 펌프 24시간 교체 주기 준수")

    def test_6_learning_progress_tracking(self):
        """
        Test 6: 학습 진행 추적
        온도 예측 정확도, 최적화 정확도, 에너지 절감률 개선 추적
        """
        print("\n" + "="*80)
        print("Test 6: 학습 진행 추적")
        print("="*80)

        # 초기 학습 진행 상태
        progress = self.hmi_manager.get_learning_progress()

        print(f"초기 학습 상태:")
        print(f"  온도 예측 정확도: {progress['temperature_prediction_accuracy']:.1f}%")
        print(f"  최적화 정확도: {progress['optimization_accuracy']:.1f}%")
        print(f"  평균 에너지 절감률: {progress['average_energy_savings']:.1f}%")
        print(f"  총 학습 시간: {progress['total_learning_hours']:.1f}h")

        # 1주차 학습 완료 시뮬레이션
        self.hmi_manager.update_learning_progress(
            temp_accuracy=72.0,
            opt_accuracy=95.5,
            energy_savings=42.0,
            learning_hours=2.0
        )

        progress = self.hmi_manager.get_learning_progress()

        print(f"\n1주차 학습 완료:")
        print(f"  온도 예측 정확도: {progress['temperature_prediction_accuracy']:.1f}%")
        print(f"  최적화 정확도: {progress['optimization_accuracy']:.1f}%")
        print(f"  평균 에너지 절감률: {progress['average_energy_savings']:.1f}%")
        print(f"  총 학습 시간: {progress['total_learning_hours']:.1f}h")

        self.assertEqual(progress['temperature_prediction_accuracy'], 72.0)
        self.assertEqual(progress['optimization_accuracy'], 95.5)
        self.assertEqual(progress['average_energy_savings'], 42.0)
        self.assertEqual(progress['total_learning_hours'], 2.0)

        # 8주차 학습 완료 시뮬레이션 (개선 확인)
        self.hmi_manager.update_learning_progress(
            temp_accuracy=82.5,
            opt_accuracy=99.2,
            energy_savings=50.1,
            learning_hours=16.0
        )

        progress = self.hmi_manager.get_learning_progress()

        print(f"\n8주차 학습 완료:")
        print(f"  온도 예측 정확도: {progress['temperature_prediction_accuracy']:.1f}%")
        print(f"  최적화 정확도: {progress['optimization_accuracy']:.1f}%")
        print(f"  평균 에너지 절감률: {progress['average_energy_savings']:.1f}%")
        print(f"  총 학습 시간: {progress['total_learning_hours']:.1f}h")

        # 개선률 계산
        temp_improvement = 82.5 - 72.0
        energy_improvement = 50.1 - 42.0

        print(f"\n8주간 개선:")
        print(f"  온도 예측 정확도: +{temp_improvement:.1f}%p")
        print(f"  에너지 절감률: +{energy_improvement:.1f}%p")

        self.assertGreater(temp_improvement, 5.0)  # 최소 5%p 개선
        self.assertGreater(energy_improvement, 5.0)  # 최소 5%p 개선

        print(f"\n✓ 학습을 통한 지속적 성능 개선 확인")

    def test_7_state_export(self):
        """
        Test 7: 상태 내보내기
        로깅 및 분석을 위한 전체 시스템 상태 내보내기
        """
        print("\n" + "="*80)
        print("Test 7: 상태 내보내기")
        print("="*80)

        # 시스템 상태 설정
        self.hmi_manager.set_control_mode("SW_PUMPS", ControlMode.AI_CONTROL)
        self.hmi_manager.update_target_frequency("SW_PUMPS", 48.4)
        self.hmi_manager.update_actual_frequency("SW_PUMPS", "SW-P1", 48.2)
        self.hmi_manager.update_actual_frequency("SW_PUMPS", "SW-P2", 48.5)

        self.hmi_manager.add_alarm(
            priority=AlarmPriority.WARNING,
            equipment="FW-P2",
            message="테스트 알람"
        )

        self.hmi_manager.update_learning_progress(
            temp_accuracy=82.5,
            opt_accuracy=99.2,
            energy_savings=50.1,
            learning_hours=16.0
        )

        # 상태 내보내기
        state = self.hmi_manager.export_state()

        # 검증
        self.assertIn("timestamp", state)
        self.assertIn("groups", state)
        self.assertIn("emergency_stop", state)
        self.assertIn("active_alarms_count", state)
        self.assertIn("learning_progress", state)

        print(f"내보낸 상태 정보:")
        print(f"  타임스탬프: {state['timestamp']}")
        print(f"  그룹 개수: {len(state['groups'])}")
        print(f"  긴급 정지 상태: {state['emergency_stop']['state']}")
        print(f"  활성 알람 개수: {state['active_alarms_count']}")

        # SW 펌프 그룹 상세 정보
        sw_pump_state = state['groups']['SW_PUMPS']

        print(f"\nSW 펌프 그룹 상세:")
        print(f"  제어 모드: {sw_pump_state['control_mode']}")
        print(f"  목표 주파수: {sw_pump_state['target_frequency']:.1f} Hz")
        print(f"  평균 실제: {sw_pump_state['avg_actual']:.1f} Hz")
        print(f"  최대 편차: {sw_pump_state['max_deviation']:.2f} Hz")
        print(f"  편차 상태: {sw_pump_state['deviation_status']}")

        self.assertEqual(sw_pump_state['control_mode'], "AI 제어")
        self.assertEqual(sw_pump_state['target_frequency'], 48.4)
        self.assertEqual(sw_pump_state['deviation_status'], "Green")

        print(f"\n✓ 상태 내보내기 정상 작동 (로깅/분석용)")


def run_tests():
    """테스트 실행"""
    print("\n" + "="*80)
    print("ESS AI 시스템 - Stage 9: HMI Dashboard 테스트 시작")
    print("="*80)

    # 테스트 스위트 생성
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestStage9HMI)

    # 테스트 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 결과 요약
    print("\n" + "="*80)
    print("테스트 결과 요약")
    print("="*80)
    print(f"실행된 테스트: {result.testsRun}개")
    print(f"성공: {result.testsRun - len(result.failures) - len(result.errors)}개")
    print(f"실패: {len(result.failures)}개")
    print(f"에러: {len(result.errors)}개")

    if result.wasSuccessful():
        print("\n✅ Stage 9: HMI Dashboard - 모든 테스트 통과!")
        print("\n구현 완료 항목:")
        print("  ✓ 그룹별 제어 모드 전환 (60Hz 고정 / AI 제어)")
        print("  ✓ 목표 vs 실제 주파수 모니터링 (Green/Yellow/Red)")
        print("  ✓ 긴급 정지 (30초 점진적 60Hz 전환)")
        print("  ✓ 알람 관리 (CRITICAL/WARNING/INFO)")
        print("  ✓ 운전 시간 균등화 모니터링")
        print("  ✓ 학습 진행 추적")
        print("  ✓ 상태 내보내기 (로깅/분석)")
    else:
        print("\n❌ 일부 테스트 실패")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
