"""
ESS AI System - Xavier NX 리소스 관리 시스템
메모리, 스토리지, CPU 효율적 활용
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
import psutil
from enum import Enum
from pathlib import Path


class ResourceType(Enum):
    """리소스 타입"""
    MEMORY = "memory"
    STORAGE = "storage"
    CPU = "cpu"
    GPU = "gpu"


class OperationMode(Enum):
    """동작 모드"""
    REAL_TIME_CONTROL = "real_time_control"  # 실시간 제어 우선
    BATCH_LEARNING = "batch_learning"  # 배치 학습 모드


@dataclass
class XavierNXSpecs:
    """
    NVIDIA Jetson Xavier NX 사양
    - AI Performance: 21 TOPS
    - GPU: 384-core NVIDIA Volta™ GPU with 48 Tensor Cores
    - CPU: 6-core NVIDIA Carmel ARM®v8.2 64-bit CPU (6 MB L2 + 4 MB L3)
    - Memory: 8GB 128-bit LPDDR4x 51.2GB/s
    - Storage: 256GB NVMe SSD (외장)
    - Power: 10W / 15W / 20W modes
    - Temperature: -25°C to 80°C
    """
    total_memory_gb: float = 8.0
    total_storage_gb: float = 256.0
    cpu_cores: int = 6
    gpu_cuda_cores: int = 384
    ai_tops: int = 21
    power_consumption_w: int = 15  # 기본 15W 모드
    operating_temp_range: tuple = (-25, 80)


@dataclass
class MemoryAllocation:
    """
    메모리 할당 계획 (8GB LPDDR4x)
    - 실시간 제어: 2GB
    - OS 및 기본 프로세스: 2.5GB
    - 머신러닝 학습: 1.5GB (주 2회 학습시만)
    - 시스템 버퍼: 2GB
    """
    real_time_control_gb: float = 2.0
    os_system_gb: float = 2.5
    ml_learning_gb: float = 1.5
    system_buffer_gb: float = 2.0

    def get_total_allocation(self) -> float:
        """총 할당량"""
        return (self.real_time_control_gb +
                self.os_system_gb +
                self.ml_learning_gb +
                self.system_buffer_gb)

    def get_allocation_dict(self) -> Dict[str, float]:
        """할당 현황"""
        return {
            "실시간 제어": self.real_time_control_gb,
            "OS 및 시스템": self.os_system_gb,
            "머신러닝 학습": self.ml_learning_gb,
            "시스템 버퍼": self.system_buffer_gb,
            "총합": self.get_total_allocation()
        }


@dataclass
class StorageAllocation:
    """
    스토리지 할당 계획 (256GB NVMe SSD)
    - OS 및 프로그램: 50GB
    - AI 모델 및 시나리오 DB: 30GB
    - 6개월 운항 데이터: 150GB
    - 여유 공간: 26GB
    """
    os_program_gb: float = 50.0
    ai_models_db_gb: float = 30.0
    operation_data_6months_gb: float = 150.0
    free_space_gb: float = 26.0

    def get_total_allocation(self) -> float:
        """총 할당량"""
        return (self.os_program_gb +
                self.ai_models_db_gb +
                self.operation_data_6months_gb +
                self.free_space_gb)

    def get_allocation_dict(self) -> Dict[str, float]:
        """할당 현황"""
        return {
            "OS 및 프로그램": self.os_program_gb,
            "AI 모델 및 시나리오 DB": self.ai_models_db_gb,
            "6개월 운항 데이터": self.operation_data_6months_gb,
            "여유 공간": self.free_space_gb,
            "총합": self.get_total_allocation()
        }


@dataclass
class DataRetentionPolicy:
    """
    데이터 순환 정책
    - 최근 6개월: 고해상도 보관 (2초 주기)
    - 6개월-1년: 압축 저장 (10초 주기로 다운샘플링)
    - 1년 이상: 핵심 패턴만 추출 보관
    """
    high_resolution_months: int = 6
    compressed_months: int = 6
    pattern_only_after_months: int = 12

    high_res_interval_seconds: int = 2
    compressed_interval_seconds: int = 10

    def get_retention_strategy(self, data_age_months: float) -> str:
        """데이터 나이에 따른 보관 전략"""
        if data_age_months <= self.high_resolution_months:
            return f"고해상도 ({self.high_res_interval_seconds}초 주기)"
        elif data_age_months <= self.high_resolution_months + self.compressed_months:
            return f"압축 저장 ({self.compressed_interval_seconds}초 주기)"
        else:
            return "핵심 패턴만 보관"


@dataclass
class ResourceMonitor:
    """리소스 모니터링"""
    specs: XavierNXSpecs = field(default_factory=XavierNXSpecs)
    memory_allocation: MemoryAllocation = field(default_factory=MemoryAllocation)
    storage_allocation: StorageAllocation = field(default_factory=StorageAllocation)
    data_retention: DataRetentionPolicy = field(default_factory=DataRetentionPolicy)

    current_mode: OperationMode = OperationMode.REAL_TIME_CONTROL
    monitoring_history: List[Dict] = field(default_factory=list)

    def get_memory_usage(self) -> Dict:
        """현재 메모리 사용량"""
        try:
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "percent": mem.percent,
                "mode": self.current_mode.value
            }
        except Exception as e:
            # psutil이 실행되지 않는 환경에서는 시뮬레이션 값 반환
            return {
                "total_gb": self.specs.total_memory_gb,
                "used_gb": 3.5 if self.current_mode == OperationMode.REAL_TIME_CONTROL else 6.0,
                "available_gb": 4.5 if self.current_mode == OperationMode.REAL_TIME_CONTROL else 2.0,
                "percent": 43.75 if self.current_mode == OperationMode.REAL_TIME_CONTROL else 75.0,
                "mode": self.current_mode.value,
                "simulated": True
            }

    def get_storage_usage(self, path: str = "/") -> Dict:
        """현재 스토리지 사용량"""
        try:
            disk = psutil.disk_usage(path)
            return {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent
            }
        except Exception as e:
            # psutil이 실행되지 않는 환경에서는 시뮬레이션 값 반환
            return {
                "total_gb": self.specs.total_storage_gb,
                "used_gb": 80.0,
                "free_gb": 176.0,
                "percent": 31.25,
                "simulated": True
            }

    def get_cpu_usage(self) -> Dict:
        """현재 CPU 사용량"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
            return {
                "cores": len(cpu_percent),
                "per_core_percent": [round(p, 1) for p in cpu_percent],
                "average_percent": round(sum(cpu_percent) / len(cpu_percent), 1),
                "mode": self.current_mode.value
            }
        except Exception as e:
            # 시뮬레이션 값
            if self.current_mode == OperationMode.REAL_TIME_CONTROL:
                usage = [15.0, 12.0, 18.0, 10.0, 8.0, 5.0]
            else:
                usage = [65.0, 70.0, 68.0, 72.0, 55.0, 50.0]

            return {
                "cores": self.specs.cpu_cores,
                "per_core_percent": usage,
                "average_percent": round(sum(usage) / len(usage), 1),
                "mode": self.current_mode.value,
                "simulated": True
            }

    def check_ml_model_utilization(self) -> Dict:
        """
        머신러닝 모델의 Xavier NX 성능 활용도
        - 초기: Xavier NX 성능의 약 10% 활용
        - scikit-learn 경량 모델
        """
        return {
            "ai_tops_available": self.specs.ai_tops,
            "ai_tops_used": 2.1,  # 약 10% 활용
            "utilization_percent": 10.0,
            "model_types": [
                {
                    "name": "Polynomial Regression (온도 예측)",
                    "size_mb": 0.5,
                    "inference_time_ms": 8,
                    "framework": "scikit-learn"
                },
                {
                    "name": "Random Forest (최적화)",
                    "size_mb": 1.5,
                    "inference_time_ms": 12,
                    "framework": "scikit-learn"
                }
            ],
            "future_expansion": {
                "available_tops": 18.9,  # 90% 여유
                "potential_models": ["LSTM", "Transformer", "진동 예지보전", "이미지 분석"]
            }
        }

    def switch_mode(self, new_mode: OperationMode) -> bool:
        """동작 모드 전환"""
        if self.current_mode == new_mode:
            return True

        print(f"🔄 모드 전환: {self.current_mode.value} → {new_mode.value}")

        if new_mode == OperationMode.BATCH_LEARNING:
            # 배치 학습 모드: 더 많은 메모리와 CPU 사용 가능
            mem_usage = self.get_memory_usage()
            if mem_usage.get("available_gb", 0) < 2.0:
                print("⚠️ 메모리 부족으로 배치 학습 모드 전환 실패")
                return False

        self.current_mode = new_mode
        return True

    def get_resource_status(self) -> Dict:
        """전체 리소스 상태"""
        return {
            "timestamp": datetime.now().isoformat(),
            "hardware_specs": {
                "platform": "NVIDIA Jetson Xavier NX",
                "memory_gb": self.specs.total_memory_gb,
                "storage_gb": self.specs.total_storage_gb,
                "cpu_cores": self.specs.cpu_cores,
                "ai_tops": self.specs.ai_tops,
                "power_w": self.specs.power_consumption_w
            },
            "current_usage": {
                "memory": self.get_memory_usage(),
                "storage": self.get_storage_usage(),
                "cpu": self.get_cpu_usage()
            },
            "allocation_plan": {
                "memory_gb": self.memory_allocation.get_allocation_dict(),
                "storage_gb": self.storage_allocation.get_allocation_dict()
            },
            "ml_utilization": self.check_ml_model_utilization(),
            "operation_mode": self.current_mode.value,
            "data_retention_policy": {
                "high_resolution_months": self.data_retention.high_resolution_months,
                "compressed_months": self.data_retention.compressed_months,
                "pattern_only_after_months": self.data_retention.pattern_only_after_months
            }
        }

    def monitor_and_log(self) -> Dict:
        """모니터링 및 로그 기록"""
        status = self.get_resource_status()
        self.monitoring_history.append(status)

        # 최근 100개만 유지
        if len(self.monitoring_history) > 100:
            self.monitoring_history = self.monitoring_history[-100:]

        return status

    def get_xavier_nx_advantages(self) -> List[str]:
        """Xavier NX 선택 근거"""
        return [
            "✅ 저전력 소비 10-20W - 선박 전력 환경 효율적",
            "✅ 광범위한 작동 온도 -25°C ~ 80°C - 엔진룸 환경 적합",
            "✅ 내진동/내충격 설계 - 선박 환경 적합",
            "✅ 팬리스 설계 가능 - 유지보수 최소화",
            "✅ 현재 10% 성능 활용 - 향후 확장 가능성 90%",
            "✅ 21 TOPS AI 성능 - 딥러닝 업그레이드 여지",
            "✅ 실시간 제어 2초 주기 여유있게 충족",
            "✅ 추가 AI 기능 통합 가능 (진동 예지보전 등)"
        ]


def create_resource_monitor() -> ResourceMonitor:
    """리소스 모니터 생성"""
    return ResourceMonitor()
