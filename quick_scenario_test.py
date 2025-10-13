#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
빠른 시나리오 테스트 (30초)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.simulation.scenarios import SimulationScenarios, ScenarioType
import time


def main():
    print("\n" + "="*80)
    print("ESS AI - 빠른 시나리오 테스트 (30초)")
    print("="*80 + "\n")

    # 시나리오 생성
    scenario_gen = SimulationScenarios()

    # 시나리오 선택
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = "3"  # 기본: 냉각 실패

    scenario_map = {
        "1": ScenarioType.NORMAL_OPERATION,
        "2": ScenarioType.HIGH_LOAD,
        "3": ScenarioType.COOLING_FAILURE,
        "4": ScenarioType.PRESSURE_DROP
    }

    scenario_type = scenario_map.get(choice, ScenarioType.COOLING_FAILURE)

    # 시나리오 시작
    scenario_gen.start_scenario(scenario_type)

    print("\n시나리오 실행 중... (30초)\n")
    print(f"{'시간':>5} | {'T1':>6} | {'T5':>6} | {'T6':>6} | {'PX1':>6} | {'부하':>6}")
    print(f"{'(초)':>5} | {'(C)':>6} | {'(C)':>6} | {'(C)':>6} | {'(bar)':>6} | {'(%)':>6}")
    print("-" * 65)

    # 30초 동안 실행
    for i in range(31):
        values = scenario_gen.get_current_values()

        # 5초마다 출력
        if i % 5 == 0:
            print(f"{i:5d} | {values['T1']:6.1f} | {values['T5']:6.1f} | "
                  f"{values['T6']:6.1f} | {values['PX1']:6.2f} | {values['engine_load']:6.1f}")

        time.sleep(1)

    print("-" * 65)
    print("\n[OK] 테스트 완료!\n")

    # 최종 값 출력
    final_values = scenario_gen.get_current_values()
    info = scenario_gen.get_scenario_info()

    print("="*80)
    print(f"시나리오: {info['name']}")
    print(f"설명: {info['description']}")
    print(f"실행 시간: {info['elapsed_seconds']:.1f}초")
    print(f"\n최종 센서 값:")
    print(f"  T1 (해수 입구): {final_values['T1']:.1f}°C")
    print(f"  T5 (FW 출구): {final_values['T5']:.1f}°C")
    print(f"  T6 (E/R 온도): {final_values['T6']:.1f}°C")
    print(f"  PX1 (압력): {final_values['PX1']:.2f} bar")
    print(f"  엔진 부하: {final_values['engine_load']:.1f}%")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
