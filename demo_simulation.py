#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
시뮬레이션 데모 - 터미널 출력
"""

from src.simulation.physics_engine import PhysicsEngine
import time

def main():
    print("\n" + "="*80)
    print("ESS AI 시뮬레이션 엔진 - 실시간 물리 시뮬레이션")
    print("="*80 + "\n")

    # 시뮬레이션 엔진 초기화
    engine = PhysicsEngine()

    print("초기 상태:")
    print(f"  해수 온도 (T1): {engine.T1:.1f}°C")
    print(f"  SW Cooler 출구 (T2/T3): {engine.T2:.1f}°C / {engine.T3:.1f}°C")
    print(f"  FW 냉각수 (T4→T5): {engine.T4:.1f}°C → {engine.T5:.1f}°C")
    print(f"  E/R 온도 (T6): {engine.T6:.1f}°C")
    print(f"  외기 온도 (T7): {engine.T7:.1f}°C")
    print(f"  SW 압력 (PX1): {engine.PX1:.1f} bar")
    print()

    # 시뮬레이션 실행
    print("시뮬레이션 시작 (60초 동안 실행)\n")
    print("-" * 80)
    print(f"{'시간':>5} | {'T1':>6} | {'T2':>6} | {'T3':>6} | {'T5':>6} | {'T6':>6} | {'PX1':>6} | {'전력':>8}")
    print(f"{'(초)':>5} | {'(°C)':>6} | {'(°C)':>6} | {'(°C)':>6} | {'(°C)':>6} | {'(°C)':>6} | {'(bar)':>6} | {'(kW)':>8}")
    print("-" * 80)

    # 제어 설정
    control = {
        'sw_pump_count': 2,
        'sw_pump_freq': 48.0,
        'fw_pump_count': 2,
        'fw_pump_freq': 48.0,
        'er_fan_count': 3,
        'er_fan_freq': 50.0
    }

    for t in range(60):
        # 엔진 부하 시뮬레이션 (50% → 70% 점진 증가)
        engine_load = 50.0 + (t / 60.0) * 20.0

        # 1초 시뮬레이션
        state = engine.step(
            sw_pump_count=control['sw_pump_count'],
            sw_pump_freq=control['sw_pump_freq'],
            fw_pump_count=control['fw_pump_count'],
            fw_pump_freq=control['fw_pump_freq'],
            er_fan_count=control['er_fan_count'],
            er_fan_freq=control['er_fan_freq'],
            engine_load=engine_load
        )

        # 전력 계산
        pump_power = engine.sw_pump.get_power(control['sw_pump_freq']) * control['sw_pump_count']
        fan_power = engine.er_fan.get_power(control['er_fan_freq']) * control['er_fan_count']
        total_power = pump_power + fan_power

        # 5초마다 출력
        if t % 5 == 0:
            print(f"{t:5d} | {state['T1']:6.1f} | {state['T2']:6.1f} | {state['T3']:6.1f} | "
                  f"{state['T5']:6.1f} | {state['T6']:6.1f} | {state['PX1']:6.2f} | {total_power:8.1f}")

    print("-" * 80)
    print("\n시뮬레이션 완료!")

    # 최종 결과 요약
    print("\n최종 상태:")
    print(f"  엔진 부하: 50% → 70%")
    print(f"  T5 (FW 출구): {engine.T5:.1f}°C (목표: 35°C)")
    print(f"  T6 (E/R 온도): {engine.T6:.1f}°C (목표: 43°C)")
    print(f"  총 전력 소비: {total_power:.1f} kW")

    # 60Hz 대비 절감 계산
    power_60hz = engine.sw_pump.get_power(60.0) * 2 + engine.er_fan.get_power(60.0) * 3
    savings = (1 - total_power / power_60hz) * 100
    print(f"  60Hz 대비 절감: {savings:.1f}%")
    print()

if __name__ == "__main__":
    main()
