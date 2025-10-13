#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
시나리오 테스트 데모 - 사용자 입력 없이 실행
"""

import sys
import os

# 경로 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.simulation.scenarios import SimulationScenarios, ScenarioType
import time


def main():
    print("\n" + "="*80)
    print("ESS AI 시스템 - 시나리오 테스트 데모")
    print("="*80 + "\n")

    # 시나리오 생성기 초기화
    scenario_gen = SimulationScenarios()

    # 사용 가능한 시나리오 표시
    print("사용 가능한 시나리오:")
    scenarios = scenario_gen.get_available_scenarios()
    for idx, (key, name) in enumerate(scenarios.items(), 1):
        print(f"  {idx}. {name}")
    print()

    # 시나리오 선택 (인자로 받거나 기본값)
    if len(sys.argv) > 1:
        scenario_choice = sys.argv[1]
    else:
        scenario_choice = "1"  # 기본값: 정상 운전

    # 시나리오 타입 매핑
    scenario_map = {
        "1": ScenarioType.NORMAL_OPERATION,
        "2": ScenarioType.HIGH_LOAD,
        "3": ScenarioType.COOLING_FAILURE,
        "4": ScenarioType.PRESSURE_DROP
    }

    if scenario_choice not in scenario_map:
        print(f"잘못된 시나리오 선택: {scenario_choice}")
        print("기본값(1. 정상 운전)으로 실행합니다.")
        scenario_choice = "1"

    scenario_type = scenario_map[scenario_choice]

    # 시나리오 시작
    scenario_gen.start_scenario(scenario_type)

    print("\n" + "="*80)
    print("시나리오 실행 중... (Ctrl+C로 종료)")
    print("="*80 + "\n")

    # 헤더 출력
    print(f"{'시간':>6} | {'진행':>6} | {'T1':>6} | {'T5':>6} | {'T6':>6} | {'PX1':>6} | {'부하':>6}")
    print(f"{'(초)':>6} | {'(%)':>6} | {'(°C)':>6} | {'(°C)':>6} | {'(°C)':>6} | {'(bar)':>6} | {'(%)':>6}")
    print("-" * 80)

    try:
        iteration = 0
        while not scenario_gen.is_scenario_complete():
            # 현재 값 가져오기
            values = scenario_gen.get_current_values()
            progress = scenario_gen.get_scenario_progress()

            # 5초마다 출력
            if iteration % 5 == 0:
                print(f"{scenario_gen.elapsed_seconds:6.0f} | {progress:6.1f} | "
                      f"{values['T1']:6.1f} | {values['T5']:6.1f} | {values['T6']:6.1f} | "
                      f"{values['PX1']:6.2f} | {values['engine_load']:6.1f}")

            iteration += 1
            time.sleep(1)  # 1초 간격

        print("-" * 80)
        print("\n✅ 시나리오 완료!\n")

        # 최종 정보 출력
        info = scenario_gen.get_scenario_info()
        print("시나리오 정보:")
        print(f"  이름: {info['name']}")
        print(f"  설명: {info['description']}")
        print(f"  실행 시간: {info['elapsed_seconds']:.1f}초")
        print(f"  진행률: {info['progress']}")
        print()

    except KeyboardInterrupt:
        print("\n\n❌ 사용자에 의해 중단되었습니다.\n")

    # 시나리오 정보 출력
    info = scenario_gen.get_scenario_info()
    print("="*80)
    print("시나리오 요약")
    print("="*80)
    print(f"시나리오: {info['name']}")
    print(f"설명: {info['description']}")
    print(f"실행 시간: {info['elapsed_seconds']:.1f}초 / {info['duration_minutes']*60}초")
    print(f"진행률: {info['progress']}")
    print(f"완료 여부: {'✅ 완료' if info['is_complete'] else '❌ 미완료'}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
