#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
대시보드 + 시나리오 시뮬레이션 통합 실행
"""

import subprocess
import sys
import time
from src.testing.test_framework import TestFramework, TestCase, TestScenario
from src.adapter.sim_adapter import SimSensorAdapter, SimEquipmentAdapter
from src.simulation.physics_engine import PhysicsEngine, VoyagePattern
import threading


def run_scenario_simulation(scenario_name: str):
    """백그라운드에서 시나리오 시뮬레이션 실행"""
    print(f"\n시나리오 '{scenario_name}' 시뮬레이션 시작...\n")

    # 시뮬레이션 엔진 초기화
    engine = PhysicsEngine()
    sensor_adapter = SimSensorAdapter(engine)
    voyage_pattern = VoyagePattern()
    equipment_adapter = SimEquipmentAdapter(engine, voyage_pattern)

    # 테스트 프레임워크 초기화
    framework = TestFramework(sensor_adapter, equipment_adapter, use_simulation=True)

    # 시나리오 선택
    scenarios = {
        '1': ('정상 운전', TestScenario.NORMAL_OPERATION, 300),
        '2': ('고부하 운전', TestScenario.HIGH_LOAD, 300),
        '3': ('냉각 실패', TestScenario.COOLING_FAILURE, 300),
        '4': ('압력 저하', TestScenario.PRESSURE_DROP, 300)
    }

    if scenario_name not in scenarios:
        print(f"잘못된 시나리오: {scenario_name}")
        return

    name, scenario, duration = scenarios[scenario_name]

    # 테스트 케이스 추가
    framework.add_test_case(TestCase(
        name=name,
        scenario=scenario,
        duration=duration,
        success_criteria={
            'safety_compliance': (80.0, 100.0)
        }
    ))

    # 실행
    framework.run_all_tests()


def main():
    print("\n" + "="*80)
    print("ESS AI 대시보드 + 시나리오 시뮬레이션 통합 실행")
    print("="*80 + "\n")

    print("시나리오 선택:")
    print("  1. 정상 운전 (Normal Operation)")
    print("  2. 고부하 운전 (High Load)")
    print("  3. 냉각 실패 (Cooling Failure)")
    print("  4. 압력 저하 (Pressure Drop)")
    print()

    scenario = input("시나리오 번호를 선택하세요 (1-4): ").strip()

    if scenario not in ['1', '2', '3', '4']:
        print("잘못된 입력입니다.")
        return

    print("\n" + "="*80)
    print("실행 방법:")
    print("="*80)
    print("\n1. 대시보드가 브라우저에서 자동으로 열립니다")
    print("2. 브라우저: http://localhost:8501")
    print("3. 시나리오 시뮬레이션이 백그라운드에서 실행됩니다")
    print("4. 대시보드에서 실시간 데이터를 확인하세요")
    print("\n종료: 터미널에서 Ctrl+C\n")

    # 시나리오 시뮬레이션을 별도 스레드로 실행
    sim_thread = threading.Thread(
        target=run_scenario_simulation,
        args=(scenario,),
        daemon=True
    )
    sim_thread.start()

    # 잠시 대기
    time.sleep(2)

    # Streamlit 대시보드 실행
    print("\n대시보드 시작 중...\n")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "src/hmi/dashboard.py",
        "--server.port", "8501",
        "--server.address", "localhost"
    ])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n프로그램 종료")
