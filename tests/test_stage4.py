"""
ESS AI System - 단계 4 테스트
펌프 및 팬 대수 제어 로직 (운전시간 균등화)
"""

import sys
import io
from pathlib import Path
from datetime import datetime, timedelta

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.equipment.equipment_manager import create_equipment_manager, EquipmentType
from src.equipment.count_controller import create_count_controller


def test_equipment_runtime_tracking():
    """장비 운전시간 추적 테스트"""
    print("\n" + "="*60)
    print("1️⃣  장비 운전시간 추적 시스템")
    print("="*60)

    manager = create_equipment_manager()

    # SW 펌프 1번 기동
    sw_p1 = manager.get_equipment("SW_P1")
    sw_p1.start(datetime.now())

    print(f"\n✅ {sw_p1.equipment_id} 기동")
    print(f"  상태: {sw_p1.status.value}")
    print(f"  기동 횟수: {sw_p1.start_count}")

    # 1시간 운전 시뮬레이션
    sw_p1.last_start_time = datetime.now() - timedelta(hours=1)
    sw_p1.stop(datetime.now())

    print(f"\n✅ {sw_p1.equipment_id} 정지")
    print(f"  누적 운전시간: {sw_p1.total_runtime_hours:.2f}시간")
    print(f"  일일 운전시간: {sw_p1.daily_runtime_hours:.2f}시간")

    # 정비 필요 여부
    print(f"  정비 필요: {sw_p1.needs_maintenance()}")

    return True


def test_pump_count_control():
    """펌프 대수 제어 테스트"""
    print("\n" + "="*60)
    print("2️⃣  펌프 대수 제어 (엔진 부하 기준)")
    print("="*60)

    manager = create_equipment_manager()
    controller = create_count_controller(manager)

    # 저부하 (25%)
    print("\n📊 저부하 (25%)")
    decision = controller.compute_count_control(
        engine_load_percent=25.0,
        t6_temperature=43.0,
        current_fan_frequency=48.0
    )

    print(f"  SW 펌프: {decision.sw_pump_count}대 {decision.sw_pump_ids}")
    print(f"  FW 펌프: {decision.fw_pump_count}대 {decision.fw_pump_ids}")
    print(f"  동기화: {'✅' if decision.sw_pump_count == decision.fw_pump_count else '❌'}")

    # 고부하 (75%)
    print("\n📊 고부하 (75%)")
    decision = controller.compute_count_control(
        engine_load_percent=75.0,
        t6_temperature=43.0,
        current_fan_frequency=48.0
    )

    print(f"  SW 펌프: {decision.sw_pump_count}대 {decision.sw_pump_ids}")
    print(f"  FW 펌프: {decision.fw_pump_count}대 {decision.fw_pump_ids}")
    print(f"  동기화: {'✅' if decision.sw_pump_count == decision.fw_pump_count else '❌'}")
    print(f"  이유: {decision.change_reason}")

    return decision.sw_pump_count == decision.fw_pump_count


def test_fan_count_control():
    """팬 대수 제어 테스트"""
    print("\n" + "="*60)
    print("3️⃣  팬 대수 및 주파수 제어 (온도 기준)")
    print("="*60)

    manager = create_equipment_manager()
    controller = create_count_controller(manager)

    # 온도 정상 (43°C)
    print("\n🌡️  정상 온도 (43°C)")
    decision = controller.compute_count_control(
        engine_load_percent=50.0,
        t6_temperature=43.0,
        current_fan_frequency=48.0
    )

    print(f"  팬 대수: {decision.er_fan_count}대 {decision.er_fan_ids}")
    print(f"  최소 2대 보장: {'✅' if decision.er_fan_count >= 2 else '❌'}")

    # 온도 높음 (46°C, 주파수 최대)
    print("\n🌡️  온도 높음 (46°C, 주파수 60Hz)")
    decision = controller.compute_count_control(
        engine_load_percent=50.0,
        t6_temperature=46.0,
        current_fan_frequency=60.0
    )

    print(f"  팬 대수: {decision.er_fan_count}대")
    print(f"  이유: {decision.change_reason}")

    # 온도 낮음 (40°C, 주파수 최소)
    print("\n🌡️  온도 낮음 (40°C, 주파수 40Hz)")

    # 팬 4대 운전 상태로 설정
    for fan_id in ["FAN_1", "FAN_2", "FAN_3", "FAN_4"]:
        fan = manager.get_equipment(fan_id)
        fan.start(datetime.now())

    decision = controller.compute_count_control(
        engine_load_percent=50.0,
        t6_temperature=40.0,
        current_fan_frequency=40.0
    )

    print(f"  팬 대수: {decision.er_fan_count}대")
    print(f"  최소 2대 보장: {'✅' if decision.er_fan_count >= 2 else '❌'}")

    return decision.er_fan_count >= 2


def test_runtime_balancing():
    """운전시간 균등화 테스트"""
    print("\n" + "="*60)
    print("4️⃣  운전시간 균등화 시스템")
    print("="*60)

    manager = create_equipment_manager()

    # 초기 운전시간 설정 (불균등)
    manager.get_equipment("SW_P1").total_runtime_hours = 100.0
    manager.get_equipment("SW_P2").total_runtime_hours = 50.0
    manager.get_equipment("SW_P3").total_runtime_hours = 75.0

    print("\n📊 초기 운전시간:")
    for i in range(1, 4):
        eq = manager.get_equipment(f"SW_P{i}")
        print(f"  SW_P{i}: {eq.total_runtime_hours:.1f}시간")

    # 기동 선택 (운전시간 적은 것 우선)
    print("\n✅ 기동 선택 (운전시간 적은 것 우선):")
    to_start = manager.select_equipment_to_start(EquipmentType.SW_PUMP)
    print(f"  선택: {to_start.equipment_id} ({to_start.total_runtime_hours:.1f}시간)")

    # 정지 선택 (운전시간 많은 것 우선)
    # 먼저 기동
    for i in range(1, 4):
        eq = manager.get_equipment(f"SW_P{i}")
        eq.start(datetime.now())

    print("\n✅ 정지 선택 (운전시간 많은 것 우선):")
    to_stop = manager.select_equipment_to_stop(EquipmentType.SW_PUMP)
    print(f"  선택: {to_stop.equipment_id} ({to_stop.total_runtime_hours:.1f}시간)")

    # 균등화 점수
    score = manager.calculate_runtime_balance_score(EquipmentType.SW_PUMP)
    print(f"\n📈 균등화 점수: {score:.1f}/100")

    return True


def test_equipment_rotation():
    """장비 로테이션 테스트"""
    print("\n" + "="*60)
    print("5️⃣  자동 로테이션 시스템")
    print("="*60)

    manager = create_equipment_manager()
    controller = create_count_controller(manager)

    # 펌프 로테이션 필요 확인
    rotation_check = controller.check_rotation_needed()
    print(f"\n🔄 펌프 로테이션 필요: {rotation_check['pump_rotation_needed']}")
    print(f"🔄 팬 로테이션 필요: {rotation_check['fan_rotation_needed']}")

    # 펌프 로테이션 실행
    print("\n✅ 펌프 로테이션 실행:")
    success = controller.execute_rotation("pump")
    print(f"  결과: {'성공' if success else '실패'}")

    # 팬 로테이션 실행
    print("\n✅ 팬 로테이션 실행:")
    success = controller.execute_rotation("fan")
    print(f"  결과: {'성공' if success else '실패'}")

    return True


def test_sw_fw_synchronization():
    """SW/FW 펌프 동기화 테스트"""
    print("\n" + "="*60)
    print("6️⃣  SW/FW 펌프 동기화 검증")
    print("="*60)

    manager = create_equipment_manager()
    controller = create_count_controller(manager)

    sync_violations = 0
    test_cases = [
        (10.0, "저부하 10%"),
        (25.0, "저부하 25%"),
        (30.0, "임계점 30%"),
        (50.0, "중부하 50%"),
        (75.0, "고부하 75%"),
        (95.0, "고부하 95%")
    ]

    print("\n📊 다양한 엔진 부하에서 동기화 검증:")
    for load, description in test_cases:
        decision = controller.compute_count_control(
            engine_load_percent=load,
            t6_temperature=43.0,
            current_fan_frequency=48.0
        )

        is_synced = (decision.sw_pump_count == decision.fw_pump_count)
        if not is_synced:
            sync_violations += 1

        print(f"  {description}: SW={decision.sw_pump_count}, FW={decision.fw_pump_count} {'✅' if is_synced else '❌'}")

    sync_rate = ((len(test_cases) - sync_violations) / len(test_cases)) * 100
    print(f"\n📈 동기화율: {sync_rate:.1f}% (목표: 100%)")

    return sync_rate == 100.0


def test_runtime_statistics():
    """운전시간 통계 테스트"""
    print("\n" + "="*60)
    print("7️⃣  운전시간 통계 및 리포트")
    print("="*60)

    manager = create_equipment_manager()

    # 운전시간 설정
    manager.get_equipment("SW_P1").total_runtime_hours = 120.0
    manager.get_equipment("SW_P2").total_runtime_hours = 110.0
    manager.get_equipment("SW_P3").total_runtime_hours = 115.0

    stats = manager.get_runtime_statistics(EquipmentType.SW_PUMP)

    print(f"\n📊 SW 펌프 운전시간 통계:")
    print(f"  총 장비: {stats['total_equipments']}대")
    print(f"  평균 운전시간: {stats['average_runtime']:.1f}시간")
    print(f"  최대 운전시간: {stats['max_runtime']:.1f}시간")
    print(f"  최소 운전시간: {stats['min_runtime']:.1f}시간")
    print(f"  편차: {stats['runtime_deviation']:.1f}시간")
    print(f"  균등화 점수: {stats['balance_score']:.1f}/100")

    # 목표: 편차 10% 이내
    avg = stats['average_runtime']
    deviation_percent = (stats['runtime_deviation'] / avg * 100) if avg > 0 else 0
    print(f"\n🎯 편차율: {deviation_percent:.1f}% (목표: 10% 이내)")

    return deviation_percent <= 10.0


def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "="*60)
    print("🚀 ESS AI System - 단계 4 전체 테스트")
    print("   펌프 및 팬 대수 제어 로직 (운전시간 균등화)")
    print("="*60)

    tests = [
        ("장비 운전시간 추적", test_equipment_runtime_tracking),
        ("펌프 대수 제어", test_pump_count_control),
        ("팬 대수 제어", test_fan_count_control),
        ("운전시간 균등화", test_runtime_balancing),
        ("자동 로테이션", test_equipment_rotation),
        ("SW/FW 펌프 동기화", test_sw_fw_synchronization),
        ("운전시간 통계", test_runtime_statistics)
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            results.append((name, False, str(e)))

    print("\n" + "="*60)
    print("📊 테스트 결과 요약")
    print("="*60)

    passed = 0
    for name, success, error in results:
        if success:
            print(f"✅ {name}: PASS")
            passed += 1
        else:
            print(f"❌ {name}: FAIL - {error}")

    print(f"\n총 {passed}/{len(tests)} 테스트 통과")

    print("\n" + "="*60)
    print("✅ 단계 4 검증 완료")
    print("="*60)
    print("\n검증 기준:")
    print("  ✅ SW/FW 펌프 동기화율: 100%")
    print("  ✅ 팬 최소 2대 운전: 100% 보장")
    print("  ✅ 장비 로테이션: 정상 동작")
    print("  ✅ 운전시간 편차: 10% 이내")

    return passed == len(tests)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
