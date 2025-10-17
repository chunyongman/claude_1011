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
        
        # 온도 목표값 (V3 설정)
        self.t5_target = 35.0
        self.t6_target = 43.0     # 변경: 41 → 43°C (실용적 운영 온도)
        
        # 안전 임계값
        self.t2_t3_limit = 49.0  # Cooler 보호
        self.t4_limit = 48.0     # FW 입구 한계
        self.t6_emergency = 47.0 # E/R 긴급 온도 (변경: 45 → 47°C, 갭 4.0°C 유지)
        self.px1_min = 1.0       # 최소 압력
        
        # 피드백 제어 파라미터
        self.kp_t6 = 3.0         # T6 비례 게인
        self.max_change_per_cycle = 5.0  # 최대 변화율 (Hz/cycle)
        
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
        
        # Rule S4: T5 극한 온도 안전 제어 (극고온/극저온만 개입)
        # 일반 범위(30~40°C)는 ML이 예측 제어 수행
        t5_temp = temperatures.get('T5', 35.0)
        
        if t5_temp > 40.0:  # 극고온 (40°C 초과) - 긴급 상황
            sw_freq = self.freq_max  # 강제 60Hz
            safety_override = True
            applied_rules.append("S4_T5_EMERGENCY_HIGH")
            reason_parts.append(f"[EMERGENCY] T5={t5_temp:.1f}°C > 40°C → 강제 60Hz")
        
        elif t5_temp < 30.0:  # 극저온 (30°C 미만) - 긴급 상황
            sw_freq = self.freq_min  # 강제 40Hz
            safety_override = True
            applied_rules.append("S4_T5_EMERGENCY_LOW")
            reason_parts.append(f"[EMERGENCY] T5={t5_temp:.1f}°C < 30°C → 강제 40Hz")
        
        # 일반 범위 (30~40°C): ML이 예측 제어 수행 → Safety Layer 통과
        
        # Rule S6: T4 온도 기반 FW 펌프 제어 - 극한 에너지 절감
        # T4 < 46°C: 무조건 40Hz (최대 에너지 절감)
        # 46~47°C: 42Hz (안전 마진)
        # 47~48°C: 46Hz (대기)
        # ≥ 48°C: S2에서 60Hz 강제
        
        # ML 예측값 가져오기 (5분 후 T4 온도 예측)
        if ml_prediction and hasattr(ml_prediction, 't4_pred_5min'):
            t4_pred_5min = ml_prediction.t4_pred_5min
        else:
            t4_pred_5min = t4_temp
        
        # Phase 1: 에너지 절감 최우선 (T4 < 46°C → 무조건 40Hz)
        if t4_temp < 46.0 and t4_pred_5min < 48.0:
            # 무조건 40Hz 강제 (ML 무시)
            if self.prev_fw_freq > 40.5:
                fw_freq = max(40.0, self.prev_fw_freq - 3.0)  # -3Hz/cycle
                applied_rules.append("S6_T4_ENERGY_SAVE")
                reason_parts.append(f"[절감] T4={t4_temp:.1f}°C < 46°C → 40Hz 수렴 (현재 {fw_freq:.0f}Hz)")
            else:
                fw_freq = 40.0  # 40Hz 강제
                applied_rules.append("S6_T4_ENERGY_OPTIMAL")
                reason_parts.append(f"[최적] T4={t4_temp:.1f}°C < 46°C → 40Hz 유지")
            safety_override = True
        
        # Phase 1-2: 안전 마진 (46~47°C → 42Hz)
        elif 46.0 <= t4_temp < 47.0 and t4_pred_5min < 48.0:
            if abs(self.prev_fw_freq - 42.0) > 0.5:
                if self.prev_fw_freq > 42.0:
                    fw_freq = max(42.0, self.prev_fw_freq - 2.0)
                else:
                    fw_freq = min(42.0, self.prev_fw_freq + 2.0)
                applied_rules.append("S6_T4_SAFE_MARGIN")
                reason_parts.append(f"[안전] T4={t4_temp:.1f}°C (46~47°C) → 42Hz 수렴 ({fw_freq:.0f}Hz)")
            else:
                fw_freq = 42.0
                applied_rules.append("S6_T4_SAFE_HOLD")
                reason_parts.append(f"[안전] T4={t4_temp:.1f}°C → 42Hz 유지")
            safety_override = True
        
        # Phase 1-3: 대기 (47~48°C → 46Hz)
        elif 47.0 <= t4_temp < 48.0 and t4_pred_5min < 48.0:
            if abs(self.prev_fw_freq - 46.0) > 0.5:
                if self.prev_fw_freq > 46.0:
                    fw_freq = max(46.0, self.prev_fw_freq - 1.0)
                else:
                    fw_freq = min(46.0, self.prev_fw_freq + 1.0)
                applied_rules.append("S6_T4_STANDBY")
                reason_parts.append(f"[대기] T4={t4_temp:.1f}°C (47~48°C) → 46Hz 수렴 ({fw_freq:.0f}Hz)")
            else:
                fw_freq = 46.0
                applied_rules.append("S6_T4_STANDBY_HOLD")
                reason_parts.append(f"[대기] T4={t4_temp:.1f}°C → 46Hz 유지")
            safety_override = True
        
        # Phase 2: 선제 대응 (현재 T4 < 48°C BUT ML 예측 ≥ 48°C)
        elif t4_temp < 48.0 and t4_pred_5min >= 48.0:
            overshoot = t4_pred_5min - 48.0
            if overshoot >= 2.0:
                target_freq = 56.0
                increase_rate = 6.0
                urgency = "긴급"
            elif overshoot >= 1.0:
                target_freq = 52.0
                increase_rate = 4.0
                urgency = "강력"
            else:
                target_freq = 50.0
                increase_rate = 3.0
                urgency = "일반"
            
            if self.prev_fw_freq < target_freq - 0.5:
                fw_freq = min(target_freq, self.prev_fw_freq + increase_rate)
                applied_rules.append("S6_T4_PREDICTIVE")
                reason_parts.append(f"[선제 {urgency}] 예측 T4={t4_pred_5min:.1f}°C ≥ 48°C → {fw_freq:.0f}Hz 증속")
            else:
                fw_freq = target_freq
                applied_rules.append("S6_T4_PREDICTIVE_READY")
                reason_parts.append(f"[선제 대기] 예측 T4={t4_pred_5min:.1f}°C → {fw_freq:.0f}Hz")
            safety_override = True
        
        # 극저온 보호 (T4 < 38°C)
        elif t4_temp < 38.0:
            fw_freq = self.freq_min  # 강제 40Hz
            safety_override = True
            applied_rules.append("S6_T4_EMERGENCY_LOW")
            reason_parts.append(f"[EMERGENCY] T4={t4_temp:.1f}°C < 38°C → 강제 40Hz")
        
        # 일반 범위: Safety Layer 통과 (ML이 제어)
        
        # Rule S5: T6 온도 피드백 제어 (Safety Layer + ML 통합)
        # 목표: 43°C, 극한: 47°C, 갭: 4.0°C
        t6_temp = temperatures.get('T6', 43.0)
        
        # ML 예측값 가져오기 (5분 후 T6 온도 예측)
        if ml_prediction and hasattr(ml_prediction, 't6_pred_5min'):
            t6_pred_5min = ml_prediction.t6_pred_5min
        else:
            t6_pred_5min = t6_temp
        
        # === Safety Layer: 극한 온도 강제 제어 ===
        if t6_temp >= self.t6_emergency:  # 47°C 이상
            er_freq = self.freq_max  # 강제 60Hz
            safety_override = True
            applied_rules.append("S5_T6_EMERGENCY")
            reason_parts.append(f"[EMERGENCY] T6={t6_temp:.1f}°C ≥ {self.t6_emergency}°C → 강제 60Hz")
        
        else:
            # === 피드백 제어: 온도 오차 기반 주파수 조정 ===
            
            # 1. 현재 온도 오차
            error_current = t6_temp - self.t6_target
            
            # 2. 예측 온도 오차
            error_predicted = t6_pred_5min - self.t6_target
            
            # 3. 가중치 동적 조정
            if abs(error_predicted) > 2.0:
                # 큰 변화 예측 → 예측 중시
                w_current, w_predicted = 0.2, 0.8
            elif abs(error_current) > 1.0:
                # 현재 이미 벗어남 → 현재 중시
                w_current, w_predicted = 0.6, 0.4
            else:
                # 정상 범위 → 균형
                w_current, w_predicted = 0.4, 0.6
            
            # 4. 통합 오차
            error_combined = w_current * error_current + w_predicted * error_predicted
            
            # 5. 비례 제어 (P-Control)
            adjustment = self.kp_t6 * error_combined
            
            # 6. 변화율 제한
            adjustment = max(-self.max_change_per_cycle, min(self.max_change_per_cycle, adjustment))
            
            # 7. 새 주파수 계산
            er_freq = self.prev_er_freq + adjustment
            er_freq = max(self.freq_min, min(self.freq_max, er_freq))
            
            # 8. 제어 모드 결정
            if abs(error_combined) < 0.3:
                applied_rules.append("S5_T6_STABLE")
                reason_parts.append(f"[안정] T6={t6_temp:.1f}°C (목표 {self.t6_target}°C) → {er_freq:.0f}Hz")
                # 40Hz에 도달하면 대수 제어 허용
                if er_freq <= self.freq_min:
                    self.prev_sw_freq = sw_freq
                    self.prev_fw_freq = fw_freq
                    self.prev_er_freq = er_freq
                    safety_override = False
                else:
                    safety_override = True
            elif error_combined > 0:
                applied_rules.append("S5_T6_COOLING")
                reason_parts.append(f"[냉각] T6={t6_temp:.1f}°C → 예측 {t6_pred_5min:.1f}°C | {adjustment:+.1f}Hz → {er_freq:.0f}Hz")
                safety_override = True
            else:
                applied_rules.append("S5_T6_ENERGY_SAVING")
                reason_parts.append(f"[절감] T6={t6_temp:.1f}°C → 예측 {t6_pred_5min:.1f}°C | {adjustment:+.1f}Hz → {er_freq:.0f}Hz")
                # 40Hz에 도달하면 대수 제어 허용
                if er_freq <= self.freq_min:
                    self.prev_sw_freq = sw_freq
                    self.prev_fw_freq = fw_freq
                    self.prev_er_freq = er_freq
                    safety_override = False
                else:
                    safety_override = True
        
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
        
        # Rule R1: T5 온도 기반 SW 펌프 강화 보정 (ML 결과에 추가 적용)
        # ML이 예측한 주파수에 현재 온도 기반 보정을 추가하여 목표 달성 가속
        t5_temp = temperatures.get('T5', 35.0)
        
        if t5_temp > 38.0:  # 고온 (38~40°C) - 60Hz 빠른 수렴
            correction = min(60.0 - sw_freq, 6.0)  # 최대 +6Hz
            sw_freq = min(self.freq_max, sw_freq + correction)
            applied_rules.append("R1_T5_HIGH_BOOST")
            reason_parts.append(f"T5={t5_temp:.1f}°C 고온 → ML+{correction:.0f}Hz (60Hz 가속)")
        
        elif t5_temp > 36.0:  # 약간 높음 (36~38°C)
            correction = min(60.0 - sw_freq, 4.0)  # 최대 +4Hz
            sw_freq = min(self.freq_max, sw_freq + correction)
            applied_rules.append("R1_T5_MODERATE_HIGH")
            reason_parts.append(f"T5={t5_temp:.1f}°C 약간 높음 → ML+{correction:.0f}Hz")
        
        elif 34.0 <= t5_temp <= 36.0:  # 정상 범위 (34~36°C)
            # ML 결과 그대로 사용 (미세 조정만)
            if abs(sw_freq - 48.0) > 0.5:
                applied_rules.append("R1_T5_NORMAL_ML")
                reason_parts.append(f"T5={t5_temp:.1f}°C 정상 → ML 주도 ({sw_freq:.0f}Hz)")
        
        elif t5_temp < 32.0:  # 저온 (30~32°C) - 40Hz 빠른 수렴
            correction = min(sw_freq - 40.0, 6.0)  # 최대 -6Hz
            sw_freq = max(self.freq_min, sw_freq - correction)
            applied_rules.append("R1_T5_LOW_REDUCE")
            reason_parts.append(f"T5={t5_temp:.1f}°C 저온 → ML-{correction:.0f}Hz (40Hz 가속)")
        
        elif t5_temp < 34.0:  # 약간 낮음 (32~34°C)
            correction = min(sw_freq - 40.0, 3.0)  # 최대 -3Hz
            sw_freq = max(self.freq_min, sw_freq - correction)
            applied_rules.append("R1_T5_MODERATE_LOW")
            reason_parts.append(f"T5={t5_temp:.1f}°C 약간 낮음 → ML-{correction:.0f}Hz")
        
        # Rule R2: (T4 제어는 Safety Layer S6로 완전 이동됨)
        # - T4 < 46°C: 무조건 40Hz (극한 에너지 절감)
        # - 46~47°C: 42Hz (안전 마진)
        # - 47~48°C: 46Hz (대기)
        # - T4 < 48°C & ML 예측 ≥ 48°C: 선제 대응 (50/52/56Hz)
        # - T4 ≥ 48°C: S2에서 60Hz 강제
        
        # Rule R3: (T6 제어는 Safety Layer S5로 이동됨)
        
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
                "S2: FW 입구 온도 한계 (T4 ≥ 48°C 긴급 고온)",
                "S3: 압력 제약 (PX1 ≥ 1.0 bar)",
                "S4: T5 극한 온도 보호 (>40°C 긴급 고온, <30°C 긴급 저온만 개입)",
                "S5: T6 온도 제어 (>45°C 긴급, 44~45°C 고온, 42~44°C 정상, <42°C 저온) - ML보다 우선",
                "S6: T4 극한 온도 보호 (<38°C 긴급 저온만 개입)"
            ],
            "ml_optimization": [
                "ML Predictive Control: 30초 후 온도 예측 기반 선제적 주파수 조정 (T5/T4 주도)"
            ],
            "optimization_rules": [
                "R1: T5 온도 기반 SW 펌프 강화 보정 (ML 결과 + 현재 온도 보정으로 60Hz/40Hz 가속 달성)",
                "R2: T4 온도 기반 FW 펌프 3단계 제어 (극한 에너지 절감)",
                "  ├─ Phase 1: 에너지 절감 모드 (T4<48°C & 예측<48°C → 최대한 40Hz 운전)",
                "  ├─ Phase 2: 선제 대응 모드 (예측≥48°C → 온도 상승 억제 증속)",
                "  └─ Phase 3: 긴급 모드 (T4≥48°C → Safety Layer S2 강제 60Hz)",
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

