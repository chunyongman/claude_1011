#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
시나리오 기반 테스트 실행 스크립트
"""

from src.testing.test_framework import TestFramework, TestCase, TestScenario
from src.adapter.sim_adapter import SimSensorAdapter, SimEquipmentAdapter
from src.simulation.physics_engine import PhysicsEngine, VoyagePattern


def main():
    """메인 함수"""
    # 시뮬레이션 어댑터 초기화
    engine = PhysicsEngine()
    sensor_adapter = SimSensorAdapter(engine)
    voyage_pattern = VoyagePattern()
    equipment_adapter = SimEquipmentAdapter(engine, voyage_pattern)

    # 테스트 프레임워크 초기화
    framework = TestFramework(sensor_adapter, equipment_adapter, use_simulation=True)

    # 테스트 케이스 추가
    framework.add_test_case(TestCase(
        name='정상 운전 테스트',
        scenario=TestScenario.NORMAL_OPERATION,
        duration=60,
        success_criteria={
            't5_target_achieved': (80.0, 100.0),
            't6_target_achieved': (80.0, 100.0),
            'avg_energy_savings': (30.0, 60.0),
            'safety_compliance': (95.0, 100.0)
        }
    ))

    framework.add_test_case(TestCase(
        name='고부하 운전 테스트',
        scenario=TestScenario.HIGH_LOAD,
        duration=120,
        success_criteria={
            't5_target_achieved': (70.0, 100.0),
            't6_target_achieved': (70.0, 100.0),
            'safety_compliance': (90.0, 100.0)
        }
    ))

    framework.add_test_case(TestCase(
        name='냉각 실패 테스트',
        scenario=TestScenario.COOLING_FAILURE,
        duration=90,
        success_criteria={
            'safety_compliance': (80.0, 100.0)
        }
    ))

    framework.add_test_case(TestCase(
        name='압력 저하 테스트',
        scenario=TestScenario.PRESSURE_DROP,
        duration=60,
        success_criteria={
            'safety_compliance': (85.0, 100.0)
        }
    ))

    # 모든 테스트 실행
    print("\n시나리오 기반 테스트를 시작합니다...\n")
    results = framework.run_all_tests()

    print("\n=== 테스트 완료 ===")
    print(f"PASS: {results['PASS']}개")
    print(f"FAIL: {results['FAIL']}개")
    print(f"WARN: {results['WARN']}개")


if __name__ == "__main__":
    main()
