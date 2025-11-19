"""
VFD 예방진단 고급 기능
- 트렌드 분석
- 이상 탐지
- 수명 예측
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import deque
import numpy as np
from dataclasses import dataclass, asdict
from src.diagnostics.vfd_monitor import VFDDiagnostic, VFDStatus


@dataclass
class VFDPrediction:
    """VFD 예측 결과"""
    vfd_id: str
    timestamp: str

    # 온도 예측
    predicted_temp_30min: float  # 30분 후 예상 온도
    temp_rise_rate: float  # °C/min
    temp_trend: str  # "rising", "stable", "falling"

    # 수명 예측
    remaining_life_percent: float  # 0-100%
    estimated_days_to_maintenance: int  # 정비까지 예상 일수

    # 이상 점수
    anomaly_score: float  # 0-100 (높을수록 이상)

    # 권고사항
    maintenance_priority: int  # 0=정상, 1=정기점검, 3=1주일내, 5=즉시
    prediction_confidence: float  # 0-1 (예측 신뢰도)

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)


class VFDTrendAnalyzer:
    """VFD 트렌드 분석"""

    def __init__(self, history_size: int = 60):
        """
        초기화

        Args:
            history_size: 히스토리 저장 개수 (기본 60개 = 2분, 2초 주기)
        """
        self.history_size = history_size
        self.histories: Dict[str, deque] = {}  # {vfd_id: deque of VFDDiagnostic}

    def add_diagnostic(self, diagnostic: VFDDiagnostic):
        """진단 데이터 추가"""
        if diagnostic.vfd_id not in self.histories:
            self.histories[diagnostic.vfd_id] = deque(maxlen=self.history_size)

        self.histories[diagnostic.vfd_id].append(diagnostic)

    def analyze_temperature_trend(self, vfd_id: str) -> Dict[str, float]:
        """
        온도 트렌드 분석

        Returns:
            {
                "current_temp": 현재 온도,
                "rise_rate": 상승률 (°C/min),
                "predicted_30min": 30분 후 예측 온도,
                "trend": "rising", "stable", "falling"
            }
        """
        if vfd_id not in self.histories or len(self.histories[vfd_id]) < 5:
            return {
                "current_temp": 0.0,
                "rise_rate": 0.0,
                "predicted_30min": 0.0,
                "trend": "stable"
            }

        history = list(self.histories[vfd_id])
        temps = [d.motor_temperature_c for d in history]
        current_temp = temps[-1]

        # 최근 10개 샘플로 선형 회귀
        if len(temps) >= 10:
            recent_temps = temps[-10:]
            x = np.arange(len(recent_temps))
            # 선형 회귀: y = ax + b
            a, b = np.polyfit(x, recent_temps, 1)
            rise_rate_per_sample = a

            # 샘플 주기 2초 가정 -> 분당 상승률
            rise_rate_per_min = rise_rate_per_sample * 30  # (60초/2초 = 30샘플)

            # 30분 후 예측 (30분 = 900개 샘플)
            predicted_temp = current_temp + (rise_rate_per_sample * 900)
        else:
            # 데이터 부족 시 간단한 차분 방식
            rise_rate_per_min = (temps[-1] - temps[0]) / (len(temps) * 2 / 60)
            predicted_temp = current_temp + (rise_rate_per_min * 30)

        # 트렌드 판단
        if rise_rate_per_min > 0.1:
            trend = "rising"
        elif rise_rate_per_min < -0.1:
            trend = "falling"
        else:
            trend = "stable"

        return {
            "current_temp": round(current_temp, 1),
            "rise_rate": round(rise_rate_per_min, 3),
            "predicted_30min": round(predicted_temp, 1),
            "trend": trend
        }

    def detect_current_anomaly(self, vfd_id: str) -> Dict[str, float]:
        """
        전류 이상 패턴 감지 (표준편차 기반)

        Returns:
            {
                "current_mean": 평균 전류,
                "current_std": 표준편차,
                "current_now": 현재 전류,
                "anomaly_score": 이상 점수 (0-100)
            }
        """
        if vfd_id not in self.histories or len(self.histories[vfd_id]) < 10:
            return {
                "current_mean": 0.0,
                "current_std": 0.0,
                "current_now": 0.0,
                "anomaly_score": 0.0
            }

        history = list(self.histories[vfd_id])
        currents = [d.output_current_a for d in history]

        current_mean = np.mean(currents)
        current_std = np.std(currents)
        current_now = currents[-1]

        # Z-score 기반 이상 점수
        if current_std > 0:
            z_score = abs((current_now - current_mean) / current_std)
            # Z-score를 0-100 점수로 변환 (3-sigma 이상이면 100점)
            anomaly_score = min(100, (z_score / 3.0) * 100)
        else:
            anomaly_score = 0.0

        return {
            "current_mean": round(current_mean, 1),
            "current_std": round(current_std, 1),
            "current_now": round(current_now, 1),
            "anomaly_score": round(anomaly_score, 1)
        }

    def calculate_stress_score(self, vfd_id: str) -> float:
        """
        누적 스트레스 점수 계산

        Returns:
            스트레스 점수 (0-100)
        """
        if vfd_id not in self.histories or len(self.histories[vfd_id]) == 0:
            return 0.0

        history = list(self.histories[vfd_id])
        stress_score = 0.0

        # 고온 운전 스트레스 (모터 온도 70°C 이상)
        high_temp_count = sum(1 for d in history if d.motor_temperature_c > 70)
        stress_score += (high_temp_count / len(history)) * 30

        # 히트싱크 고온 스트레스 (55°C 이상)
        heatsink_high_count = sum(1 for d in history if d.heatsink_temperature_c > 55)
        stress_score += (heatsink_high_count / len(history)) * 20

        # 과부하 스트레스 (정격 전류 초과)
        # Danfoss FC302 132kW: 정격 전류 약 250A, 75kW: 145A, 54.3kW: 105A
        overload_count = sum(1 for d in history if d.output_current_a > 250)
        stress_score += (overload_count / len(history)) * 50

        return min(100, stress_score)


class VFDLifePredictor:
    """VFD 수명 예측"""

    # 설계 수명 (시간)
    BEARING_LIFE_HOURS = 40000  # 베어링 수명
    FAN_LIFE_HOURS = 50000  # 냉각팬 수명
    CAPACITOR_LIFE_HOURS = 60000  # DC 커패시터 수명

    def predict_remaining_life(self, diagnostic: VFDDiagnostic, stress_score: float) -> Dict[str, float]:
        """
        수명 예측

        Args:
            diagnostic: VFD 진단 데이터
            stress_score: 스트레스 점수 (0-100)

        Returns:
            {
                "remaining_life_percent": 잔여 수명 비율 (0-100%),
                "estimated_days": 예상 잔여 일수,
                "limiting_component": 제한 부품 ("bearing", "fan", "capacitor")
            }
        """
        runtime_hours = diagnostic.cumulative_runtime_hours

        # 기본 수명 소모율 (시간 기반)
        bearing_consumed = (runtime_hours / self.BEARING_LIFE_HOURS) * 100
        fan_consumed = (runtime_hours / self.FAN_LIFE_HOURS) * 100
        capacitor_consumed = (runtime_hours / self.CAPACITOR_LIFE_HOURS) * 100

        # 스트레스 가중치 적용 (고스트레스 환경은 수명 단축)
        stress_factor = 1.0 + (stress_score / 100)
        bearing_consumed *= stress_factor
        fan_consumed *= stress_factor
        capacitor_consumed *= stress_factor

        # 가장 빨리 소모되는 부품 기준
        consumptions = {
            "bearing": bearing_consumed,
            "fan": fan_consumed,
            "capacitor": capacitor_consumed
        }
        limiting_component = max(consumptions, key=consumptions.get)
        max_consumed = consumptions[limiting_component]

        # 잔여 수명 (%)
        remaining_life_percent = max(0, 100 - max_consumed)

        # 예상 잔여 일수 (1일 24시간 기준)
        if max_consumed >= 100:
            estimated_days = 0
        else:
            # 현재 소모율로 계산
            if runtime_hours > 0:
                daily_consumption = max_consumed / (runtime_hours / 24)
                if daily_consumption > 0:
                    estimated_days = int(remaining_life_percent / daily_consumption)
                else:
                    estimated_days = 9999
            else:
                estimated_days = 9999

        return {
            "remaining_life_percent": round(remaining_life_percent, 1),
            "estimated_days": estimated_days,
            "limiting_component": limiting_component
        }


class VFDPredictiveDiagnosis:
    """VFD 예방진단 통합 시스템"""

    def __init__(self):
        self.trend_analyzer = VFDTrendAnalyzer(history_size=60)
        self.life_predictor = VFDLifePredictor()

    def add_diagnostic(self, diagnostic: VFDDiagnostic):
        """진단 데이터 추가"""
        self.trend_analyzer.add_diagnostic(diagnostic)

    def predict(self, diagnostic: VFDDiagnostic) -> VFDPrediction:
        """
        종합 예측 수행

        Args:
            diagnostic: 최신 VFD 진단 데이터

        Returns:
            VFDPrediction 객체
        """
        vfd_id = diagnostic.vfd_id

        # 트렌드 분석을 먼저 추가
        self.add_diagnostic(diagnostic)

        # 온도 트렌드 분석
        temp_trend = self.trend_analyzer.analyze_temperature_trend(vfd_id)

        # 전류 이상 감지
        current_anomaly = self.trend_analyzer.detect_current_anomaly(vfd_id)

        # 스트레스 점수
        stress_score = self.trend_analyzer.calculate_stress_score(vfd_id)

        # 수명 예측
        life_prediction = self.life_predictor.predict_remaining_life(diagnostic, stress_score)

        # 종합 이상 점수 (severity_score + anomaly + stress)
        anomaly_score = (
            diagnostic.severity_score * 0.5 +
            current_anomaly["anomaly_score"] * 0.3 +
            stress_score * 0.2
        )

        # 정비 우선순위 결정
        if anomaly_score > 75 or life_prediction["estimated_days"] < 7:
            maintenance_priority = 5  # 즉시
        elif anomaly_score > 50 or life_prediction["estimated_days"] < 30:
            maintenance_priority = 3  # 1주일 내
        elif anomaly_score > 20 or life_prediction["estimated_days"] < 90:
            maintenance_priority = 1  # 정기 점검
        else:
            maintenance_priority = 0  # 정상

        # 예측 신뢰도 (히스토리 개수에 비례)
        history_count = len(self.trend_analyzer.histories.get(vfd_id, []))
        prediction_confidence = min(1.0, history_count / 30)  # 30개 이상이면 신뢰도 1.0

        return VFDPrediction(
            vfd_id=vfd_id,
            timestamp=datetime.now().isoformat(),
            predicted_temp_30min=temp_trend["predicted_30min"],
            temp_rise_rate=temp_trend["rise_rate"],
            temp_trend=temp_trend["trend"],
            remaining_life_percent=life_prediction["remaining_life_percent"],
            estimated_days_to_maintenance=life_prediction["estimated_days"],
            anomaly_score=round(anomaly_score, 1),
            maintenance_priority=maintenance_priority,
            prediction_confidence=round(prediction_confidence, 2)
        )
