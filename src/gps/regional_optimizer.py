"""
해역별 제어 최적화
열대/온대/극지 해역별 적응형 제어
"""
from dataclasses import dataclass
from typing import Dict
from enum import Enum

from src.gps.gps_processor import SeaRegion, NavigationState


class ControlMode(Enum):
    """제어 모드"""
    TROPICAL_INTENSIVE = "tropical_intensive"  # 열대 집중 냉각
    TEMPERATE_BALANCED = "temperate_balanced"  # 온대 균형
    POLAR_ECONOMY = "polar_economy"  # 극지 절약
    BERTHED_MINIMUM = "berthed_minimum"  # 정박 최소


@dataclass
class RegionalParameters:
    """해역별 파라미터"""
    sea_region: SeaRegion
    control_mode: ControlMode

    # 냉각 용량 조정 (1.0 = 기준)
    cooling_capacity_factor: float

    # 팬 최소 대수
    minimum_fan_count: int

    # PID 게인 조정 (1.0 = 기준)
    pid_gain_factor: float

    # 주파수 범위 조정
    min_frequency_hz: float
    max_frequency_hz: float

    # 우선순위
    cooling_priority: float  # 0-1 (낮을수록 절약 우선)
    energy_priority: float  # 0-1 (높을수록 절약 우선)

    # 설명
    description: str


@dataclass
class BerthedParameters:
    """정박 모드 파라미터"""
    # 최소 대수
    minimum_pump_count: int
    minimum_fan_count: int

    # 주파수 하한선
    min_frequency_hz: float

    # 에너지 절약 우선
    energy_priority: float

    description: str


class RegionalOptimizer:
    """
    해역별 제어 최적화

    - 열대: 냉각 성능 우선 (+10% 용량, 팬 3대 이상, PID +20%)
    - 온대: 균형 (표준 제어)
    - 극지: 에너지 절약 우선 (-20% 용량, PID -20%)
    - 정박: 최소 전력 모드
    """

    def __init__(self):
        """초기화"""
        # 해역별 파라미터 정의
        self.regional_params = self._define_regional_parameters()

        # 정박 모드 파라미터
        self.berthed_params = self._define_berthed_parameters()

        # 현재 적용 파라미터
        self.current_params: Dict = {}

    def _define_regional_parameters(self) -> Dict[SeaRegion, RegionalParameters]:
        """해역별 파라미터 정의"""
        params = {}

        # 열대 해역
        params[SeaRegion.TROPICAL] = RegionalParameters(
            sea_region=SeaRegion.TROPICAL,
            control_mode=ControlMode.TROPICAL_INTENSIVE,
            cooling_capacity_factor=1.1,  # +10% 냉각 용량
            minimum_fan_count=3,  # 최소 3대
            pid_gain_factor=1.2,  # +20% PID 게인
            min_frequency_hz=42.0,  # 더 높은 하한
            max_frequency_hz=60.0,
            cooling_priority=0.8,  # 냉각 우선
            energy_priority=0.2,
            description="열대 해역: 냉각 성능 우선, 에너지 절약 < 냉각"
        )

        # 온대 해역
        params[SeaRegion.TEMPERATE] = RegionalParameters(
            sea_region=SeaRegion.TEMPERATE,
            control_mode=ControlMode.TEMPERATE_BALANCED,
            cooling_capacity_factor=1.0,  # 표준
            minimum_fan_count=2,  # 최소 2대
            pid_gain_factor=1.0,  # 표준
            min_frequency_hz=40.0,
            max_frequency_hz=60.0,
            cooling_priority=0.5,  # 균형
            energy_priority=0.5,
            description="온대 해역: 균형잡힌 제어, 에너지 절약 = 냉각"
        )

        # 극지 해역
        params[SeaRegion.POLAR] = RegionalParameters(
            sea_region=SeaRegion.POLAR,
            control_mode=ControlMode.POLAR_ECONOMY,
            cooling_capacity_factor=0.8,  # -20% 냉각 용량
            minimum_fan_count=2,  # 최소 2대
            pid_gain_factor=0.8,  # -20% PID 게인 (과냉각 방지)
            min_frequency_hz=38.0,  # 더 낮은 하한
            max_frequency_hz=60.0,
            cooling_priority=0.2,  # 에너지 우선
            energy_priority=0.8,
            description="극지 해역: 에너지 절약 우선, 과냉각 방지"
        )

        return params

    def _define_berthed_parameters(self) -> BerthedParameters:
        """정박 모드 파라미터 정의"""
        return BerthedParameters(
            minimum_pump_count=1,  # 펌프 1대
            minimum_fan_count=2,  # 팬 2대
            min_frequency_hz=40.0,  # 40Hz 하한
            energy_priority=1.0,  # 100% 에너지 절약 우선
            description="정박 모드: 최소 전력, 에너지 절약 최대화"
        )

    def get_optimized_parameters(
        self,
        sea_region: SeaRegion,
        navigation_state: NavigationState
    ) -> Dict:
        """
        최적화된 파라미터 반환

        Args:
            sea_region: 해역
            navigation_state: 운항 상태

        Returns:
            제어 파라미터 사전
        """
        # 정박 모드 우선 체크
        if navigation_state == NavigationState.BERTHED:
            return self._get_berthed_mode_parameters()

        # 해역별 파라미터
        if sea_region not in self.regional_params:
            sea_region = SeaRegion.TEMPERATE  # 기본값

        regional = self.regional_params[sea_region]

        self.current_params = {
            'sea_region': regional.sea_region.value,
            'control_mode': regional.control_mode.value,
            'cooling_capacity_factor': regional.cooling_capacity_factor,
            'minimum_fan_count': regional.minimum_fan_count,
            'pid_gain_factor': regional.pid_gain_factor,
            'min_frequency_hz': regional.min_frequency_hz,
            'max_frequency_hz': regional.max_frequency_hz,
            'cooling_priority': regional.cooling_priority,
            'energy_priority': regional.energy_priority,
            'description': regional.description
        }

        return self.current_params

    def _get_berthed_mode_parameters(self) -> Dict:
        """정박 모드 파라미터"""
        berthed = self.berthed_params

        self.current_params = {
            'sea_region': 'N/A',
            'control_mode': ControlMode.BERTHED_MINIMUM.value,
            'cooling_capacity_factor': 0.6,  # 대폭 감소
            'minimum_pump_count': berthed.minimum_pump_count,
            'minimum_fan_count': berthed.minimum_fan_count,
            'pid_gain_factor': 0.8,
            'min_frequency_hz': berthed.min_frequency_hz,
            'max_frequency_hz': 55.0,  # 최대도 제한
            'cooling_priority': 0.0,
            'energy_priority': berthed.energy_priority,
            'description': berthed.description
        }

        return self.current_params

    def apply_regional_adjustment(
        self,
        base_frequency: float,
        base_pump_count: int,
        base_fan_count: int,
        sea_region: SeaRegion,
        navigation_state: NavigationState
    ) -> Dict[str, float]:
        """
        해역별 조정 적용

        Args:
            base_frequency: 기본 주파수
            base_pump_count: 기본 펌프 대수
            base_fan_count: 기본 팬 대수
            sea_region: 해역
            navigation_state: 운항 상태

        Returns:
            조정된 파라미터
        """
        params = self.get_optimized_parameters(sea_region, navigation_state)

        # 주파수 조정
        adjusted_freq = base_frequency * params['cooling_capacity_factor']

        # 범위 제한
        adjusted_freq = max(params['min_frequency_hz'],
                           min(params['max_frequency_hz'], adjusted_freq))

        # 팬 대수 조정
        adjusted_fan_count = max(params['minimum_fan_count'], base_fan_count)

        # 정박 모드: 펌프 최소화
        if navigation_state == NavigationState.BERTHED:
            adjusted_pump_count = params['minimum_pump_count']
        else:
            adjusted_pump_count = base_pump_count

        return {
            'adjusted_frequency_hz': adjusted_freq,
            'adjusted_pump_count': adjusted_pump_count,
            'adjusted_fan_count': adjusted_fan_count,
            'pid_gain_factor': params['pid_gain_factor'],
            'control_mode': params['control_mode']
        }

    def get_mode_transition_time(
        self,
        from_region: SeaRegion,
        to_region: SeaRegion
    ) -> float:
        """
        모드 전환 시간 (초)

        Args:
            from_region: 이전 해역
            to_region: 새 해역

        Returns:
            전환 예상 시간 (초)
        """
        # 같은 해역: 즉시
        if from_region == to_region:
            return 0.0

        # 열대 ↔ 극지: 30초 (큰 변화)
        if {from_region, to_region} == {SeaRegion.TROPICAL, SeaRegion.POLAR}:
            return 30.0

        # 기타: 15초
        return 15.0

    def get_efficiency_improvement(
        self,
        sea_region: SeaRegion,
        baseline_energy: float
    ) -> Dict:
        """
        효율 개선 추정

        Args:
            sea_region: 해역
            baseline_energy: 기준 에너지 (표준 제어)

        Returns:
            효율 개선 정보
        """
        params = self.regional_params.get(sea_region, self.regional_params[SeaRegion.TEMPERATE])

        # 해역별 효율 개선율
        improvements = {
            SeaRegion.TROPICAL: -3.0,  # -3% (냉각 우선으로 에너지 증가)
            SeaRegion.TEMPERATE: 0.0,  # 기준
            SeaRegion.POLAR: 8.0  # +8% (에너지 절약)
        }

        improvement_percent = improvements.get(sea_region, 0.0)
        improved_energy = baseline_energy * (1.0 + improvement_percent / 100.0)

        return {
            'sea_region': sea_region.value,
            'baseline_energy_kw': baseline_energy,
            'improved_energy_kw': improved_energy,
            'improvement_percent': improvement_percent,
            'description': params.description
        }
