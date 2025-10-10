"""
시나리오 데이터베이스 및 학습 시스템
성공적인 제어 사례를 저장하고 활용
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from enum import Enum
import json
import os


class ScenarioType(Enum):
    """시나리오 타입"""
    TROPICAL = "tropical"  # 열대 해역
    TEMPERATE = "temperate"  # 온대 해역
    POLAR = "polar"  # 극지 해역
    HIGH_LOAD = "high_load"  # 고부하 운전
    LOW_LOAD = "low_load"  # 저부하 운전
    ACCELERATION = "acceleration"  # 가속 구간
    DECELERATION = "deceleration"  # 감속 구간
    BERTHING = "berthing"  # 정박


@dataclass
class ScenarioCondition:
    """시나리오 조건"""
    # 환경 조건
    seawater_temp_range: tuple[float, float]  # T1 범위
    outside_air_temp_range: tuple[float, float]  # T7 범위

    # 운항 조건
    engine_load_range: tuple[float, float]  # % 범위
    ship_speed_range: tuple[float, float]  # knots 범위

    # 선택적 조건
    season: Optional[int] = None  # 0-3

    # 지리 조건
    latitude_range: Optional[tuple[float, float]] = None
    longitude_range: Optional[tuple[float, float]] = None


@dataclass
class ScenarioSolution:
    """시나리오 해결책"""
    pump_frequency_hz: float
    pump_count: int
    fan_frequency_hz: float
    fan_count: int

    # 성과
    achieved_t5: float
    achieved_t6: float
    power_consumption_kw: float
    savings_percent: float
    performance_score: float  # 0-100


@dataclass
class Scenario:
    """시나리오"""
    scenario_id: str
    scenario_type: ScenarioType
    condition: ScenarioCondition
    solution: ScenarioSolution

    # 메타데이터
    created_at: datetime
    last_used: datetime
    usage_count: int
    success_rate: float  # 0-1

    def matches_condition(
        self,
        t1: float,
        t7: float,
        engine_load: float,
        ship_speed: float,
        season: int,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> tuple[bool, float]:
        """
        조건 매칭 여부 및 유사도

        Returns:
            (매칭 여부, 유사도 0-1)
        """
        similarity = 1.0

        # 온도 매칭
        if not (self.condition.seawater_temp_range[0] <= t1 <= self.condition.seawater_temp_range[1]):
            return False, 0.0
        if not (self.condition.outside_air_temp_range[0] <= t7 <= self.condition.outside_air_temp_range[1]):
            return False, 0.0

        # 엔진 부하 매칭
        if not (self.condition.engine_load_range[0] <= engine_load <= self.condition.engine_load_range[1]):
            return False, 0.0

        # 선속 매칭
        if not (self.condition.ship_speed_range[0] <= ship_speed <= self.condition.ship_speed_range[1]):
            return False, 0.0

        # 계절 매칭 (옵션)
        if self.condition.season is not None and self.condition.season != season:
            similarity *= 0.9

        # 위치 매칭 (옵션)
        if self.condition.latitude_range is not None and lat is not None:
            if not (self.condition.latitude_range[0] <= lat <= self.condition.latitude_range[1]):
                similarity *= 0.8

        return True, similarity


class ScenarioDatabase:
    """
    시나리오 데이터베이스

    학습 목표:
    - 2-4주 이내 새 패턴 학습
    - 동일 조건 30회 이상 누적시 학습
    - 성공 사례 (95점 이상) 저장
    """

    def __init__(self, db_path: str = "data/scenarios"):
        """
        Args:
            db_path: 데이터베이스 경로
        """
        self.db_path = db_path
        self.scenarios: List[Scenario] = []

        # 학습 파라미터
        self.min_samples_for_learning = 30  # 학습 시작 임계값
        self.min_performance_score = 95.0  # 저장 기준 점수

        # 통계
        self.total_scenarios = 0
        self.scenarios_by_type: Dict[ScenarioType, int] = {}

        os.makedirs(db_path, exist_ok=True)
        self._load_database()

    def _load_database(self):
        """데이터베이스 로드"""
        db_file = os.path.join(self.db_path, "scenarios.json")

        if not os.path.exists(db_file):
            return

        try:
            with open(db_file, 'r') as f:
                data = json.load(f)

            for item in data:
                scenario = self._deserialize_scenario(item)
                self.scenarios.append(scenario)

            self._update_statistics()

        except Exception as e:
            print(f"Warning: Failed to load database: {e}")

    def _save_database(self):
        """데이터베이스 저장"""
        db_file = os.path.join(self.db_path, "scenarios.json")

        data = [self._serialize_scenario(s) for s in self.scenarios]

        with open(db_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _serialize_scenario(self, scenario: Scenario) -> Dict:
        """시나리오 직렬화"""
        return {
            'scenario_id': scenario.scenario_id,
            'scenario_type': scenario.scenario_type.value,
            'condition': asdict(scenario.condition),
            'solution': asdict(scenario.solution),
            'created_at': scenario.created_at.isoformat(),
            'last_used': scenario.last_used.isoformat(),
            'usage_count': scenario.usage_count,
            'success_rate': scenario.success_rate
        }

    def _deserialize_scenario(self, data: Dict) -> Scenario:
        """시나리오 역직렬화"""
        return Scenario(
            scenario_id=data['scenario_id'],
            scenario_type=ScenarioType(data['scenario_type']),
            condition=ScenarioCondition(**data['condition']),
            solution=ScenarioSolution(**data['solution']),
            created_at=datetime.fromisoformat(data['created_at']),
            last_used=datetime.fromisoformat(data['last_used']),
            usage_count=data['usage_count'],
            success_rate=data['success_rate']
        )

    def add_scenario(
        self,
        scenario_type: ScenarioType,
        condition: ScenarioCondition,
        solution: ScenarioSolution
    ) -> str:
        """
        시나리오 추가 (성과 기준 충족시)

        Returns:
            시나리오 ID
        """
        # 성과 점수 확인
        if solution.performance_score < self.min_performance_score:
            return ""  # 저장하지 않음

        # 시나리오 ID 생성
        scenario_id = f"{scenario_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        scenario = Scenario(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            condition=condition,
            solution=solution,
            created_at=datetime.now(),
            last_used=datetime.now(),
            usage_count=1,
            success_rate=1.0
        )

        self.scenarios.append(scenario)
        self._update_statistics()
        self._save_database()

        return scenario_id

    def find_matching_scenarios(
        self,
        t1: float,
        t7: float,
        engine_load: float,
        ship_speed: float,
        season: int,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        max_results: int = 5
    ) -> List[tuple[Scenario, float]]:
        """
        매칭되는 시나리오 검색

        Returns:
            [(시나리오, 유사도)] 리스트 (유사도 내림차순)
        """
        matches = []

        for scenario in self.scenarios:
            is_match, similarity = scenario.matches_condition(
                t1, t7, engine_load, ship_speed, season, lat, lon
            )

            if is_match:
                # 성공률과 사용 빈도를 고려한 점수
                score = similarity * scenario.success_rate * (1 + 0.1 * min(scenario.usage_count, 10))
                matches.append((scenario, score))

        # 점수 기준 정렬
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches[:max_results]

    def update_scenario_usage(
        self,
        scenario_id: str,
        success: bool
    ):
        """시나리오 사용 결과 업데이트"""
        for scenario in self.scenarios:
            if scenario.scenario_id == scenario_id:
                scenario.last_used = datetime.now()
                scenario.usage_count += 1

                # 성공률 업데이트 (지수 이동 평균)
                alpha = 0.1
                scenario.success_rate = (
                    alpha * (1.0 if success else 0.0) +
                    (1 - alpha) * scenario.success_rate
                )

                self._save_database()
                break

    def get_learning_progress(self) -> Dict:
        """
        학습 진행 상황

        Returns:
            타입별 학습 진행률
        """
        progress = {}

        for scenario_type in ScenarioType:
            count = self.scenarios_by_type.get(scenario_type, 0)
            learned = count >= self.min_samples_for_learning

            progress[scenario_type.value] = {
                'count': count,
                'target': self.min_samples_for_learning,
                'progress_percent': min(100, (count / self.min_samples_for_learning) * 100),
                'learned': learned
            }

        return progress

    def cleanup_old_scenarios(self, days: int = 90):
        """오래된 시나리오 정리"""
        cutoff = datetime.now() - timedelta(days=days)

        # 최근 사용되지 않은 시나리오 제거
        self.scenarios = [
            s for s in self.scenarios
            if s.last_used > cutoff or s.usage_count > 10
        ]

        self._update_statistics()
        self._save_database()

    def _update_statistics(self):
        """통계 업데이트"""
        self.total_scenarios = len(self.scenarios)
        self.scenarios_by_type = {}

        for scenario in self.scenarios:
            stype = scenario.scenario_type
            self.scenarios_by_type[stype] = self.scenarios_by_type.get(stype, 0) + 1

    def get_database_info(self) -> Dict:
        """데이터베이스 정보"""
        return {
            'total_scenarios': self.total_scenarios,
            'scenarios_by_type': {k.value: v for k, v in self.scenarios_by_type.items()},
            'learning_progress': self.get_learning_progress(),
            'db_path': self.db_path
        }
