#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
압력 저하 시나리오 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.simulation.scenarios import SimulationScenarios, ScenarioType
import time


def main():
    print("\n" + "="*80)
    print("압력 저하 시나리오 테스트")
    print("="*80 + "\n")

    # 시나리오 엔진 생성
    scenario_gen = SimulationScenarios()

    # 압력 저하 시나리오 시작
    scenario_gen.start_scenario(ScenarioType.PRESSURE_DROP)

    print(f"{'시간(초)':>10} | {'PX1 (bar)':>12} | {'상태':>20}")
    print("-" * 50)

    # 10분간 테스트 (600초)
    for i in range(0, 601, 10):  # 10초 간격으로 출력
        # 시뮬레이션 시간 설정
        scenario_gen.elapsed_seconds = i

        # 현재 값 가져오기
        values = scenario_gen.get_current_values()
        pressure = values['PX1']

        # 상태 판단
        if pressure >= 2.0:
            status = "정상"
        elif pressure >= 1.5:
            status = "주의"
        elif pressure >= 1.0:
            status = "경고"
        else:
            status = "🔴 위험 (1.0 이하)"

        print(f"{i:10d} | {pressure:12.2f} | {status:>20}")

        # 1.0 이하로 떨어진 시점 체크
        if pressure < 1.0 and i > 0:
            print(f"\n✅ {i}초에 압력이 1.0 bar 이하로 떨어졌습니다!")
            break

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
