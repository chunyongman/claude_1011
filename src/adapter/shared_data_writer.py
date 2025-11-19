"""
공유 데이터 파일 Writer
EDGE AI 분석 결과를 공유 JSON 파일에 저장하여 HMI와 데이터 교환
"""

import json
import logging
from typing import Dict, Any
from pathlib import Path
from datetime import datetime
from src.diagnostics.vfd_monitor import VFDDiagnostic
from src.diagnostics.vfd_predictive_diagnosis import VFDPrediction

logger = logging.getLogger(__name__)


class SharedDataWriter:
    """공유 데이터 파일 Writer (EDGE → HMI)"""

    def __init__(self, shared_dir: str = "C:/shared"):
        """
        초기화

        Args:
            shared_dir: 공유 디렉토리 경로
        """
        self.shared_dir = Path(shared_dir)
        self.shared_dir.mkdir(parents=True, exist_ok=True)

        self.vfd_diagnostics_file = self.shared_dir / "vfd_diagnostics.json"

        logger.info(f"✅ 공유 데이터 Writer 초기화: {self.shared_dir}")

    def write_vfd_diagnostics(
        self,
        diagnostics: Dict[str, VFDDiagnostic],
        predictions: Dict[str, VFDPrediction]
    ):
        """
        VFD 진단 및 예측 결과를 공유 파일에 저장

        Args:
            diagnostics: {vfd_id: VFDDiagnostic}
            predictions: {vfd_id: VFDPrediction}
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "vfd_count": len(diagnostics),
            "vfd_diagnostics": {}
        }

        # 각 VFD별로 진단 + 예측 데이터 통합
        for vfd_id, diagnostic in diagnostics.items():
            prediction = predictions.get(vfd_id)

            vfd_data = {
                # 기본 정보
                "vfd_id": vfd_id,
                "timestamp": diagnostic.timestamp.isoformat(),

                # 실시간 운전 데이터
                "current_frequency_hz": diagnostic.current_frequency_hz,
                "output_current_a": diagnostic.output_current_a,
                "output_voltage_v": diagnostic.output_voltage_v,
                "dc_bus_voltage_v": diagnostic.dc_bus_voltage_v,
                "motor_temperature_c": diagnostic.motor_temperature_c,
                "heatsink_temperature_c": diagnostic.heatsink_temperature_c,

                # 진단 결과
                "status_grade": diagnostic.status_grade.value,  # "normal", "caution", etc.
                "severity_score": diagnostic.severity_score,
                "anomaly_patterns": diagnostic.anomaly_patterns,
                "recommendation": diagnostic.recommendation,

                # 누적 통계
                "cumulative_runtime_hours": diagnostic.cumulative_runtime_hours,
                "trip_count": diagnostic.trip_count,
                "error_count": diagnostic.error_count,
                "warning_count": diagnostic.warning_count,
            }

            # 예측 데이터 추가 (있으면)
            if prediction:
                vfd_data.update({
                    "predicted_temp_30min": prediction.predicted_temp_30min,
                    "temp_rise_rate": prediction.temp_rise_rate,
                    "temp_trend": prediction.temp_trend,
                    "remaining_life_percent": prediction.remaining_life_percent,
                    "estimated_days_to_maintenance": prediction.estimated_days_to_maintenance,
                    "anomaly_score": prediction.anomaly_score,
                    "maintenance_priority": prediction.maintenance_priority,
                    "prediction_confidence": prediction.prediction_confidence,
                })

            data["vfd_diagnostics"][vfd_id] = vfd_data

        # JSON 파일로 저장
        try:
            with open(self.vfd_diagnostics_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"✅ VFD 진단 데이터 저장 완료: {len(diagnostics)}개 VFD")

        except Exception as e:
            logger.error(f"❌ VFD 진단 데이터 저장 실패: {e}")

    def write_simple_status(self, key: str, value: Any):
        """
        간단한 상태 데이터 저장

        Args:
            key: 데이터 키
            value: 값 (JSON 직렬화 가능한 타입)
        """
        status_file = self.shared_dir / f"{key}.json"

        try:
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "value": value
                }, f, ensure_ascii=False, indent=2)

            logger.debug(f"✅ 상태 데이터 저장: {key}")

        except Exception as e:
            logger.error(f"❌ 상태 데이터 저장 실패 ({key}): {e}")
