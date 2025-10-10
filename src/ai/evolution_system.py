"""
ESS AI System - 3단계 진화형 AI 시스템
Evolution Stage 1 (0-6개월): 규칙 기반 + 온도 추세 예측
Evolution Stage 2 (6-12개월): 패턴 학습 시작
Evolution Stage 3 (12개월+): 적응형 학습
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
from pathlib import Path


class EvolutionStage(Enum):
    """AI 진화 단계"""
    STAGE_1_RULE_BASED = 1  # 0-6개월: 80% 규칙 + 20% ML
    STAGE_2_PATTERN_LEARNING = 2  # 6-12개월: 70% 규칙 + 30% ML
    STAGE_3_ADAPTIVE = 3  # 12개월+: 60% 규칙 + 40% ML


class LearningStatus(Enum):
    """학습 상태"""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class EvolutionConfig:
    """진화 시스템 설정"""
    # Stage 1: 규칙 기반 제어
    stage1_rule_weight: float = 0.8
    stage1_ml_weight: float = 0.2
    stage1_duration_months: int = 6

    # Stage 2: 패턴 학습
    stage2_rule_weight: float = 0.7
    stage2_ml_weight: float = 0.3
    stage2_duration_months: int = 6

    # Stage 3: 적응형 학습
    stage3_rule_weight: float = 0.6
    stage3_ml_weight: float = 0.4

    # 학습 시작 조건
    min_same_condition_count: int = 30
    min_continuous_months: int = 3
    min_scenario_samples: int = 50

    # 배치 학습 스케줄
    batch_learning_days: List[str] = field(default_factory=lambda: ["Wednesday", "Sunday"])
    batch_learning_time: str = "02:00"
    batch_learning_duration_hours: int = 2


@dataclass
class LearningCondition:
    """학습 시작 조건"""
    same_condition_count: int = 0
    continuous_operation_months: float = 0.0
    scenario_samples: Dict[str, int] = field(default_factory=dict)
    last_safety_incident: Optional[datetime] = None
    consecutive_efficiency_drop_days: int = 0
    sensor_error_detected: bool = False

    def can_start_learning(self, config: EvolutionConfig) -> Tuple[bool, str]:
        """학습 시작 가능 여부"""
        reasons = []

        if self.same_condition_count < config.min_same_condition_count:
            reasons.append(f"동일 조건 누적 부족: {self.same_condition_count}/{config.min_same_condition_count}")

        if self.continuous_operation_months < config.min_continuous_months:
            reasons.append(f"연속 운항 기간 부족: {self.continuous_operation_months:.1f}/{config.min_continuous_months}개월")

        insufficient_scenarios = []
        for scenario, count in self.scenario_samples.items():
            if count < config.min_scenario_samples:
                insufficient_scenarios.append(f"{scenario}({count}/{config.min_scenario_samples})")

        if insufficient_scenarios:
            reasons.append(f"시나리오 샘플 부족: {', '.join(insufficient_scenarios)}")

        if self.last_safety_incident is not None:
            days_since_incident = (datetime.now() - self.last_safety_incident).days
            if days_since_incident < 7:
                reasons.append(f"최근 안전 사고 발생 ({days_since_incident}일 전)")

        if self.consecutive_efficiency_drop_days >= 3:
            reasons.append(f"연속 효율 저하: {self.consecutive_efficiency_drop_days}일")

        if self.sensor_error_detected:
            reasons.append("센서 오류 감지")

        if len(reasons) == 0:
            return True, "학습 시작 조건 충족"
        else:
            return False, "; ".join(reasons)

    def should_stop_learning(self) -> Tuple[bool, str]:
        """학습 중단 필요 여부"""
        if self.last_safety_incident is not None:
            days_since = (datetime.now() - self.last_safety_incident).days
            if days_since < 1:
                return True, "안전 사고 발생"

        if self.consecutive_efficiency_drop_days >= 3:
            return True, f"3일 연속 효율 저하"

        if self.sensor_error_detected:
            return True, "센서 오류 감지"

        return False, ""


@dataclass
class AIEvolutionSystem:
    """AI 진화 시스템"""
    config: EvolutionConfig
    system_start_date: datetime
    current_stage: EvolutionStage = EvolutionStage.STAGE_1_RULE_BASED
    learning_status: LearningStatus = LearningStatus.ACTIVE
    learning_condition: LearningCondition = field(default_factory=LearningCondition)

    # 모델 정보
    temperature_prediction_model_size: float = 0.5  # MB
    optimization_model_size: float = 1.5  # MB
    total_scenario_db_size: float = 0.0  # MB

    # 학습 이력
    last_batch_learning: Optional[datetime] = None
    learning_count: int = 0
    model_updates: List[datetime] = field(default_factory=list)

    def get_current_stage(self) -> EvolutionStage:
        """현재 진화 단계 확인"""
        months_elapsed = (datetime.now() - self.system_start_date).days / 30.0

        if months_elapsed < self.config.stage1_duration_months:
            return EvolutionStage.STAGE_1_RULE_BASED
        elif months_elapsed < (self.config.stage1_duration_months + self.config.stage2_duration_months):
            return EvolutionStage.STAGE_2_PATTERN_LEARNING
        else:
            return EvolutionStage.STAGE_3_ADAPTIVE

    def get_control_weights(self) -> Tuple[float, float]:
        """
        현재 단계의 제어 가중치 반환
        Returns: (rule_weight, ml_weight)
        """
        stage = self.get_current_stage()

        if stage == EvolutionStage.STAGE_1_RULE_BASED:
            return self.config.stage1_rule_weight, self.config.stage1_ml_weight
        elif stage == EvolutionStage.STAGE_2_PATTERN_LEARNING:
            return self.config.stage2_rule_weight, self.config.stage2_ml_weight
        else:
            return self.config.stage3_rule_weight, self.config.stage3_ml_weight

    def is_batch_learning_time(self, current_time: datetime) -> bool:
        """배치 학습 시간 여부"""
        day_name = current_time.strftime("%A")
        if day_name not in self.config.batch_learning_days:
            return False

        # 02:00-04:00 시간대 확인
        learning_hour = int(self.config.batch_learning_time.split(":")[0])
        current_hour = current_time.hour

        return learning_hour <= current_hour < (learning_hour + self.config.batch_learning_duration_hours)

    def can_start_learning(self) -> Tuple[bool, str]:
        """학습 시작 가능 여부"""
        if self.learning_status == LearningStatus.STOPPED:
            return False, "학습 중단 상태"

        stage = self.get_current_stage()
        if stage == EvolutionStage.STAGE_1_RULE_BASED:
            # Stage 1에서는 온도 예측만 수행, 본격적인 학습은 Stage 2부터
            return False, "Stage 1: 규칙 기반 제어 단계 (본격적 학습 전)"

        return self.learning_condition.can_start_learning(self.config)

    def check_learning_stop_condition(self) -> Tuple[bool, str]:
        """학습 중단 조건 확인"""
        return self.learning_condition.should_stop_learning()

    def update_learning_status(self) -> None:
        """학습 상태 업데이트"""
        should_stop, reason = self.check_learning_stop_condition()

        if should_stop:
            self.learning_status = LearningStatus.STOPPED
            print(f"⚠️ 학습 중단: {reason}")
        else:
            can_learn, message = self.can_start_learning()
            if can_learn and self.learning_status == LearningStatus.PAUSED:
                self.learning_status = LearningStatus.ACTIVE
                print(f"✅ 학습 재개: {message}")

    def execute_batch_learning(self) -> Dict:
        """
        배치 학습 실행
        수요일, 일요일 심야 02:00-04:00
        """
        stage = self.get_current_stage()
        learning_result = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage.name,
            "status": "success",
            "tasks": []
        }

        # 02:00-02:30: 데이터 정리
        learning_result["tasks"].append({
            "name": "데이터 정리",
            "time": "02:00-02:30",
            "status": "pending"
        })

        # 02:30-03:30: 모델 업데이트
        if stage == EvolutionStage.STAGE_2_PATTERN_LEARNING:
            learning_result["tasks"].append({
                "name": "Polynomial Regression 업데이트",
                "time": "02:30-03:00",
                "model_size_mb": self.temperature_prediction_model_size,
                "status": "pending"
            })
            learning_result["tasks"].append({
                "name": "Random Forest 학습",
                "time": "03:00-03:30",
                "model_size_mb": self.optimization_model_size,
                "status": "pending"
            })
        elif stage == EvolutionStage.STAGE_3_ADAPTIVE:
            learning_result["tasks"].append({
                "name": "적응형 모델 최적화",
                "time": "02:30-03:30",
                "status": "pending"
            })

        # 03:30-04:00: 시나리오 DB 업데이트
        learning_result["tasks"].append({
            "name": "시나리오 DB 업데이트",
            "time": "03:30-04:00",
            "db_size_mb": self.total_scenario_db_size,
            "status": "pending"
        })

        self.last_batch_learning = datetime.now()
        self.learning_count += 1
        self.model_updates.append(datetime.now())

        return learning_result

    def get_stage_description(self) -> str:
        """현재 단계 설명"""
        stage = self.get_current_stage()
        rule_weight, ml_weight = self.get_control_weights()

        descriptions = {
            EvolutionStage.STAGE_1_RULE_BASED: f"규칙 기반 제어 ({rule_weight*100:.0f}% 규칙 + {ml_weight*100:.0f}% ML)\n"
                                                f"- Polynomial Regression 온도 예측\n"
                                                f"- 선제적 대응 제어",
            EvolutionStage.STAGE_2_PATTERN_LEARNING: f"패턴 학습 시작 ({rule_weight*100:.0f}% 규칙 + {ml_weight*100:.0f}% ML)\n"
                                                      f"- Random Forest 최적화\n"
                                                      f"- 주 2회 배치 학습",
            EvolutionStage.STAGE_3_ADAPTIVE: f"적응형 학습 ({rule_weight*100:.0f}% 규칙 + {ml_weight*100:.0f}% ML)\n"
                                              f"- 선박별 맞춤형 최적화\n"
                                              f"- 시나리오 DB 기반 제어"
        }

        return descriptions.get(stage, "Unknown stage")

    def get_system_info(self) -> Dict:
        """시스템 정보"""
        months_elapsed = (datetime.now() - self.system_start_date).days / 30.0
        stage = self.get_current_stage()
        rule_weight, ml_weight = self.get_control_weights()

        return {
            "system_start_date": self.system_start_date.isoformat(),
            "months_elapsed": round(months_elapsed, 1),
            "current_stage": stage.name,
            "stage_number": stage.value,
            "control_weights": {
                "rule_based": f"{rule_weight*100:.0f}%",
                "machine_learning": f"{ml_weight*100:.0f}%"
            },
            "learning_status": self.learning_status.value,
            "learning_count": self.learning_count,
            "last_batch_learning": self.last_batch_learning.isoformat() if self.last_batch_learning else None,
            "model_sizes": {
                "temperature_prediction_mb": self.temperature_prediction_model_size,
                "optimization_mb": self.optimization_model_size,
                "scenario_db_mb": self.total_scenario_db_size,
                "total_mb": self.temperature_prediction_model_size + self.optimization_model_size + self.total_scenario_db_size
            },
            "learning_conditions": {
                "same_condition_count": self.learning_condition.same_condition_count,
                "continuous_operation_months": round(self.learning_condition.continuous_operation_months, 1),
                "scenario_samples": self.learning_condition.scenario_samples,
                "can_start_learning": self.can_start_learning()[0]
            }
        }


def create_default_evolution_system(installation_date: Optional[datetime] = None) -> AIEvolutionSystem:
    """기본 진화 시스템 생성"""
    if installation_date is None:
        installation_date = datetime.now()

    config = EvolutionConfig()
    system = AIEvolutionSystem(
        config=config,
        system_start_date=installation_date
    )

    # 초기 시나리오 샘플 카운트 설정
    system.learning_condition.scenario_samples = {
        "tropical_high_load": 0,
        "tropical_low_load": 0,
        "temperate_high_load": 0,
        "temperate_low_load": 0,
        "polar_high_load": 0,
        "polar_low_load": 0
    }

    return system
