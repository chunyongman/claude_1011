"""
ESS AI System - 통합 제어기 (Rule-based AI)
- Rule-based 제어 로직
- ML 모델 통합 (온도 예측, Random Forest 최적화)
- 안전 제약조건 우선순위 제어
- 대수 제어 통합
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import os

from .energy_saving import EnergySavingController, ControlStrategy
from .rule_based_controller import RuleBasedController, RuleDecision
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


class ControlPriority(Enum):
    """제어 우선순위"""
    PRIORITY_1_SAFETY = 1  # 안전 제약 (T2/T3, T4, T6, PX1)
    PRIORITY_2_ML_OPTIMIZATION = 2  # ML 최적화
    PRIORITY_3_RULE_FINETUNING = 3  # Rule 미세 조정
    PRIORITY_4_ENERGY_SAVING = 4  # 에너지 절감


@dataclass
class ControlDecision:
    """제어 결정"""
    sw_pump_freq: float
    fw_pump_freq: float
    er_fan_freq: float
    er_fan_count: int = 3  # E/R 팬 작동 대수
    control_mode: str = ""
    priority_violated: Optional[int] = None
    emergency_action: bool = False
    reason: str = ""
    count_change_reason: str = ""  # 대수 변경 이유
    timestamp: datetime = None
    
    # 예측 정보 (선택적)
    temperature_prediction: Optional[TemperaturePrediction] = None
    use_predictive_control: bool = False
    
    # Rule 정보
    applied_rules: List[str] = None


class IntegratedController:
    """
    통합 제어기 - Rule-based AI + ML 최적화
    
    제어 계층:
    1. Safety Layer (Rule-based, 최우선)
    2. ML Optimization (Random Forest, 온도 예측)
    3. Rule-based Fine-tuning (미세 조정)
    4. Equipment Count Control (대수 제어)
    """

    def __init__(
        self, 
        equipment_manager: Optional[EquipmentManager] = None,
        enable_predictive_control: bool = True
    ):
        # Rule-based 제어기 (핵심)
        self.rule_controller = RuleBasedController()
        
        # 에너지 절감 제어기 (보조)
        self.energy_saving = EnergySavingController()
        
        # 안전 제약조건
        self.safety_constraints = SafetyConstraints()

        # 대수 제어기 (옵션)
        self.count_controller = None
        if equipment_manager:
            self.count_controller = CountController(equipment_manager)

        # 예측 제어 활성화 여부
        self.enable_predictive_control = enable_predictive_control
        self.temp_predictor: Optional[PolynomialRegressionPredictor] = None
        self.rf_optimizer: Optional[RandomForestOptimizer] = None
        self.pattern_classifier: Optional[PatternClassifier] = None
        
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
        
        # ML 모델 초기화
        if enable_predictive_control:
            self._initialize_ml_models()

        # 제어 모드
        self.emergency_mode = False

    def _initialize_ml_models(self):
        """ML 모델 초기화"""
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
            self.rf_optimizer = RandomForestOptimizer(n_trees=5)
            self.pattern_classifier = PatternClassifier()
            
            print("[OK] ML 모델 초기화 완료 (Rule-based 제어 보조용)")
                
        except Exception as e:
            print(f"[ERROR] ML 모델 초기화 실패: {e}")
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

    def _get_ml_prediction(
        self,
        temperatures: Dict[str, float],
        engine_load: float,
        temp_prediction: Optional[TemperaturePrediction] = None
    ) -> Optional[Dict[str, float]]:
        """
        ML 모델 기반 최적 주파수 예측
        
        Returns:
            {'sw_pump_freq', 'fw_pump_freq', 'er_fan_freq'} 또는 None
        """
        if not self.rf_optimizer:
            return None
        
        try:
            # Random Forest로 최적 주파수 예측
            # (실제로는 학습된 모델 사용, 여기서는 간단한 휴리스틱)
            
            # 기본 주파수 (엔진 부하 기반)
            if engine_load > 80:
                base_freq = 52.0
            elif engine_load > 50:
                base_freq = 48.0
            else:
                base_freq = 45.0
            
            # 온도 예측 반영 (선제적 조치)
            sw_adj = 0.0
            fw_adj = 0.0
            er_adj = 0.0
            
            if temp_prediction and temp_prediction.confidence > 0.5:
                # 10분 후 온도 변화 예측
                t4_delta = temp_prediction.t4_pred_10min - temp_prediction.t4_current
                t5_delta = temp_prediction.t5_pred_10min - temp_prediction.t5_current
                t6_delta = temp_prediction.t6_pred_10min - temp_prediction.t6_current
                
                # 예측 기반 선제적 조정
                if t5_delta > 0.5:
                    sw_adj = 3.0
                elif t5_delta > 0.3:
                    sw_adj = 2.0
                
                if t4_delta > 1.0:
                    fw_adj = 3.0
                elif t4_delta > 0.5:
                    fw_adj = 2.0
                
                if t6_delta > 1.0:
                    er_adj = 4.0
                elif t6_delta > 0.5:
                    er_adj = 2.0
            
            return {
                'sw_pump_freq': base_freq + sw_adj,
                'fw_pump_freq': base_freq + fw_adj,
                'er_fan_freq': base_freq + er_adj
            }
            
        except Exception as e:
            print(f"[WARNING] ML 예측 실패: {e}")
            return None

    def compute_control(
        self,
        temperatures: Dict[str, float],
        pressure: float,
        engine_load: float,
        current_frequencies: Dict[str, float]
    ) -> ControlDecision:
        """
        통합 제어 계산 (Rule-based AI + ML)
        
        제어 흐름:
        1. 온도 시퀀스 업데이트
        2. ML 모델로 온도 예측 및 최적 주파수 계산
        3. Rule-based 제어기로 최종 결정
        4. 대수 제어 적용
        """
        # 온도 시퀀스 버퍼 업데이트
        self.update_temperature_sequence(temperatures, engine_load)
        
        # 온도 예측 수행 (예측 제어 활성화 시)
        temp_prediction = None
        if self.enable_predictive_control and self.temp_predictor:
            temp_sequence = self._get_temperature_sequence()
            if temp_sequence and self.temp_predictor.is_trained:
                try:
                    temp_prediction = self.temp_predictor.predict(temp_sequence)
                except Exception as e:
                    print(f"[WARNING] 온도 예측 실패: {e}")
        
        # ML 기반 최적 주파수 예측
        ml_prediction = self._get_ml_prediction(temperatures, engine_load, temp_prediction)
        
        # Rule-based 제어 계산
        rule_decision = self.rule_controller.compute_control(
            temperatures=temperatures,
            pressure=pressure,
            engine_load=engine_load,
            ml_prediction=ml_prediction
        )
        
        # ControlDecision으로 변환
        decision = ControlDecision(
            sw_pump_freq=rule_decision.sw_pump_freq,
            fw_pump_freq=rule_decision.fw_pump_freq,
            er_fan_freq=rule_decision.er_fan_freq,
            er_fan_count=current_frequencies.get('er_fan_count', 3),
            control_mode="rule_based_ai",
            emergency_action=rule_decision.safety_override,
            reason=rule_decision.reason,
            timestamp=datetime.now(),
            temperature_prediction=temp_prediction,
            use_predictive_control=(temp_prediction is not None and ml_prediction is not None),
            applied_rules=rule_decision.applied_rules
        )
        
        # 예측 제어 정보 추가
        if temp_prediction and ml_prediction:
            decision.control_mode = "rule_based_ai_with_prediction"
        
        # 대수 제어 적용
        decision = self._apply_count_control(
            decision, temperatures, current_frequencies
        )
        
        return decision

    def _apply_count_control(
        self,
        decision: ControlDecision,
        temperatures: Dict[str, float],
        current_frequencies: Dict[str, float]
    ) -> ControlDecision:
        """
        대수 제어 적용
        
        E/R 팬 대수 제어 로직:
        - 60Hz 최대 도달 시 대수 증가 검토
        - 40Hz 최소 도달 시 대수 감소 검토
        - 30초 지연 적용 (떨림 방지)
        """
        if self.count_controller:
            # 실제 시스템: EquipmentManager 기반 대수 제어
            current_fan_count = current_frequencies.get('er_fan_count', 3)
            fan_count, fan_reason = self.count_controller.decide_fan_count(
                t6_temperature=temperatures.get('T6', 43.0),
                current_count=current_fan_count,
                current_frequency=decision.er_fan_freq
            )
            decision.er_fan_count = fan_count
            if fan_count != current_fan_count:
                decision.count_change_reason = fan_reason
        else:
            # 시뮬레이션: 우선순위별 대수 제어 로직
            current_count = current_frequencies.get('er_fan_count', 3)
            t6 = temperatures.get('T6', 43.0)

            # ML 예측값 가져오기
            t6_pred_5min = t6  # 기본값
            if hasattr(decision, 'ml_prediction') and decision.ml_prediction:
                if hasattr(decision.ml_prediction, 't6_pred_5min'):
                    t6_pred_5min = decision.ml_prediction.t6_pred_5min

            # 시간 추적
            time_at_max = current_frequencies.get('time_at_max_freq', 0)
            time_at_min = current_frequencies.get('time_at_min_freq', 0)
            count_change_cooldown = current_frequencies.get('count_change_cooldown', 0)

            # 대수 변경 쿨다운 감소
            if count_change_cooldown > 0:
                current_frequencies['count_change_cooldown'] = count_change_cooldown - 2

            # ===================================================================
            # 대수 증가 로직 (우선순위별)
            # ===================================================================
            
            # Priority 1: 극한 온도 도달 (즉시! 주파수 무관)
            if t6 >= 47.0 and count_change_cooldown <= 0 and current_count < 4:
                decision.er_fan_count = current_count + 1
                decision.count_change_reason = f"[긴급] 극한 온도 {t6:.1f}°C ≥ 47°C → 즉시 {current_count + 1}대 증설!"
                current_frequencies['time_at_max_freq'] = 0
                current_frequencies['time_at_min_freq'] = 0
                current_frequencies['count_change_cooldown'] = 30
                decision.er_fan_freq = max(50.0, decision.er_fan_freq - 8.0)
            
            # Priority 2: 극한 예상 (즉시! 주파수 무관)
            elif t6 >= 46.0 and t6_pred_5min >= 47.0 and count_change_cooldown <= 0 and current_count < 4:
                decision.er_fan_count = current_count + 1
                decision.count_change_reason = f"[선제] 극한 예상 (예측 {t6_pred_5min:.1f}°C ≥ 47°C) → 즉시 {current_count + 1}대 증설!"
                current_frequencies['time_at_max_freq'] = 0
                current_frequencies['time_at_min_freq'] = 0
                current_frequencies['count_change_cooldown'] = 30
                decision.er_fan_freq = max(50.0, decision.er_fan_freq - 8.0)
            
            # Priority 3: 고온 (5초 대기, 주파수 무관)
            elif t6 >= 45.0 and count_change_cooldown <= 0 and current_count < 4:
                new_time = time_at_max + 2
                current_frequencies['time_at_max_freq'] = new_time
                if new_time >= 5:
                    decision.er_fan_count = current_count + 1
                    decision.count_change_reason = f"[고온] {t6:.1f}°C ≥ 45°C, 5초 대기 → {current_count + 1}대 증설"
                    current_frequencies['time_at_max_freq'] = 0
                    current_frequencies['count_change_cooldown'] = 30
                    decision.er_fan_freq = max(50.0, decision.er_fan_freq - 8.0)
                else:
                    decision.er_fan_count = current_count
                    decision.count_change_reason = f"[고온 대기] {t6:.1f}°C ≥ 45°C, {new_time}초/5초 (주파수 {decision.er_fan_freq:.1f}Hz)"
                # 감소 타이머 리셋
                current_frequencies['time_at_min_freq'] = 0
            
            # Priority 4: 정상 (10초 대기, 60Hz 조건 필요)
            elif decision.er_fan_freq >= 59.5 and count_change_cooldown <= 0 and current_count < 4:
                new_time = time_at_max + 2
                current_frequencies['time_at_max_freq'] = new_time
                if new_time >= 10:
                    decision.er_fan_count = current_count + 1
                    decision.count_change_reason = f"[정상] {decision.er_fan_freq:.1f}Hz 10초 지속 → {current_count + 1}대 증설"
                    current_frequencies['time_at_max_freq'] = 0
                    current_frequencies['count_change_cooldown'] = 30
                    decision.er_fan_freq = max(50.0, decision.er_fan_freq - 8.0)
                else:
                    decision.er_fan_count = current_count
                    decision.count_change_reason = f"[증가 대기] {decision.er_fan_freq:.1f}Hz {new_time}초/10초 (T6={t6:.1f}°C)"
                # 감소 타이머 리셋
                current_frequencies['time_at_min_freq'] = 0
            
            # ===================================================================
            # 대수 감소 로직 (10초 대기)
            # ===================================================================
            # 조건: 40.5Hz 이하 (피드백 제어의 부동소수점 오차 허용)
            elif decision.er_fan_freq <= 40.5 and count_change_cooldown <= 0 and current_count > 2:
                new_time = time_at_min + 2
                current_frequencies['time_at_min_freq'] = new_time
                if new_time >= 10:
                    decision.er_fan_count = current_count - 1
                    decision.count_change_reason = f"[절감] {decision.er_fan_freq:.1f}Hz 10초 지속 → {current_count - 1}대 감소"
                    current_frequencies['time_at_min_freq'] = 0
                    current_frequencies['count_change_cooldown'] = 30
                    decision.er_fan_freq = 48.0  # 재분배
                else:
                    decision.er_fan_count = current_count
                    decision.count_change_reason = f"[감소 대기] {decision.er_fan_freq:.1f}Hz {new_time}초/10초"
                
                # 감소 조건에서는 증가 타이머 리셋
                current_frequencies['time_at_max_freq'] = 0
            
            # ===================================================================
            # 현재 대수 유지
            # ===================================================================
            else:
                decision.er_fan_count = current_count
                current_frequencies['time_at_max_freq'] = 0
                current_frequencies['time_at_min_freq'] = 0
                if count_change_cooldown > 0:
                    decision.count_change_reason = f"[안정화] {decision.er_fan_freq:.1f}Hz, T6={t6:.1f}°C, {current_count}대 (쿨다운 {count_change_cooldown}초)"
                elif current_count >= 4:
                    decision.count_change_reason = f"[최대] {current_count}대 운전 중 (Max 4대)"
                elif current_count <= 2:
                    decision.count_change_reason = f"[최소] {current_count}대 운전 중 (Min 2대)"
                else:
                    decision.count_change_reason = f"[안정] {decision.er_fan_freq:.1f}Hz, T6={t6:.1f}°C, {current_count}대 운전"

        return decision

    def get_control_summary(self) -> str:
        """제어 요약"""
        summary = []
        summary.append("Rule-based AI Control System")
        summary.append(f"  Emergency mode: {'Yes' if self.emergency_mode else 'No'}")
        
        # Rule 정보
        rule_info = self.rule_controller.get_rule_info()
        summary.append(f"\n  Control type: {rule_info['controller_type']}")
        summary.append(f"  Safety rules: {len(rule_info['safety_rules'])}")
        summary.append(f"  Optimization rules: {len(rule_info['optimization_rules'])}")
        
        # ML 모델 상태
        if self.enable_predictive_control:
            summary.append(f"\n  ML models: Enabled")
            if self.temp_predictor and self.temp_predictor.is_trained:
                summary.append(f"  Temperature prediction: Available")
            else:
                summary.append(f"  Temperature prediction: Training needed")
        else:
            summary.append(f"\n  ML models: Disabled")

        return "\n".join(summary)


def create_integrated_controller(
    equipment_manager: Optional[EquipmentManager] = None,
    enable_predictive_control: bool = True
) -> IntegratedController:
    """통합 제어기 생성"""
    return IntegratedController(
        equipment_manager=equipment_manager,
        enable_predictive_control=enable_predictive_control
    )
