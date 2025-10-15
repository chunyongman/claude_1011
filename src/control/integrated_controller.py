"""
ESS AI System - 통합 제어기
- 안전 제약조건 우선순위 제어
- 긴급 제어 모드
- 에너지 절감 + PID 통합
- 온도 예측 기반 선제적 제어
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import os

from .energy_saving import EnergySavingController, ControlStrategy
from .pid_controller import DualPIDController
from ..core.safety_constraints import SafetyConstraints, SafetyLevel
from ..equipment.count_controller import CountController
from ..equipment.equipment_manager import EquipmentManager
from ..ml.temperature_predictor import (
    PolynomialRegressionPredictor,
    TemperatureSequence,
    TemperaturePrediction
)
from ..ml.random_forest_optimizer import RandomForestOptimizer
from ..ml.pattern_classifier import PatternClassifier
from ..ml.predictive_controller import PredictiveController


class ControlPriority(Enum):
    """제어 우선순위"""
    PRIORITY_1_PRESSURE = 1  # PX1 ≥ 1.0 bar
    PRIORITY_2_COOLER_PROTECTION = 2  # T2/T3 < 49°C
    PRIORITY_3_TEMPERATURE_TARGET = 3  # T5, T6 목표
    PRIORITY_4_FW_INLET_LIMIT = 4  # T4 < 48°C
    PRIORITY_5_ENERGY_OPTIMIZATION = 5  # 에너지 최적화


@dataclass
class ControlDecision:
    """제어 결정"""
    sw_pump_freq: float
    fw_pump_freq: float
    er_fan_freq: float
    er_fan_count: int = 2  # E/R 팬 작동 대수
    control_mode: str = ""
    priority_violated: Optional[int] = None
    emergency_action: bool = False
    reason: str = ""
    count_change_reason: str = ""  # 대수 변경 이유
    timestamp: datetime = None
    
    # 예측 정보 (선택적)
    temperature_prediction: Optional[TemperaturePrediction] = None
    use_predictive_control: bool = False


class IntegratedController:
    """
    통합 제어기 - 예측 제어 통합
    """

    def __init__(
        self, 
        equipment_manager: Optional[EquipmentManager] = None,
        enable_predictive_control: bool = True
    ):
        # 하위 제어기
        self.energy_saving = EnergySavingController()
        self.pid_controller = DualPIDController()
        self.safety_constraints = SafetyConstraints()

        # 대수 제어기 (옵션)
        self.count_controller = None
        if equipment_manager:
            self.count_controller = CountController(equipment_manager)

        # 예측 제어 활성화 여부
        self.enable_predictive_control = enable_predictive_control
        self.predictive_controller: Optional[PredictiveController] = None
        self.temp_predictor: Optional[PolynomialRegressionPredictor] = None
        
        # 온도 시퀀스 버퍼 (30분, 20초 간격 = 90개 데이터 포인트)
        self.temp_sequence_buffer = {
            'timestamps': deque(maxlen=90),
            't1': deque(maxlen=90),
            't2': deque(maxlen=90),
            't3': deque(maxlen=90),
            't4': deque(maxlen=90),
            't5': deque(maxlen=90),
            't6': deque(maxlen=90),
            't7': deque(maxlen=90),
            'engine_load': deque(maxlen=90)
        }
        
        # 예측 제어 초기화
        if enable_predictive_control:
            self._initialize_predictive_control()

        # 제어 모드
        self.emergency_mode = False

    def _initialize_predictive_control(self):
        """예측 제어 시스템 초기화"""
        try:
            # 온도 예측기 초기화
            self.temp_predictor = PolynomialRegressionPredictor(degree=2)
            
            # 사전 학습된 모델이 있으면 로드
            model_path = "data/models/temperature_predictor.pkl"
            if os.path.exists(model_path):
                self.temp_predictor.load_model(model_path)
                print(f"[OK] 온도 예측 모델 로드 완료: {model_path}")
            else:
                print("[WARNING] 사전 학습된 모델 없음. 실시간 학습 모드로 시작")
                # 기본 더미 학습 (최소 50개 샘플 필요)
                self._train_dummy_model()
            
            # Random Forest 및 Pattern Classifier 초기화
            rf_optimizer = RandomForestOptimizer(n_trees=5)
            pattern_classifier = PatternClassifier()
            
            # 예측 제어기 생성
            if self.temp_predictor.is_trained:
                self.predictive_controller = PredictiveController(
                    temp_predictor=self.temp_predictor,
                    rf_optimizer=rf_optimizer,
                    pattern_classifier=pattern_classifier
                )
                print("[OK] 예측 제어 시스템 초기화 완료")
            else:
                print("[WARNING] 예측 모델 미학습. 예측 제어 비활성화")
                self.enable_predictive_control = False
                
        except Exception as e:
            print(f"[ERROR] 예측 제어 초기화 실패: {e}")
            self.enable_predictive_control = False

    def _train_dummy_model(self):
        """더미 모델 학습 (최소 동작용)"""
        import numpy as np
        
        # 더미 학습 데이터 생성 (50개, 다양한 패턴)
        training_data = []
        for i in range(50):
            # 다양한 초기 온도 및 부하 조건
            base_t4 = 40.0 + np.random.uniform(-5, 10)
            base_t5 = 32.0 + np.random.uniform(-3, 8)
            base_t6 = 40.0 + np.random.uniform(-5, 10)
            base_load = 50.0 + np.random.uniform(-20, 40)
            
            # 온도 변화 트렌드 (상승/하강/안정)
            trend = np.random.choice([-1, 0, 1])
            
            # 더미 시퀀스 생성 (시간에 따라 변화)
            timestamps = [datetime.now() - timedelta(minutes=30-j*0.33) for j in range(90)]
            t4_seq = [base_t4 + trend * j/90 * 2 + np.random.randn() * 0.3 for j in range(90)]
            t5_seq = [base_t5 + trend * j/90 * 1.5 + np.random.randn() * 0.3 for j in range(90)]
            t6_seq = [base_t6 + trend * j/90 * 2.5 + np.random.randn() * 0.3 for j in range(90)]
            load_seq = [base_load + trend * j/90 * 10 + np.random.randn() * 2 for j in range(90)]
            
            sequence = TemperatureSequence(
                timestamps=timestamps,
                t1_sequence=[25.0 + np.random.randn() * 0.3 for _ in range(90)],
                t2_sequence=[35.0 + np.random.randn() * 0.5 for _ in range(90)],
                t3_sequence=[35.0 + np.random.randn() * 0.5 for _ in range(90)],
                t4_sequence=t4_seq,
                t5_sequence=t5_seq,
                t6_sequence=t6_seq,
                t7_sequence=[30.0 + np.random.randn() * 1.0 for _ in range(90)],
                engine_load_sequence=load_seq
            )
            
            # 더미 타겟 (현재 값 + 트렌드 반영)
            targets = {
                't4_5min': t4_seq[-1] + trend * 0.5, 
                't4_10min': t4_seq[-1] + trend * 1.0, 
                't4_15min': t4_seq[-1] + trend * 1.5,
                't5_5min': t5_seq[-1] + trend * 0.3, 
                't5_10min': t5_seq[-1] + trend * 0.6, 
                't5_15min': t5_seq[-1] + trend * 0.9,
                't6_5min': t6_seq[-1] + trend * 0.5, 
                't6_10min': t6_seq[-1] + trend * 1.0, 
                't6_15min': t6_seq[-1] + trend * 1.5
            }
            training_data.append((sequence, targets))
        
        try:
            self.temp_predictor.train(training_data)
            print("[OK] 더미 모델 학습 완료 (실제 데이터로 재학습 필요)")
        except Exception as e:
            print(f"[ERROR] 더미 모델 학습 실패: {e}")

    def update_temperature_sequence(
        self,
        temperatures: Dict[str, float],
        engine_load: float,
        timestamp: Optional[datetime] = None
    ):
        """온도 시퀀스 버퍼 업데이트"""
        if timestamp is None:
            timestamp = datetime.now()
        
        self.temp_sequence_buffer['timestamps'].append(timestamp)
        self.temp_sequence_buffer['t1'].append(temperatures.get('T1', 25.0))
        self.temp_sequence_buffer['t2'].append(temperatures.get('T2', 35.0))
        self.temp_sequence_buffer['t3'].append(temperatures.get('T3', 35.0))
        self.temp_sequence_buffer['t4'].append(temperatures.get('T4', 45.0))
        self.temp_sequence_buffer['t5'].append(temperatures.get('T5', 35.0))
        self.temp_sequence_buffer['t6'].append(temperatures.get('T6', 43.0))
        self.temp_sequence_buffer['t7'].append(temperatures.get('T7', 30.0))
        self.temp_sequence_buffer['engine_load'].append(engine_load)

    def _get_temperature_sequence(self) -> Optional[TemperatureSequence]:
        """버퍼에서 TemperatureSequence 생성"""
        # 최소 30개 데이터 포인트 필요 (10분)
        if len(self.temp_sequence_buffer['timestamps']) < 30:
            return None
        
        try:
            return TemperatureSequence(
                timestamps=list(self.temp_sequence_buffer['timestamps']),
                t1_sequence=list(self.temp_sequence_buffer['t1']),
                t2_sequence=list(self.temp_sequence_buffer['t2']),
                t3_sequence=list(self.temp_sequence_buffer['t3']),
                t4_sequence=list(self.temp_sequence_buffer['t4']),
                t5_sequence=list(self.temp_sequence_buffer['t5']),
                t6_sequence=list(self.temp_sequence_buffer['t6']),
                t7_sequence=list(self.temp_sequence_buffer['t7']),
                engine_load_sequence=list(self.temp_sequence_buffer['engine_load'])
            )
        except Exception as e:
            print(f"[WARNING] TemperatureSequence 생성 실패: {e}")
            return None

    def compute_control(
        self,
        temperatures: Dict[str, float],
        pressure: float,
        engine_load: float,
        current_frequencies: Dict[str, float]
    ) -> ControlDecision:
        """
        통합 제어 계산

        우선순위:
        1. PX1 ≥ 1.0 bar
        2. T2/T3 < 49°C
        3. T5 = 35±0.5°C, T6 = 43±1.0°C
        4. T4 < 48°C
        5. 에너지 최적화
        6. 예측 제어 (활성화 시)
        """
        # 온도 시퀀스 버퍼 업데이트
        self.update_temperature_sequence(temperatures, engine_load)
        
        # 온도 예측 수행 (예측 제어 활성화 시)
        temp_prediction = None
        if self.enable_predictive_control and self.predictive_controller:
            temp_sequence = self._get_temperature_sequence()
            if temp_sequence and self.temp_predictor.is_trained:
                try:
                    temp_prediction = self.temp_predictor.predict(temp_sequence)
                except Exception as e:
                    print(f"[WARNING] 온도 예측 실패: {e}")
        
        decision = ControlDecision(
            sw_pump_freq=50.0,
            fw_pump_freq=50.0,
            er_fan_freq=48.0,
            control_mode="normal",
            timestamp=datetime.now(),
            temperature_prediction=temp_prediction,
            use_predictive_control=(temp_prediction is not None)
        )

        # === 긴급 상황 체크 (복합 가능) ===
        emergency_actions = []

        # 우선순위 2: Cooler 보호 (T2/T3 < 49°C, 히스테리시스: 49°C 이상에서 긴급, 47°C 이하에서 해제)
        t2_t3_max = max(temperatures.get('T2', 0), temperatures.get('T3', 0))
        if t2_t3_max >= 49.0:
            decision.sw_pump_freq = 60.0
            emergency_actions.append(f"Cooler 과열: max(T2,T3)={t2_t3_max:.1f}°C ≥ 49°C")
            decision.priority_violated = 2
            decision.emergency_action = True
        elif t2_t3_max >= 47.0:  # 히스테리시스 구간 (47~49°C): 현재값보다 낮추지 않음 (감속 방지)
            current_sw = current_frequencies.get('sw_pump', 50.0)
            # PID가 주파수를 낮추려고 해도 현재값 이상 유지
            # (온도가 여전히 높으므로 감속 방지)
            # 단, emergency_actions에 추가하여 히스테리시스 상태임을 표시
            if current_sw >= 50.0:  # 50 Hz 이상이면 현재 주파수 유지
                decision.sw_pump_freq = current_sw
                emergency_actions.append(f"Cooler 주의: max(T2,T3)={t2_t3_max:.1f}°C (감속 방지, {current_sw:.1f}Hz 유지)")
                decision.priority_violated = 2
                decision.emergency_action = True
            # 50 Hz 미만이면 PID가 처리 (emergency_actions 없음)

        # 우선순위 4: T4 < 48°C (히스테리시스: 48°C 이상에서 긴급, 46°C 이하에서 해제)
        t4_temp = temperatures.get('T4', 0)
        if t4_temp >= 48.0:
            decision.fw_pump_freq = 60.0
            emergency_actions.append(f"FW 입구 과열: T4={t4_temp:.1f}°C ≥ 48°C")
            if decision.priority_violated is None:
                decision.priority_violated = 4
            decision.emergency_action = True
        elif t4_temp >= 46.0:  # 히스테리시스 구간 (46~48°C): 현재값보다 낮추지 않음 (감속 방지)
            current_fw = current_frequencies.get('fw_pump', 50.0)
            # PID가 주파수를 낮추려고 해도 현재값 이상 유지
            # (온도가 여전히 높으므로 감속 방지)
            if current_fw >= 50.0:  # 50 Hz 이상이면 현재 주파수 유지
                decision.fw_pump_freq = current_fw
                emergency_actions.append(f"FW 입구 주의: T4={t4_temp:.1f}°C (감속 방지, {current_fw:.1f}Hz 유지)")
                if decision.priority_violated is None:
                    decision.priority_violated = 4
                decision.emergency_action = True
            # 50 Hz 미만이면 PID가 처리

        # 우선순위 3-1: T6 온도 제어 (50°C 이상만 긴급 처리)
        t6_temp = temperatures.get('T6', 43.0)
        if t6_temp >= 50.0:
            # 50°C 이상: 긴급 상황만 여기서 처리
            decision.er_fan_freq = 60.0
            emergency_actions.append(f"E/R 심각한 과열: T6={t6_temp:.1f}°C ≥ 50.0°C → 60Hz 강제")
            if decision.priority_violated is None:
                decision.priority_violated = 3
            decision.emergency_action = True
        # 45°C 초과는 긴급이 아니므로 PID 이후 처리 (아래에서 오버라이드)

        # 긴급 상황이 있으면 즉시 반환 (단, 다른 온도 경고도 추가)
        if emergency_actions:
            if len(emergency_actions) > 1:
                decision.control_mode = "emergency_multiple"
            elif t2_t3_max >= 49.0:
                decision.control_mode = "emergency_cooler"
            elif t6_temp >= 47.0:
                decision.control_mode = "emergency_er"
            else:
                decision.control_mode = "emergency_fw_inlet"

            # 추가 경고 정보 (T5, T6 - 긴급 제어가 아닌 경우만 표시)
            warnings = []
            t5 = temperatures.get('T5', 35.0)
            if t5 > 37.0:  # T5 목표 35°C + 2°C 마진
                warnings.append(f"T5={t5:.1f}°C (목표 35°C)")
            # T6는 이미 긴급 제어로 처리되므로 여기서는 표시하지 않음

            if warnings:
                decision.reason = " | ".join(emergency_actions) + " [추가 경고: " + ", ".join(warnings) + "]"
            else:
                decision.reason = " | ".join(emergency_actions)

            # 긴급 상황에서도 대수 제어 수행 (30초 지연)
            if self.count_controller:
                # 실제 시스템: EquipmentManager 기반 대수 제어
                current_fan_count = current_frequencies.get('er_fan_count', 2)
                fan_count, fan_reason = self.count_controller.decide_fan_count(
                    t6_temperature=temperatures.get('T6', 43.0),
                    current_count=current_fan_count,
                    current_frequency=decision.er_fan_freq
                )
                decision.er_fan_count = fan_count
                if fan_count != current_fan_count:
                    decision.count_change_reason = fan_reason
            else:
                # 시뮬레이션: 30초 지연을 가진 대수 제어 로직
                current_count = current_frequencies.get('er_fan_count', 3)  # 기본 3대
                t6 = temperatures.get('T6', 43.0)

                # 시간 추적 (세션 상태 사용 - current_frequencies에 저장)
                time_at_max = current_frequencies.get('time_at_max_freq', 0)
                time_at_min = current_frequencies.get('time_at_min_freq', 0)

                # 대수 증가 조건: 주파수 ≥ 58Hz & 10초 대기 (시뮬레이션 스케일)
                # 로직: 60Hz로 최대 출력 중 = 냉각 수요가 높음 → 10초 후 대수 증가
                # 시뮬레이션 10초 = 실제 약 30초 (시간 스케일 조정)
                if decision.er_fan_freq >= 58.0:
                    if time_at_max >= 10 and current_count < 4:
                        decision.er_fan_count = current_count + 1
                        decision.count_change_reason = f"✅ 60Hz 30초 유지 (T6={t6:.1f}°C) → 팬 {current_count}→{current_count + 1}대 증가"
                        current_frequencies['time_at_max_freq'] = 0  # 리셋
                    else:
                        decision.er_fan_count = current_count
                        new_time = time_at_max + 2  # 2초씩 증가
                        current_frequencies['time_at_max_freq'] = new_time
                        if time_at_max >= 10:
                            decision.count_change_reason = f"[DEBUG] Timer={new_time}s, Count={current_count} (최대 4대)"
                        else:
                            decision.count_change_reason = f"[DEBUG] 60Hz 유지중 (T6={t6:.1f}°C), Timer={new_time}s/10s, Count={current_count}"
                    # 최소 조건 타이머는 리셋
                    current_frequencies['time_at_min_freq'] = 0
                # 대수 감소 조건: 주파수 ≤ 40Hz & 10초 대기
                elif decision.er_fan_freq <= 40.0:
                    if time_at_min >= 10 and current_count > 3:
                        decision.er_fan_count = current_count - 1
                        decision.count_change_reason = f"✅ 40Hz 30초 유지 (T6={t6:.1f}°C) → 팬 {current_count}→{current_count - 1}대 감소"
                        current_frequencies['time_at_min_freq'] = 0  # 리셋
                    else:
                        decision.er_fan_count = current_count
                        new_time = time_at_min + 2  # 2초씩 증가
                        current_frequencies['time_at_min_freq'] = new_time
                        decision.count_change_reason = f"[DEBUG] 40Hz 유지중 (T6={t6:.1f}°C), Timer={new_time}s/10s (감소대기)"
                    # 최대 조건 타이머는 리셋
                    current_frequencies['time_at_max_freq'] = 0
                else:
                    # 조건 미충족 시 현재 대수 유지 및 타이머 리셋
                    decision.er_fan_count = current_count
                    current_frequencies['time_at_max_freq'] = 0
                    current_frequencies['time_at_min_freq'] = 0
                    decision.count_change_reason = f"[정상] Freq={decision.er_fan_freq:.1f}Hz, T6={t6:.1f}°C, Count={current_count}대"

            return decision

        # === 우선순위 3 & 5: PID + 에너지 절감 + 예측 제어 ===
        
        # 예측 제어 활성화 여부 판단
        use_predictive = (
            temp_prediction is not None and
            self.enable_predictive_control and
            temp_prediction.confidence > 0.5
        )
        
        if use_predictive:
            # === 예측 기반 선제적 제어 ===
            # 10분 후 온도 변화 예측
            t4_delta = temp_prediction.t4_pred_10min - temp_prediction.t4_current
            t5_delta = temp_prediction.t5_pred_10min - temp_prediction.t5_current
            t6_delta = temp_prediction.t6_pred_10min - temp_prediction.t6_current
            
            # 기본 PID 제어
            pid_output = self.pid_controller.compute_control_outputs(
                t5_measured=temperatures.get('T5', 35.0),
                t6_measured=temperatures.get('T6', 43.0),
                engine_load_percent=engine_load,
                seawater_temp=temperatures.get('T1', 28.0),
                dt_seconds=2.0
            )
            
            # 예측 보정: 각 온도별 독립적인 증속 전략
            sw_adjustment = 0.0   # SW 펌프 (T5 냉각용)
            fw_adjustment = 0.0   # FW 펌프 (T4 냉각용)
            fan_adjustment = 0.0  # E/R 팬 (T6 냉각용)
            reasons = []
            
            # T4 (FW Inlet) 상승 예상 → FW 펌프 증속
            if t4_delta > 1.0:
                fw_adjustment = 3.0  # FW 순환 증가
                reasons.append(f"T4 {t4_delta:+.1f}°C 예상 → FW 펌프 +3Hz")
            elif t4_delta > 0.5:
                fw_adjustment = 2.0
                reasons.append(f"T4 {t4_delta:+.1f}°C 예상 → FW 펌프 +2Hz")
            
            # T5 (FW Outlet) 상승 예상 → SW 펌프 증속 (Cooler에 해수 더 공급)
            if t5_delta > 0.5:
                sw_adjustment = 3.0  # Cooler 냉각 능력 증가
                reasons.append(f"T5 {t5_delta:+.1f}°C 예상 → SW 펌프 +3Hz")
            elif t5_delta > 0.3:
                sw_adjustment = 2.0
                reasons.append(f"T5 {t5_delta:+.1f}°C 예상 → SW 펌프 +2Hz")
            
            # T6 (E/R Temperature) 상승 예상 → E/R 팬 증속
            if t6_delta > 1.0:
                fan_adjustment = 4.0  # 기관실 환기 증가
                reasons.append(f"T6 {t6_delta:+.1f}°C 예상 → E/R 팬 +4Hz")
            elif t6_delta > 0.5:
                fan_adjustment = 2.0
                reasons.append(f"T6 {t6_delta:+.1f}°C 예상 → E/R 팬 +2Hz")
            
            # 각 장비별 독립적으로 예측 보정 적용
            decision.sw_pump_freq = min(60.0, pid_output['sw_pump_freq'] + sw_adjustment)
            decision.er_fan_freq = min(60.0, pid_output['er_fan_freq'] + fan_adjustment)
            # FW 펌프는 에너지 절감 제어 기반 (T4)
            energy_decision = self.energy_saving.evaluate_control_decision(
                temperatures=temperatures,
                current_frequencies=current_frequencies
            )
            decision.fw_pump_freq = min(60.0, energy_decision['fw_pump_freq'] + fw_adjustment)
            
            decision.control_mode = "predictive_control"
            if reasons:
                decision.reason = f"예측 제어: {', '.join(reasons)}"
            else:
                decision.reason = f"예측 제어: T4 {t4_delta:+.1f}°C, T5 {t5_delta:+.1f}°C, T6 {t6_delta:+.1f}°C (10분 후, 안정)"
        else:
            # === 기존 PID + 에너지 절감 제어 ===
            # PID 제어
            pid_output = self.pid_controller.compute_control_outputs(
                t5_measured=temperatures.get('T5', 35.0),
                t6_measured=temperatures.get('T6', 43.0),
                engine_load_percent=engine_load,
                seawater_temp=temperatures.get('T1', 28.0),
                dt_seconds=2.0
            )

            # 에너지 절감 제어
            energy_decision = self.energy_saving.evaluate_control_decision(
                temperatures=temperatures,
                current_frequencies=current_frequencies
            )

            # 통합 결정 (PID + 에너지 절감)
            decision.sw_pump_freq = max(
                pid_output['sw_pump_freq'],
                energy_decision['sw_pump_freq']
            )

            # E/R 팬은 PID 우선 (온도가 높을 때는 에너지 절감보다 냉각 우선)
            decision.er_fan_freq = pid_output['er_fan_freq']
            
            decision.fw_pump_freq = energy_decision['fw_pump_freq']  # FW 펌프는 T4 기반 (Energy Saving)

        # T6 온도 범위 기반 즉각 대응 (항상 적용!)
        # PID나 예측 제어와 관계없이 현재 온도에 따라 최소/최대 주파수 보장
        t6_temp = temperatures.get('T6', 43.0)
        current_er_freq = current_frequencies.get('er_fan', 48.0)
        
        # 디버깅: PID 출력 확인
        print(f"[DEBUG] T6={t6_temp:.1f}°C, PID 출력 E/R 팬={decision.er_fan_freq:.1f}Hz (변경 전)")

        # 현재 온도 기반 즉각 대응 (온도 우선!)
        if t6_temp > 46.0:
            # 46°C 초과: 60Hz 긴급
            decision.er_fan_freq = 60.0
            decision.control_mode = "emergency_t6"
            decision.reason = f"🚨 T6={t6_temp:.1f}°C > 46°C → 60Hz 긴급!"
        elif t6_temp > 45.0:
            # 45-46°C: 최소 58Hz
            old_freq = decision.er_fan_freq
            decision.er_fan_freq = max(decision.er_fan_freq, 58.0)
            print(f"[DEBUG] T6 > 45°C: {old_freq:.1f}Hz → {decision.er_fan_freq:.1f}Hz (max 58Hz)")
            if not use_predictive:
                decision.control_mode = "high_t6"
                decision.reason = f"⚠️ T6={t6_temp:.1f}°C > 45°C → 최소 58Hz"
        elif t6_temp > 44.0:
            # 44-45°C: 최소 52Hz
            old_freq = decision.er_fan_freq
            decision.er_fan_freq = max(decision.er_fan_freq, 52.0)
            print(f"[DEBUG] T6 > 44°C: {old_freq:.1f}Hz → {decision.er_fan_freq:.1f}Hz (max 52Hz)")
            if not use_predictive:
                decision.control_mode = "elevated_t6"
                decision.reason = f"⚠️ T6={t6_temp:.1f}°C > 44°C → 최소 52Hz"
        elif t6_temp > 42.0:
            # 42-44°C: 최소 48Hz (정상 범위)
            decision.er_fan_freq = max(decision.er_fan_freq, 48.0)
            if not use_predictive and not decision.reason:
                decision.control_mode = "normal_t6"
                decision.reason = f"✅ T6={t6_temp:.1f}°C 정상 → 최소 48Hz"
        elif t6_temp < 40.0:
            # 40°C 미만: 주파수 감소 가능
            decision.er_fan_freq = max(40.0, decision.er_fan_freq)  # 최소 40Hz
            if not use_predictive and not decision.reason:
                decision.control_mode = "low_t6"
                decision.reason = f"✅ T6={t6_temp:.1f}°C < 40°C → 감속 (최소 40Hz)"
        
        print(f"[DEBUG] T6 제어 후 E/R 팬={decision.er_fan_freq:.1f}Hz (최종)")

        # === 우선순위 1: 압력 제약 (주파수 감소 제한) ===
        # PID 제어가 주파수를 낮추려고 해도 압력이 1.0 미만이면 현재 값 이하로 내려가지 않도록 함
        if pressure < 1.0:
            current_sw_freq = current_frequencies.get('sw_pump', 50.0)
            if decision.sw_pump_freq < current_sw_freq:
                # 주파수를 낮추려고 하는 경우 → 현재 값 유지
                decision.sw_pump_freq = current_sw_freq
                decision.control_mode = "pressure_constraint"
                decision.priority_violated = 1
                decision.emergency_action = False  # 긴급은 아니고 제약 조건
                decision.reason = f"압력 제약 활성: {pressure:.2f}bar < 1.0bar → SW 펌프 주파수 감소 제한 (현재 {current_sw_freq:.1f}Hz 유지)"

        # === 대수 제어 (에너지 효율 최적화, 30초 지연) ===
        # 중요: 주파수는 이미 결정되었고, 여기서는 대수만 제어
        if self.count_controller:
            # 실제 시스템: EquipmentManager 기반 대수 제어
            current_fan_count = current_frequencies.get('er_fan_count', 2)
            fan_count, fan_reason = self.count_controller.decide_fan_count(
                t6_temperature=temperatures.get('T6', 43.0),
                current_count=current_fan_count,
                current_frequency=decision.er_fan_freq
            )
            decision.er_fan_count = fan_count
            if fan_count != current_fan_count:
                decision.count_change_reason = fan_reason
        else:
            # 시뮬레이션: 30초 지연을 가진 대수 제어 로직
            current_count = current_frequencies.get('er_fan_count', 3)  # 기본 3대
            t6 = temperatures.get('T6', 43.0)

            # 시간 추적 (세션 상태 사용 - current_frequencies에 저장)
            time_at_max = current_frequencies.get('time_at_max_freq', 0)
            time_at_min = current_frequencies.get('time_at_min_freq', 0)

            # ======================================================
            # E/R 팬 대수 제어 로직 (실제 운전 기준)
            # ======================================================
            # 기본 원칙:
            # 1. 주파수 52Hz 이상 → 대수 증가 검토 (부하 상승)
            # 2. 주파수 42Hz 이하 → 대수 감소 검토 (부하 하강)
            # 3. 42-52Hz 중간 대역 → 현재 대수 유지 (안정 운전)
            # 4. 대수 변경 시 주파수 조정으로 풍량 급변 방지
            # ======================================================

            # 대수 증가 조건: 주파수 ≥ 52Hz & 10초 지속
            if decision.er_fan_freq >= 52.0:
                if time_at_max >= 10 and current_count < 4:
                    decision.er_fan_count = current_count + 1
                    decision.count_change_reason = f"✅ 52Hz 이상 지속 (T6={t6:.1f}°C) → 팬 {current_count}→{current_count + 1}대 증가"
                    current_frequencies['time_at_max_freq'] = 0  # 리셋
                    # 대수 증가 후 주파수 감소 (전체 풍량 유지)
                    decision.er_fan_freq = max(45.0, decision.er_fan_freq - 8.0)
                else:
                    decision.er_fan_count = current_count
                    new_time = time_at_max + 2  # 2초씩 증가
                    current_frequencies['time_at_max_freq'] = new_time
                    if current_count >= 4:
                        decision.count_change_reason = f"[최대] {current_count}대 운전 중 (Max 4대)"
                    else:
                        decision.count_change_reason = f"[증가 대기] {decision.er_fan_freq:.1f}Hz 지속, Timer={new_time}s/10s"
                # 최소 조건 타이머는 리셋
                current_frequencies['time_at_min_freq'] = 0
            
            # 대수 감소 조건: 주파수 ≤ 42Hz & 10초 지속
            elif decision.er_fan_freq <= 42.0:
                if time_at_min >= 10 and current_count > 2:  # 최소 2대 유지
                    decision.er_fan_count = current_count - 1
                    decision.count_change_reason = f"✅ 42Hz 이하 지속 (T6={t6:.1f}°C) → 팬 {current_count}→{current_count - 1}대 감소"
                    current_frequencies['time_at_min_freq'] = 0  # 리셋
                    # 대수 감소 후 주파수 증가 (전체 풍량 유지)
                    decision.er_fan_freq = min(48.0, decision.er_fan_freq + 8.0)
                else:
                    decision.er_fan_count = current_count
                    new_time = time_at_min + 2  # 2초씩 증가
                    current_frequencies['time_at_min_freq'] = new_time
                    if current_count <= 2:
                        decision.count_change_reason = f"[최소] {current_count}대 운전 중 (Min 2대)"
                    else:
                        decision.count_change_reason = f"[감소 대기] {decision.er_fan_freq:.1f}Hz 지속, Timer={new_time}s/10s"
                # 최대 조건 타이머는 리셋
                current_frequencies['time_at_max_freq'] = 0
            
            # 중간 대역 (42-52Hz): 현재 대수 안정 유지
            else:
                decision.er_fan_count = current_count
                current_frequencies['time_at_max_freq'] = 0
                current_frequencies['time_at_min_freq'] = 0
                decision.count_change_reason = f"[안정] {decision.er_fan_freq:.1f}Hz, T6={t6:.1f}°C, {current_count}대 운전"

        return decision

    def get_control_summary(self) -> str:
        """제어 요약"""
        summary = []
        summary.append("🎮 통합 제어 상태")
        summary.append(f"  긴급 모드: {'🚨 Yes' if self.emergency_mode else '✅ No'}")

        # PID 정보
        pid_info = self.pid_controller.get_controllers_info()
        summary.append(f"\n  T5 제어: {pid_info['t5_controller']['error']:.2f}°C 오차")
        summary.append(f"  T6 제어: {pid_info['t6_controller']['error']:.2f}°C 오차")

        # 에너지 절감 정보
        summary.append(f"\n{self.energy_saving.get_savings_summary()}")

        return "\n".join(summary)


def create_integrated_controller() -> IntegratedController:
    """통합 제어기 생성"""
    return IntegratedController()
