"""
ESS AI System - Rule-based 제어기
- 명확한 규칙 기반 제어 로직
- ML 모델 예측과 통합
- 안전 제약조건 우선순위 제어
- Edge Computing 최적화
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from datetime import datetime
from enum import Enum


class LoadCategory(Enum):
    """엔진 부하 구간"""
    LOW = "low"          # 0-30%
    MEDIUM = "medium"    # 30-70%
    HIGH = "high"        # 70-100%


class SeawaterCategory(Enum):
    """해수 온도 구간"""
    POLAR = "polar"          # < 15°C
    TEMPERATE = "temperate"  # 15-28°C
    TROPICAL = "tropical"    # > 28°C


@dataclass
class RuleDecision:
    """Rule 기반 제어 결정"""
    sw_pump_freq: float
    fw_pump_freq: float
    er_fan_freq: float
    applied_rules: list  # 적용된 규칙 목록
    reason: str
    safety_override: bool = False
    ml_prediction_used: bool = False


class RuleBasedController:
    """
    Rule-based 제어기
    
    3단계 계층 구조:
    1. Safety Layer (최우선)
    2. ML Optimization (최적화)
    3. Rule-based Fine-tuning (미세 조정)
    """
    
    def __init__(self):
        # 기본 주파수 범위
        self.freq_min = 40.0
        self.freq_max = 60.0
        
        # 온도 목표값
        self.t5_target = 35.0
        self.t6_target = 43.0
        
        # 안전 임계값
        self.t2_t3_limit = 49.0  # Cooler 보호
        self.t4_limit = 48.0     # FW 입구 한계
        self.t6_emergency = 45.0 # E/R 긴급 온도 (Rule R3에서 처리)
        self.px1_min = 1.0       # 최소 압력
        
        # 히스테리시스 (떨림 방지)
        self.hysteresis_freq = 0.5  # Hz
        self.hysteresis_temp = 0.3  # °C
        
        # 이전 제어값 (히스테리시스용)
        self.prev_sw_freq = 48.0
        self.prev_fw_freq = 48.0
        self.prev_er_freq = 48.0
        
    def compute_control(
        self,
        temperatures: Dict[str, float],
        pressure: float,
        engine_load: float,
        ml_prediction: Optional[Dict[str, float]] = None
    ) -> RuleDecision:
        """
        Rule-based 제어 계산
        
        Args:
            temperatures: 온도 센서 딕셔너리 (T1~T7)
            pressure: PX1 압력 (bar)
            engine_load: 엔진 부하율 (%)
            ml_prediction: ML 모델 예측값 (선택적)
        
        Returns:
            RuleDecision: 제어 결정
        """
        applied_rules = []
        reason_parts = []
        
        # 기본값 (ML 예측 또는 현재값)
        if ml_prediction:
            sw_freq = ml_prediction.get('sw_pump_freq', self.prev_sw_freq)
            fw_freq = ml_prediction.get('fw_pump_freq', self.prev_fw_freq)
            er_freq = ml_prediction.get('er_fan_freq', self.prev_er_freq)
            ml_used = True
            applied_rules.append("ML_PREDICTION")
        else:
            sw_freq = self.prev_sw_freq
            fw_freq = self.prev_fw_freq
            er_freq = self.prev_er_freq
            ml_used = False
        
        # ===================================================================
        # 1️⃣ Safety Layer (최우선 - 강제 오버라이드)
        # ===================================================================
        safety_override = False
        
        # Rule S1: Cooler 과열 보호 (T2/T3 < 49°C)
        t2_t3_max = max(temperatures.get('T2', 0), temperatures.get('T3', 0))
        if t2_t3_max >= self.t2_t3_limit:
            sw_freq = self.freq_max
            safety_override = True
            applied_rules.append("S1_COOLER_PROTECTION")
            reason_parts.append(f"[CRITICAL] Cooler 과열 보호: max(T2,T3)={t2_t3_max:.1f}°C >= {self.t2_t3_limit}°C")
        elif t2_t3_max >= (self.t2_t3_limit - 2.0):  # 히스테리시스 구간 (47-49°C)
            # 감속 방지 (현재값 이상 유지)
            sw_freq = max(sw_freq, self.prev_sw_freq)
            applied_rules.append("S1_COOLER_HYSTERESIS")
            reason_parts.append(f"[WARNING] Cooler 주의: max(T2,T3)={t2_t3_max:.1f}°C (감속 방지)")
        
        # Rule S2: FW 입구 온도 한계 (T4 < 48°C)
        t4_temp = temperatures.get('T4', 0)
        if t4_temp >= self.t4_limit:
            fw_freq = self.freq_max
            safety_override = True
            applied_rules.append("S2_FW_INLET_PROTECTION")
            reason_parts.append(f"[CRITICAL] FW 입구 과열: T4={t4_temp:.1f}°C >= {self.t4_limit}°C")
        elif t4_temp >= (self.t4_limit - 2.0):  # 히스테리시스 구간 (46-48°C)
            fw_freq = max(fw_freq, self.prev_fw_freq)
            applied_rules.append("S2_FW_INLET_HYSTERESIS")
            reason_parts.append(f"[WARNING] FW 입구 주의: T4={t4_temp:.1f}°C (감속 방지)")
        
        # Rule S3: 압력 제약 (PX1 < 1.0 bar → SW 펌프 감속 금지)
        # (T6 긴급 온도는 Rule R3에서 처리)
        if pressure < self.px1_min:
            if sw_freq < self.prev_sw_freq:
                sw_freq = self.prev_sw_freq
                applied_rules.append("S3_PRESSURE_CONSTRAINT")
                reason_parts.append(f"[CONSTRAINT] 압력 제약: PX1={pressure:.2f}bar < {self.px1_min}bar (감속 금지)")
        
        # Rule S4: T6 온도 기반 E/R 팬 제어 (Safety + Fine-tuning)
        # T6 제어는 ML보다 우선하여 적용
        t6_temp = temperatures.get('T6', 43.0)
        NORMAL_TARGET_FREQ = 48.0
        
        if t6_temp > 45.0:  # 긴급 고온 (45°C 초과)
            er_freq = self.freq_max  # 강제 60Hz
            safety_override = True
            applied_rules.append("S4_ER_HIGH_TEMP")
            reason_parts.append(f"[CRITICAL] T6={t6_temp:.1f}°C > 45°C → 강제 60Hz")
        
        elif 42.0 <= t6_temp <= 44.0:  # 정상 범위 (42~44°C)
            # 목표 주파수(48Hz)로 수렴 (이전 주파수 기준)
            if self.prev_er_freq > NORMAL_TARGET_FREQ + 0.5:
                er_freq = max(NORMAL_TARGET_FREQ, self.prev_er_freq - 2.0)
                applied_rules.append("S4_T6_NORMAL_DECREASING")
                reason_parts.append(f"정상 복귀 ({self.prev_er_freq:.0f}Hz → {er_freq:.0f}Hz)")
                safety_override = True  # ML 무시
            elif self.prev_er_freq < NORMAL_TARGET_FREQ - 0.5:
                er_freq = min(NORMAL_TARGET_FREQ, self.prev_er_freq + 2.0)
                applied_rules.append("S4_T6_NORMAL_INCREASING")
                reason_parts.append(f"정상 복귀 ({self.prev_er_freq:.0f}Hz → {er_freq:.0f}Hz)")
                safety_override = True  # ML 무시
            else:
                # 목표 주파수 도달 (48Hz ± 0.5Hz)
                er_freq = NORMAL_TARGET_FREQ
                applied_rules.append("S4_T6_NORMAL_HOLD")
                reason_parts.append(f"정상 유지 (48Hz)")
                # 정상 유지 시에는 ML 허용하지 않음 (48Hz 고정)
        
        elif 40.0 <= t6_temp < 42.0:  # 저온 범위
            # 이전 주파수 기준으로 감소
            er_freq = max(self.freq_min, self.prev_er_freq - 2.0)
            applied_rules.append("S4_T6_LOW")
            reason_parts.append(f"저온 (T6={t6_temp:.1f}°C) → -2Hz (현재 {self.prev_er_freq:.0f}Hz → {er_freq:.0f}Hz)")
            safety_override = True  # ML 무시
        
        elif t6_temp < 40.0:  # 매우 낮음
            # 이전 주파수 기준으로 감소
            er_freq = max(self.freq_min, self.prev_er_freq - 4.0)
            applied_rules.append("S4_T6_VERY_LOW")
            reason_parts.append(f"매우 낮음 (T6={t6_temp:.1f}°C) → -4Hz (현재 {self.prev_er_freq:.0f}Hz → {er_freq:.0f}Hz)")
            safety_override = True  # ML 무시
        
        # 안전 계층에서 처리되었으면 즉시 반환
        if safety_override:
            # 이전 값 업데이트 (다음 사이클을 위해)
            self.prev_sw_freq = sw_freq
            self.prev_fw_freq = fw_freq
            self.prev_er_freq = er_freq
            
            return RuleDecision(
                sw_pump_freq=sw_freq,
                fw_pump_freq=fw_freq,
                er_fan_freq=er_freq,
                applied_rules=applied_rules,
                reason=" | ".join(reason_parts),
                safety_override=True,
                ml_prediction_used=ml_used
            )
        
        # ===================================================================
        # 2️⃣ ML Optimization Layer (정상 범위에서 최적화)
        # ===================================================================
        # ML 예측이 없으면 기본 규칙 기반 계산
        if not ml_prediction:
            sw_freq, fw_freq, er_freq = self._compute_baseline_frequencies(
                temperatures, engine_load
            )
            applied_rules.append("BASELINE_RULES")
        
        # ===================================================================
        # 3️⃣ Rule-based Fine-tuning Layer (미세 조정)
        # ===================================================================
        
        # Rule R1: T5 온도 기반 SW 펌프 조정
        t5_temp = temperatures.get('T5', 35.0)
        t5_error = t5_temp - self.t5_target
        
        if t5_error > 2.0:  # T5 > 37°C
            sw_freq = min(self.freq_max, sw_freq + 4.0)
            applied_rules.append("R1_T5_HIGH")
            reason_parts.append(f"T5={t5_temp:.1f}°C 높음 → SW 펌프 +4Hz")
        elif t5_error > 1.0:  # T5 > 36°C
            sw_freq = min(self.freq_max, sw_freq + 2.0)
            applied_rules.append("R1_T5_MODERATE")
            reason_parts.append(f"T5={t5_temp:.1f}°C 약간 높음 → SW 펌프 +2Hz")
        elif t5_error < -1.0 and pressure > 1.5:  # T5 < 34°C & 압력 충분
            sw_freq = max(self.freq_min, sw_freq - 2.0)
            applied_rules.append("R1_T5_LOW")
            reason_parts.append(f"T5={t5_temp:.1f}°C 낮음 → SW 펌프 -2Hz (에너지 절감)")
        
        # Rule R2: T4 온도 기반 FW 펌프 조정
        if t4_temp > 45.0:
            fw_freq = min(self.freq_max, fw_freq + 3.0)
            applied_rules.append("R2_T4_HIGH")
            reason_parts.append(f"T4={t4_temp:.1f}°C 높음 → FW 펌프 +3Hz")
        elif t4_temp > 43.0:
            fw_freq = min(self.freq_max, fw_freq + 1.5)
            applied_rules.append("R2_T4_MODERATE")
            reason_parts.append(f"T4={t4_temp:.1f}°C 약간 높음 → FW 펌프 +1.5Hz")
        elif t4_temp < 40.0:
            fw_freq = max(self.freq_min, fw_freq - 2.0)
            applied_rules.append("R2_T4_LOW")
            reason_parts.append(f"T4={t4_temp:.1f}°C 낮음 → FW 펌프 -2Hz")
        
        # Rule R3: (T6 제어는 Safety Layer S4로 이동됨)
        
        # Rule R4: 엔진 부하 기반 보정
        load_category = self._get_load_category(engine_load)
        
        if load_category == LoadCategory.HIGH:  # 70-100%
            correction = 1.1  # 10% 증속
            sw_freq = min(self.freq_max, sw_freq * correction)
            fw_freq = min(self.freq_max, fw_freq * correction)
            er_freq = min(self.freq_max, er_freq * correction)
            applied_rules.append("R4_HIGH_LOAD")
            reason_parts.append(f"고부하 ({engine_load:.0f}%) → 10% 증속")
        elif load_category == LoadCategory.LOW:  # 0-30%
            correction = 0.95  # 5% 감속
            sw_freq = max(self.freq_min, sw_freq * correction)
            fw_freq = max(self.freq_min, fw_freq * correction)
            er_freq = max(self.freq_min, er_freq * correction)
            applied_rules.append("R4_LOW_LOAD")
            reason_parts.append(f"저부하 ({engine_load:.0f}%) → 5% 감속")
        
        # Rule R5: 해수 온도 기반 보정
        t1_temp = temperatures.get('T1', 28.0)
        sw_category = self._get_seawater_category(t1_temp)
        
        if sw_category == SeawaterCategory.TROPICAL:  # > 28°C
            correction = 1.05  # 5% 증속
            sw_freq = min(self.freq_max, sw_freq * correction)
            applied_rules.append("R5_TROPICAL")
            reason_parts.append(f"열대 해역 (T1={t1_temp:.1f}°C) → 5% 증속")
        elif sw_category == SeawaterCategory.POLAR:  # < 15°C
            correction = 0.95  # 5% 감속
            sw_freq = max(self.freq_min, sw_freq * correction)
            applied_rules.append("R5_POLAR")
            reason_parts.append(f"극지 해역 (T1={t1_temp:.1f}°C) → 5% 감속")
        
        # Rule R6: 히스테리시스 적용 (떨림 방지)
        sw_freq = self._apply_hysteresis(sw_freq, self.prev_sw_freq)
        fw_freq = self._apply_hysteresis(fw_freq, self.prev_fw_freq)
        er_freq = self._apply_hysteresis(er_freq, self.prev_er_freq)
        
        # 이전 값 업데이트
        self.prev_sw_freq = sw_freq
        self.prev_fw_freq = fw_freq
        self.prev_er_freq = er_freq
        
        # 기본 메시지 (규칙이 적용되지 않은 경우)
        if not reason_parts:
            reason_parts.append(f"[OK] 정상 운전 (T5={t5_temp:.1f}°C, T6={t6_temp:.1f}°C)")
        
        return RuleDecision(
            sw_pump_freq=sw_freq,
            fw_pump_freq=fw_freq,
            er_fan_freq=er_freq,
            applied_rules=applied_rules,
            reason=" | ".join(reason_parts),
            safety_override=False,
            ml_prediction_used=ml_used
        )
    
    def _compute_baseline_frequencies(
        self,
        temperatures: Dict[str, float],
        engine_load: float
    ) -> Tuple[float, float, float]:
        """
        ML 예측이 없을 때 기본 주파수 계산
        
        Returns:
            (sw_freq, fw_freq, er_freq)
        """
        # 엔진 부하 기반 기본 주파수
        if engine_load > 80:
            base_freq = 52.0
        elif engine_load > 50:
            base_freq = 48.0
        else:
            base_freq = 45.0
        
        # T5 기반 SW 펌프
        t5 = temperatures.get('T5', 35.0)
        if t5 > 36.0:
            sw_freq = min(self.freq_max, base_freq + 4.0)
        elif t5 > 35.5:
            sw_freq = base_freq + 2.0
        elif t5 < 34.0:
            sw_freq = max(self.freq_min, base_freq - 2.0)
        else:
            sw_freq = base_freq
        
        # T4 기반 FW 펌프
        t4 = temperatures.get('T4', 45.0)
        if t4 > 46.0:
            fw_freq = min(self.freq_max, base_freq + 4.0)
        elif t4 > 44.0:
            fw_freq = base_freq + 2.0
        elif t4 < 40.0:
            fw_freq = max(self.freq_min, base_freq - 2.0)
        else:
            fw_freq = base_freq
        
        # T6 기반 E/R 팬
        t6 = temperatures.get('T6', 43.0)
        if t6 > 45.0:
            er_freq = min(self.freq_max, base_freq + 6.0)
        elif t6 > 44.0:
            er_freq = base_freq + 4.0
        elif t6 < 41.0:
            er_freq = max(self.freq_min, base_freq - 2.0)
        else:
            er_freq = base_freq
        
        return sw_freq, fw_freq, er_freq
    
    def _get_load_category(self, engine_load: float) -> LoadCategory:
        """엔진 부하 구간 분류"""
        if engine_load < 30.0:
            return LoadCategory.LOW
        elif engine_load < 70.0:
            return LoadCategory.MEDIUM
        else:
            return LoadCategory.HIGH
    
    def _get_seawater_category(self, seawater_temp: float) -> SeawaterCategory:
        """해수 온도 구간 분류"""
        if seawater_temp > 28.0:
            return SeawaterCategory.TROPICAL
        elif seawater_temp < 15.0:
            return SeawaterCategory.POLAR
        else:
            return SeawaterCategory.TEMPERATE
    
    def _apply_hysteresis(self, new_freq: float, prev_freq: float) -> float:
        """
        히스테리시스 적용 (떨림 방지)
        
        변화량이 임계값 이하면 이전 값 유지
        """
        if abs(new_freq - prev_freq) < self.hysteresis_freq:
            return prev_freq
        return new_freq
    
    def reset(self):
        """제어기 리셋"""
        self.prev_sw_freq = 48.0
        self.prev_fw_freq = 48.0
        self.prev_er_freq = 48.0
    
    def get_rule_info(self) -> Dict:
        """규칙 정보 반환"""
        return {
            "controller_type": "Rule-based AI",
            "safety_rules": [
                "S1: Cooler 과열 보호 (T2/T3 < 49°C)",
                "S2: FW 입구 온도 한계 (T4 < 48°C)",
                "S3: 압력 제약 (PX1 ≥ 1.0 bar)",
                "S4: T6 온도 제어 (>45°C 긴급, 42~44°C 정상, <42°C 저온) - ML보다 우선"
            ],
            "optimization_rules": [
                "R1: T5 온도 기반 SW 펌프 조정",
                "R2: T4 온도 기반 FW 펌프 조정",
                "R4: 엔진 부하 기반 보정",
                "R5: 해수 온도 기반 보정",
                "R6: 히스테리시스 (떨림 방지)"
            ],
            "current_state": {
                "prev_sw_freq": self.prev_sw_freq,
                "prev_fw_freq": self.prev_fw_freq,
                "prev_er_freq": self.prev_er_freq
            }
        }


def create_rule_based_controller() -> RuleBasedController:
    """Rule-based 제어기 생성"""
    return RuleBasedController()

