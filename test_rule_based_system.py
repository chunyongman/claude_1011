"""
Rule-based AI 제어 시스템 테스트
"""

import sys
from datetime import datetime

# 경로 추가
sys.path.append('.')

from src.control.rule_based_controller import RuleBasedController
from src.control.integrated_controller import IntegratedController


def test_rule_based_controller():
    """Rule-based 제어기 단독 테스트"""
    print("=" * 60)
    print("Test 1: Rule-based Controller")
    print("=" * 60)
    
    controller = RuleBasedController()
    
    # 테스트 케이스 1: 정상 운전
    print("\n[테스트 1] 정상 운전")
    temperatures = {
        'T1': 28.0, 'T2': 35.0, 'T3': 35.0, 'T4': 42.0,
        'T5': 35.0, 'T6': 43.0, 'T7': 30.0
    }
    decision = controller.compute_control(
        temperatures=temperatures,
        pressure=2.0,
        engine_load=75.0,
        ml_prediction=None
    )
    
    print(f"  SW 펌프: {decision.sw_pump_freq:.1f} Hz")
    print(f"  FW 펌프: {decision.fw_pump_freq:.1f} Hz")
    print(f"  E/R 팬: {decision.er_fan_freq:.1f} Hz")
    print(f"  적용 규칙: {', '.join(decision.applied_rules)}")
    print(f"  이유: {decision.reason}")
    print(f"  안전 오버라이드: {decision.safety_override}")
    
    # 테스트 케이스 2: Cooler 과열 (긴급)
    print("\n[테스트 2] Cooler 과열 (T2 = 50°C)")
    temperatures['T2'] = 50.0
    decision = controller.compute_control(
        temperatures=temperatures,
        pressure=2.0,
        engine_load=75.0,
        ml_prediction=None
    )
    
    print(f"  SW 펌프: {decision.sw_pump_freq:.1f} Hz (예상: 60.0)")
    print(f"  적용 규칙: {', '.join(decision.applied_rules)}")
    print(f"  이유: {decision.reason}")
    print(f"  안전 오버라이드: {decision.safety_override} (예상: True)")
    
    # 테스트 케이스 3: 압력 저하
    print("\n[테스트 3] 압력 저하 (PX1 = 0.8 bar)")
    temperatures['T2'] = 35.0  # 정상으로 복구
    temperatures['T5'] = 34.0  # T5 낮음 (감속 시도)
    decision = controller.compute_control(
        temperatures=temperatures,
        pressure=0.8,  # 압력 낮음
        engine_load=75.0,
        ml_prediction=None
    )
    
    print(f"  SW 펌프: {decision.sw_pump_freq:.1f} Hz")
    print(f"  적용 규칙: {', '.join(decision.applied_rules)}")
    print(f"  이유: {decision.reason}")
    print(f"  압력 제약 적용 여부: {'S4_PRESSURE_CONSTRAINT' in decision.applied_rules}")
    
    # 테스트 케이스 4: ML 예측 통합
    print("\n[테스트 4] ML 예측 통합")
    temperatures['T5'] = 35.0
    ml_prediction = {
        'sw_pump_freq': 50.0,
        'fw_pump_freq': 49.0,
        'er_fan_freq': 48.0
    }
    decision = controller.compute_control(
        temperatures=temperatures,
        pressure=2.0,
        engine_load=75.0,
        ml_prediction=ml_prediction
    )
    
    print(f"  SW 펌프: {decision.sw_pump_freq:.1f} Hz")
    print(f"  FW 펌프: {decision.fw_pump_freq:.1f} Hz")
    print(f"  E/R 팬: {decision.er_fan_freq:.1f} Hz")
    print(f"  ML 예측 사용: {decision.ml_prediction_used}")
    print(f"  적용 규칙: {', '.join(decision.applied_rules)}")
    
    print("\nRule-based Controller test completed!")


def test_integrated_controller():
    """통합 제어기 테스트"""
    print("\n" + "=" * 60)
    print("Test 2: Integrated Controller")
    print("=" * 60)
    
    controller = IntegratedController(enable_predictive_control=True)
    
    # 테스트 케이스 1: 정상 운전
    print("\n[테스트 1] 정상 운전 (통합 제어)")
    temperatures = {
        'T1': 28.0, 'T2': 35.0, 'T3': 35.0, 'T4': 42.0,
        'T5': 35.0, 'T6': 43.0, 'T7': 30.0
    }
    current_frequencies = {
        'sw_pump': 48.0,
        'fw_pump': 48.0,
        'er_fan': 48.0,
        'er_fan_count': 3,
        'time_at_max_freq': 0,
        'time_at_min_freq': 0
    }
    
    decision = controller.compute_control(
        temperatures=temperatures,
        pressure=2.0,
        engine_load=75.0,
        current_frequencies=current_frequencies
    )
    
    print(f"  SW 펌프: {decision.sw_pump_freq:.1f} Hz")
    print(f"  FW 펌프: {decision.fw_pump_freq:.1f} Hz")
    print(f"  E/R 팬: {decision.er_fan_freq:.1f} Hz ({decision.er_fan_count}대)")
    print(f"  제어 모드: {decision.control_mode}")
    print(f"  이유: {decision.reason}")
    if decision.applied_rules:
        print(f"  적용 규칙: {', '.join(decision.applied_rules)}")
    
    # 테스트 케이스 2: 온도 시퀀스 업데이트 및 예측
    print("\n[테스트 2] 온도 예측 (30개 데이터 포인트 후)")
    for i in range(35):
        controller.update_temperature_sequence(temperatures, 75.0)
    
    decision = controller.compute_control(
        temperatures=temperatures,
        pressure=2.0,
        engine_load=75.0,
        current_frequencies=current_frequencies
    )
    
    print(f"  예측 제어 사용: {decision.use_predictive_control}")
    if decision.temperature_prediction:
        pred = decision.temperature_prediction
        print(f"  T5 예측 (10분 후): {pred.t5_pred_10min:.1f}°C (현재: {pred.t5_current:.1f}°C)")
        print(f"  T6 예측 (10분 후): {pred.t6_pred_10min:.1f}°C (현재: {pred.t6_current:.1f}°C)")
        print(f"  예측 신뢰도: {pred.confidence * 100:.0f}%")
    
    # 제어 요약 출력
    print("\n[제어 시스템 요약]")
    summary = controller.get_control_summary()
    print(summary)
    
    print("\nIntegrated Controller test completed!")


def test_rule_info():
    """규칙 정보 출력"""
    print("\n" + "=" * 60)
    print("Test 3: Rule-based AI System Info")
    print("=" * 60)
    
    controller = RuleBasedController()
    rule_info = controller.get_rule_info()
    
    print(f"\n제어 방식: {rule_info['controller_type']}")
    
    print("\n[Safety Rules]")
    for rule in rule_info['safety_rules']:
        print(f"  - {rule}")
    
    print("\n[Optimization Rules]")
    for rule in rule_info['optimization_rules']:
        print(f"  - {rule}")
    
    print("\nRule info display completed!")


def main():
    """메인 테스트 함수"""
    print("\n" + "=" * 60)
    print("Rule-based AI Control System Test")
    print("=" * 60)
    
    try:
        # 1. Rule-based Controller 테스트
        test_rule_based_controller()
        
        # 2. Integrated Controller 테스트
        test_integrated_controller()
        
        # 3. 규칙 정보 출력
        test_rule_info()
        
        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Run dashboard: streamlit run src/hmi/dashboard.py")
        print("  2. Check Rule application in Scenario Test")
        print("  3. View applied rules in real-time")
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

