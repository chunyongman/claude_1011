"""
성과 기반 파라미터 자동 튜닝
예측 정확도 및 제어 성과에 따라 파라미터 자동 조정
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np


@dataclass
class PerformanceMetrics:
    """성과 지표"""
    timestamp: datetime

    # 예측 정확도
    prediction_accuracy: float  # 0-100 (%)
    t5_prediction_error: float  # °C
    t6_prediction_error: float  # °C

    # 제어 성과
    t5_control_error: float  # |T5 - 35.0|
    t6_control_error: float  # |T6 - 43.0|
    energy_savings: float  # %

    # 종합 점수
    overall_score: float  # 0-100


@dataclass
class TuningParameters:
    """튜닝 파라미터"""
    # 예측 가중치
    prediction_weight_acceleration: float  # 가속시 예측 가중치
    prediction_weight_steady: float  # 정속시 예측 가중치
    prediction_weight_deceleration: float  # 감속시 예측 가중치

    # 온도 임계값
    temp_rise_threshold: float  # 온도 상승 임계값 (°C)
    temp_fall_threshold: float  # 온도 하강 임계값 (°C)

    # 제어 공격성
    control_aggressiveness: float  # 0-1 (0=보수적, 1=공격적)

    # PID 게인
    t5_pid_kp: float
    t5_pid_ki: float
    t5_pid_kd: float
    t6_pid_kp: float
    t6_pid_ki: float
    t6_pid_kd: float


class ParameterTuner:
    """
    성과 기반 파라미터 자동 튜닝 시스템

    목표:
    - 예측 정확도에 따라 예측 가중치 조정
    - 제어 성과에 따라 파라미터 최적화
    - 주간 단위 성능 개선 추적
    """

    def __init__(self):
        """초기화"""
        # 초기 파라미터 (보수적 설정)
        self.params = TuningParameters(
            # 예측 가중치
            prediction_weight_acceleration=0.6,
            prediction_weight_steady=0.3,
            prediction_weight_deceleration=0.5,

            # 온도 임계값
            temp_rise_threshold=1.0,
            temp_fall_threshold=-0.5,

            # 제어 공격성
            control_aggressiveness=0.5,

            # PID 게인
            t5_pid_kp=2.0,
            t5_pid_ki=0.1,
            t5_pid_kd=0.5,
            t6_pid_kp=1.5,
            t6_pid_ki=0.08,
            t6_pid_kd=0.4
        )

        # 성과 히스토리
        self.performance_history: List[PerformanceMetrics] = []

        # 튜닝 통계
        self.total_tunings = 0
        self.last_tuning_time: Optional[datetime] = None

        # 주간 성과 추적
        self.weekly_scores: List[float] = []

    def record_performance(
        self,
        prediction_accuracy: float,
        t5_pred_error: float,
        t6_pred_error: float,
        t5_control_error: float,
        t6_control_error: float,
        energy_savings: float
    ):
        """성과 기록"""
        # 종합 점수 계산
        overall_score = self._calculate_overall_score(
            prediction_accuracy, t5_control_error, t6_control_error, energy_savings
        )

        metric = PerformanceMetrics(
            timestamp=datetime.now(),
            prediction_accuracy=prediction_accuracy,
            t5_prediction_error=t5_pred_error,
            t6_prediction_error=t6_pred_error,
            t5_control_error=t5_control_error,
            t6_control_error=t6_control_error,
            energy_savings=energy_savings,
            overall_score=overall_score
        )

        self.performance_history.append(metric)

        # 히스토리 크기 제한 (최근 1000개)
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]

    def _calculate_overall_score(
        self,
        prediction_acc: float,
        t5_error: float,
        t6_error: float,
        energy_savings: float
    ) -> float:
        """
        종합 점수 계산 (0-100)

        가중치:
        - 예측 정확도: 20%
        - T5 제어 정확도: 30%
        - T6 제어 정확도: 30%
        - 에너지 절감: 20%
        """
        # 예측 점수 (80% 이상 목표)
        pred_score = min(100, (prediction_acc / 80.0) * 100)

        # T5 제어 점수 (±0.5°C 목표)
        t5_score = max(0, 100 - abs(t5_error) * 200)

        # T6 제어 점수 (±1.0°C 목표)
        t6_score = max(0, 100 - abs(t6_error) * 100)

        # 에너지 절감 점수 (40-55% 목표)
        if 40 <= energy_savings <= 55:
            energy_score = 100
        elif energy_savings > 55:
            energy_score = max(0, 100 - (energy_savings - 55) * 5)
        else:
            energy_score = max(0, 100 - (40 - energy_savings) * 5)

        # 가중 평균
        overall = (
            pred_score * 0.2 +
            t5_score * 0.3 +
            t6_score * 0.3 +
            energy_score * 0.2
        )

        return overall

    def should_tune(self) -> bool:
        """튜닝 실행 여부 판정"""
        # 최소 100개 데이터 필요
        if len(self.performance_history) < 100:
            return False

        # 주 1회 튜닝 (일요일 심야)
        now = datetime.now()
        if now.weekday() != 6:  # 일요일
            return False

        if now.hour < 2 or now.hour >= 4:  # 02:00-04:00
            return False

        # 이미 이번 주 튜닝했는지 확인
        if self.last_tuning_time is not None:
            if (now - self.last_tuning_time).days < 6:
                return False

        return True

    def tune_parameters(self) -> Dict:
        """
        파라미터 튜닝 실행

        Returns:
            튜닝 결과
        """
        # 최근 7일 데이터
        recent = self._get_recent_metrics(days=7)

        if len(recent) < 50:
            return {'status': 'insufficient_data', 'samples': len(recent)}

        # 평균 성과 계산
        avg_pred_acc = np.mean([m.prediction_accuracy for m in recent])
        avg_t5_error = np.mean([m.t5_control_error for m in recent])
        avg_t6_error = np.mean([m.t6_control_error for m in recent])
        avg_energy = np.mean([m.energy_savings for m in recent])
        avg_score = np.mean([m.overall_score for m in recent])

        # 주간 점수 기록
        self.weekly_scores.append(avg_score)

        # 튜닝 로직
        changes = {}

        # 1. 예측 가중치 조정
        if avg_pred_acc >= 85.0:
            # 예측 정확도 높음 → 가중치 증가
            old_weight = self.params.prediction_weight_acceleration
            self.params.prediction_weight_acceleration = min(0.9, old_weight + 0.05)
            changes['prediction_weight_acceleration'] = f"{old_weight:.2f} → {self.params.prediction_weight_acceleration:.2f}"

        elif avg_pred_acc < 70.0:
            # 예측 정확도 낮음 → 가중치 감소
            old_weight = self.params.prediction_weight_acceleration
            self.params.prediction_weight_acceleration = max(0.3, old_weight - 0.05)
            changes['prediction_weight_acceleration'] = f"{old_weight:.2f} → {self.params.prediction_weight_acceleration:.2f}"

        # 2. 제어 공격성 조정
        if avg_t5_error > 0.5 or avg_t6_error > 1.0:
            # 제어 오차 큼 → 공격성 증가
            old_aggr = self.params.control_aggressiveness
            self.params.control_aggressiveness = min(0.9, old_aggr + 0.1)
            changes['control_aggressiveness'] = f"{old_aggr:.2f} → {self.params.control_aggressiveness:.2f}"

        elif avg_t5_error < 0.2 and avg_t6_error < 0.5:
            # 제어 오차 작음 → 공격성 감소 (에너지 절감 우선)
            old_aggr = self.params.control_aggressiveness
            self.params.control_aggressiveness = max(0.3, old_aggr - 0.05)
            changes['control_aggressiveness'] = f"{old_aggr:.2f} → {self.params.control_aggressiveness:.2f}"

        # 3. PID 게인 미세 조정
        if avg_t5_error > 0.7:
            # T5 오차 큼 → Kp 증가
            old_kp = self.params.t5_pid_kp
            self.params.t5_pid_kp = min(3.0, old_kp * 1.1)
            changes['t5_pid_kp'] = f"{old_kp:.2f} → {self.params.t5_pid_kp:.2f}"

        if avg_t6_error > 1.5:
            # T6 오차 큼 → Kp 증가
            old_kp = self.params.t6_pid_kp
            self.params.t6_pid_kp = min(2.5, old_kp * 1.1)
            changes['t6_pid_kp'] = f"{old_kp:.2f} → {self.params.t6_pid_kp:.2f}"

        # 4. 임계값 조정
        if avg_pred_acc >= 90.0:
            # 예측 매우 정확 → 임계값 낮춤 (더 민감하게)
            old_thresh = self.params.temp_rise_threshold
            self.params.temp_rise_threshold = max(0.5, old_thresh - 0.1)
            changes['temp_rise_threshold'] = f"{old_thresh:.1f} → {self.params.temp_rise_threshold:.1f}"

        # 메타데이터 업데이트
        self.total_tunings += 1
        self.last_tuning_time = datetime.now()

        return {
            'status': 'success',
            'samples': len(recent),
            'avg_score': avg_score,
            'avg_prediction_accuracy': avg_pred_acc,
            'avg_t5_error': avg_t5_error,
            'avg_t6_error': avg_t6_error,
            'avg_energy_savings': avg_energy,
            'changes': changes,
            'total_tunings': self.total_tunings
        }

    def _get_recent_metrics(self, days: int) -> List[PerformanceMetrics]:
        """최근 N일 데이터 추출"""
        cutoff = datetime.now() - timedelta(days=days)
        return [m for m in self.performance_history if m.timestamp > cutoff]

    def get_current_parameters(self) -> TuningParameters:
        """현재 파라미터 반환"""
        return self.params

    def get_tuning_status(self) -> Dict:
        """튜닝 상태"""
        if len(self.performance_history) == 0:
            return {
                'total_samples': 0,
                'total_tunings': 0,
                'last_tuning': None,
                'weekly_improvement': 0.0
            }

        # 주간 개선율 계산
        improvement = 0.0
        if len(self.weekly_scores) >= 2:
            recent_avg = np.mean(self.weekly_scores[-4:])  # 최근 4주
            baseline = self.weekly_scores[0]
            improvement = ((recent_avg - baseline) / baseline) * 100.0

        return {
            'total_samples': len(self.performance_history),
            'total_tunings': self.total_tunings,
            'last_tuning': self.last_tuning_time,
            'weekly_improvement': improvement,
            'current_params': {
                'prediction_weight_accel': self.params.prediction_weight_acceleration,
                'prediction_weight_steady': self.params.prediction_weight_steady,
                'control_aggressiveness': self.params.control_aggressiveness,
                't5_pid_kp': self.params.t5_pid_kp,
                't6_pid_kp': self.params.t6_pid_kp
            }
        }

    def get_weekly_trend(self) -> List[Dict]:
        """주간 성과 추이"""
        return [
            {
                'week': i + 1,
                'score': score,
                'improvement': ((score - self.weekly_scores[0]) / self.weekly_scores[0] * 100)
                              if i > 0 else 0.0
            }
            for i, score in enumerate(self.weekly_scores)
        ]
