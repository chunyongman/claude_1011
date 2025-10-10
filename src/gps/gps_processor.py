"""
GPS 데이터 처리 및 환경 분류
"""
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime
from enum import Enum
import math


class SeaRegion(Enum):
    """해역 분류"""
    TROPICAL = "tropical"  # 열대
    TEMPERATE = "temperate"  # 온대
    POLAR = "polar"  # 극지


class Season(Enum):
    """계절"""
    SPRING = "spring"  # 봄
    SUMMER = "summer"  # 여름
    AUTUMN = "autumn"  # 가을
    WINTER = "winter"  # 겨울


class NavigationState(Enum):
    """운항 상태"""
    BERTHED = "berthed"  # 정박
    NAVIGATING = "navigating"  # 운항


@dataclass
class GPSData:
    """GPS 데이터"""
    timestamp: datetime
    latitude: float  # 위도 (-90 ~ +90)
    longitude: float  # 경도 (-180 ~ +180)
    speed_knots: float  # 선속 (knots)
    heading_degrees: float  # 방향 (0-360°, 0=북)
    utc_time: datetime  # UTC 시간


@dataclass
class EnvironmentClassification:
    """환경 분류 결과"""
    timestamp: datetime

    # GPS 기반
    sea_region: SeaRegion
    season: Season
    navigation_state: NavigationState

    # 환경 특성
    estimated_seawater_temp: float  # 추정 해수 온도
    ambient_correction_factor: float  # 환경 보정 계수

    # 위치 정보
    latitude: float
    longitude: float
    speed_knots: float


class GPSProcessor:
    """
    GPS 데이터 처리 및 환경 분류

    - 위치, 속도, 방향, UTC 시간 추출
    - 해역별 분류 (열대/온대/극지)
    - 계절별 보정
    - 운항 상태 판단
    """

    def __init__(self):
        """초기화"""
        # 정박 판정 임계값
        self.berthing_speed_threshold = 0.5  # knots

        # 해역별 온도 가정
        self.tropical_temp = 28.0  # °C
        self.temperate_temp_range = (15.0, 28.0)  # °C
        self.polar_temp = 10.0  # °C

    def process_gps_data(self, gps_data: GPSData) -> EnvironmentClassification:
        """
        GPS 데이터 처리

        Args:
            gps_data: GPS 데이터

        Returns:
            EnvironmentClassification
        """
        # 해역 분류
        sea_region = self._classify_sea_region(gps_data.latitude)

        # 계절 판단
        season = self._determine_season(gps_data.utc_time, gps_data.latitude)

        # 운항 상태
        nav_state = self._determine_navigation_state(gps_data.speed_knots)

        # 해수 온도 추정
        seawater_temp = self._estimate_seawater_temperature(
            sea_region, season, gps_data.latitude
        )

        # 환경 보정 계수 (계절별)
        correction_factor = self._calculate_correction_factor(season, sea_region)

        return EnvironmentClassification(
            timestamp=gps_data.timestamp,
            sea_region=sea_region,
            season=season,
            navigation_state=nav_state,
            estimated_seawater_temp=seawater_temp,
            ambient_correction_factor=correction_factor,
            latitude=gps_data.latitude,
            longitude=gps_data.longitude,
            speed_knots=gps_data.speed_knots
        )

    def _classify_sea_region(self, latitude: float) -> SeaRegion:
        """
        해역 분류

        Args:
            latitude: 위도

        Returns:
            SeaRegion
        """
        abs_lat = abs(latitude)

        if abs_lat <= 23.5:
            # 열대 (적도 ±23.5°)
            return SeaRegion.TROPICAL
        elif abs_lat <= 66.5:
            # 온대 (23.5° ~ 66.5°)
            return SeaRegion.TEMPERATE
        else:
            # 극지 (66.5° 이상)
            return SeaRegion.POLAR

    def _determine_season(self, utc_time: datetime, latitude: float) -> Season:
        """
        계절 판단

        UTC 시간과 위도를 조합하여 계절 판단

        Args:
            utc_time: UTC 시간
            latitude: 위도

        Returns:
            Season
        """
        month = utc_time.month

        # 북반구
        if latitude >= 0:
            if month in [3, 4, 5]:
                return Season.SPRING
            elif month in [6, 7, 8]:
                return Season.SUMMER
            elif month in [9, 10, 11]:
                return Season.AUTUMN
            else:
                return Season.WINTER
        else:
            # 남반구 (계절 반대)
            if month in [3, 4, 5]:
                return Season.AUTUMN
            elif month in [6, 7, 8]:
                return Season.WINTER
            elif month in [9, 10, 11]:
                return Season.SPRING
            else:
                return Season.SUMMER

    def _determine_navigation_state(self, speed_knots: float) -> NavigationState:
        """
        운항 상태 판단

        Args:
            speed_knots: 선속

        Returns:
            NavigationState
        """
        if speed_knots < self.berthing_speed_threshold:
            return NavigationState.BERTHED
        else:
            return NavigationState.NAVIGATING

    def _estimate_seawater_temperature(
        self,
        sea_region: SeaRegion,
        season: Season,
        latitude: float
    ) -> float:
        """
        해수 온도 추정

        Args:
            sea_region: 해역
            season: 계절
            latitude: 위도

        Returns:
            추정 해수 온도 (°C)
        """
        if sea_region == SeaRegion.TROPICAL:
            # 열대: 28°C 기준
            base_temp = self.tropical_temp

            # 계절 변동 작음 (±1°C)
            if season in [Season.WINTER, Season.SPRING]:
                return base_temp - 1.0
            else:
                return base_temp

        elif sea_region == SeaRegion.TEMPERATE:
            # 온대: 15-28°C
            # 위도에 따라 선형 보간
            abs_lat = abs(latitude)
            # 23.5° → 28°C, 66.5° → 15°C
            lat_factor = (66.5 - abs_lat) / (66.5 - 23.5)
            base_temp = 15.0 + lat_factor * 13.0

            # 계절 변동 (±5°C)
            if season == Season.SUMMER:
                return base_temp + 5.0
            elif season == Season.WINTER:
                return base_temp - 5.0
            else:
                return base_temp

        else:
            # 극지: 10°C 이하
            base_temp = self.polar_temp

            # 계절 변동 (±3°C)
            if season == Season.SUMMER:
                return base_temp + 3.0
            else:
                return base_temp - 2.0

    def _calculate_correction_factor(
        self,
        season: Season,
        sea_region: SeaRegion
    ) -> float:
        """
        환경 보정 계수

        계절 및 해역에 따른 보정

        Args:
            season: 계절
            sea_region: 해역

        Returns:
            보정 계수 (1.0 = 기준)
        """
        # 기준: 1.0
        factor = 1.0

        # 열대 해역: 냉각 부하 증가
        if sea_region == SeaRegion.TROPICAL:
            factor *= 1.1  # +10%

            # 여름: 추가 증가
            if season == Season.SUMMER:
                factor *= 1.05  # 총 +15.5%

        # 극지 해역: 냉각 부하 감소
        elif sea_region == SeaRegion.POLAR:
            factor *= 0.8  # -20%

            # 겨울: 추가 감소
            if season == Season.WINTER:
                factor *= 0.95  # 총 -24%

        # 온대 해역: 계절별 보정
        else:
            if season == Season.SUMMER:
                factor *= 1.05  # +5%
            elif season == Season.WINTER:
                factor *= 0.95  # -5%

        return factor

    def calculate_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        두 GPS 좌표 간 거리 계산 (Haversine formula)

        Args:
            lat1, lon1: 첫 번째 좌표
            lat2, lon2: 두 번째 좌표

        Returns:
            거리 (nautical miles)
        """
        # 지구 반경 (nautical miles)
        R = 3440.065

        # 라디안 변환
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        # Haversine formula
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance

    def calculate_bearing(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        방위각 계산

        Args:
            lat1, lon1: 시작 좌표
            lat2, lon2: 목표 좌표

        Returns:
            방위각 (0-360°, 0=북)
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon = math.radians(lon2 - lon1)

        y = math.sin(dlon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))

        bearing_rad = math.atan2(y, x)
        bearing = (math.degrees(bearing_rad) + 360) % 360

        return bearing

    def detect_course_change(
        self,
        previous_heading: float,
        current_heading: float,
        threshold_degrees: float = 15.0
    ) -> bool:
        """
        변침 감지

        Args:
            previous_heading: 이전 방향
            current_heading: 현재 방향
            threshold_degrees: 변침 판정 임계값

        Returns:
            변침 여부
        """
        # 각도 차이 계산 (최단 각)
        diff = abs(current_heading - previous_heading)
        if diff > 180:
            diff = 360 - diff

        return diff >= threshold_degrees
