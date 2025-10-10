"""
물리 기반 시뮬레이션 엔진
실제 선박의 열교환 및 유체역학 모델
"""

import numpy as np
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class HeatExchangerParams:
    """열교환기 파라미터"""
    effectiveness: float = 0.85  # 열교환 효율
    UA: float = 250.0  # 열전달계수 × 면적 (kW/K)
    cp_water: float = 4.186  # 물 비열 (kJ/kg·K)


@dataclass
class PumpCharacteristics:
    """펌프 특성 곡선"""
    rated_flow: float = 500.0  # 정격 유량 (m³/h)
    rated_head: float = 50.0  # 정격 양정 (m)
    rated_power: float = 132.0  # 정격 전력 (kW)

    def get_flow(self, frequency: float) -> float:
        """주파수별 유량 계산 (Affinity Laws)"""
        return self.rated_flow * (frequency / 60.0)

    def get_head(self, frequency: float) -> float:
        """주파수별 양정 계산"""
        return self.rated_head * (frequency / 60.0) ** 2

    def get_power(self, frequency: float) -> float:
        """주파수별 전력 계산"""
        return self.rated_power * (frequency / 60.0) ** 3


@dataclass
class FanCharacteristics:
    """팬 특성 곡선"""
    rated_flow: float = 300.0  # 정격 풍량 (m³/min)
    rated_pressure: float = 300.0  # 정격 정압 (Pa)
    rated_power: float = 54.3  # 정격 전력 (kW)

    def get_flow(self, frequency: float) -> float:
        """주파수별 풍량 계산"""
        return self.rated_flow * (frequency / 60.0)

    def get_pressure(self, frequency: float) -> float:
        """주파수별 정압 계산"""
        return self.rated_pressure * (frequency / 60.0) ** 2

    def get_power(self, frequency: float) -> float:
        """주파수별 전력 계산"""
        return self.rated_power * (frequency / 60.0) ** 3


class PhysicsEngine:
    """물리 기반 시뮬레이션 엔진"""

    def __init__(self):
        """초기화"""
        self.heat_exchanger = HeatExchangerParams()
        self.sw_pump = PumpCharacteristics(rated_flow=500.0, rated_power=132.0)
        self.fw_pump = PumpCharacteristics(rated_flow=400.0, rated_power=75.0)
        self.er_fan = FanCharacteristics(rated_flow=300.0, rated_power=54.3)

        # 상태 변수
        self.T1 = 25.0  # SW Inlet (해수 온도)
        self.T2 = 35.0  # No.1 Cooler SW Outlet
        self.T3 = 35.0  # No.2 Cooler SW Outlet
        self.T4 = 45.0  # FW Inlet
        self.T5 = 35.0  # FW Outlet
        self.T6 = 43.0  # E/R Temperature
        self.T7 = 40.0  # Outside Air Temperature
        self.PX1 = 2.5  # SW Discharge Pressure

        # 열용량 (단순화된 1차 시스템)
        self.thermal_mass_sw = 5000.0  # kg (SW 측 열용량)
        self.thermal_mass_fw = 3000.0  # kg (FW 측 열용량)
        self.thermal_mass_er = 50000.0  # kg (E/R 측 열용량)

        # 시간 스텝
        self.dt = 1.0  # 초

    def calculate_engine_heat_generation(self, engine_load: float) -> float:
        """
        엔진 발열량 계산

        Args:
            engine_load: 엔진 부하율 (0-100%)

        Returns:
            발열량 (kW)
        """
        # 16K급 선박 주기관: 약 60,000 kW
        # 냉각 필요 열량: 약 40% (24,000 kW)
        rated_heat = 24000.0  # kW

        # 부하율에 따른 발열량 (비선형)
        if engine_load < 30:
            heat_ratio = 0.3 + (engine_load / 30.0) * 0.2
        else:
            heat_ratio = 0.5 + ((engine_load - 30) / 70.0) * 0.5

        return rated_heat * heat_ratio

    def calculate_heat_exchanger(
        self,
        T_hot_in: float,
        T_cold_in: float,
        flow_hot: float,
        flow_cold: float
    ) -> Tuple[float, float]:
        """
        열교환기 출구 온도 계산

        Args:
            T_hot_in: 고온측 입구 온도 (°C)
            T_cold_in: 저온측 입구 온도 (°C)
            flow_hot: 고온측 유량 (m³/h)
            flow_cold: 저온측 유량 (m³/h)

        Returns:
            (고온측 출구 온도, 저온측 출구 온도)
        """
        # 질량 유량 (kg/s)
        # 물 밀도: 1000 kg/m³
        m_hot = flow_hot * 1000.0 / 3600.0  # kg/s
        m_cold = flow_cold * 1000.0 / 3600.0  # kg/s

        # 열용량 유량 (kW/K)
        C_hot = m_hot * self.heat_exchanger.cp_water
        C_cold = m_cold * self.heat_exchanger.cp_water

        C_min = min(C_hot, C_cold)
        C_max = max(C_hot, C_cold)

        # NTU-effectiveness 방법
        NTU = self.heat_exchanger.UA / C_min if C_min > 0 else 0

        # 효율 (단순 모델)
        if C_min == C_max:
            effectiveness = NTU / (1 + NTU)
        else:
            C_ratio = C_min / C_max
            effectiveness = (1 - np.exp(-NTU * (1 - C_ratio))) / (1 - C_ratio * np.exp(-NTU * (1 - C_ratio)))

        effectiveness = min(effectiveness, self.heat_exchanger.effectiveness)

        # 최대 열전달량
        Q_max = C_min * (T_hot_in - T_cold_in)

        # 실제 열전달량
        Q = effectiveness * Q_max

        # 출구 온도
        if C_hot > 0:
            T_hot_out = T_hot_in - Q / C_hot
        else:
            T_hot_out = T_hot_in

        if C_cold > 0:
            T_cold_out = T_cold_in + Q / C_cold
        else:
            T_cold_out = T_cold_in

        return T_hot_out, T_cold_out

    def calculate_er_ventilation(
        self,
        T_er: float,
        T_outside: float,
        fan_count: int,
        fan_frequency: float
    ) -> float:
        """
        E/R 환기 효과 계산

        Args:
            T_er: E/R 온도 (°C)
            T_outside: 외기 온도 (°C)
            fan_count: 팬 대수
            fan_frequency: 팬 주파수 (Hz)

        Returns:
            E/R 온도 변화율 (°C/s)
        """
        # 총 풍량
        total_flow = fan_count * self.er_fan.get_flow(fan_frequency)  # m³/min

        # 환기 열전달 계수 (단순 모델)
        # 공기 밀도: 1.2 kg/m³, 비열: 1.005 kJ/kg·K
        air_mass_flow = total_flow * 1.2 / 60.0  # kg/s
        heat_transfer = air_mass_flow * 1.005  # kW/K

        # E/R 열용량에 의한 온도 변화율
        # dT/dt = (외기 열전달 - E/R 발열) / 열용량
        cooling_effect = heat_transfer * (T_er - T_outside)  # kW

        # E/R 자체 발열 (기기, 배관 등)
        er_self_heating = 50.0  # kW (상수)

        # 온도 변화율
        dT_dt = (er_self_heating - cooling_effect) / (self.thermal_mass_er * self.heat_exchanger.cp_water)

        return dT_dt

    def calculate_sw_pressure(
        self,
        pump_count: int,
        pump_frequency: float,
        flow_resistance: float = 1.0
    ) -> float:
        """
        SW 압력 계산

        Args:
            pump_count: 펌프 대수
            pump_frequency: 펌프 주파수 (Hz)
            flow_resistance: 유량 저항 계수

        Returns:
            압력 (bar)
        """
        # 총 양정
        total_head = pump_count * self.sw_pump.get_head(pump_frequency)  # m

        # 압력 = 양정 × 중력가속도 × 밀도
        # 1 bar = 10.2 m H2O
        pressure = (total_head / flow_resistance) / 10.2  # bar

        return max(0.0, pressure)

    def step(
        self,
        engine_load: float,
        sw_pump_count: int,
        sw_pump_freq: float,
        fw_pump_count: int,
        fw_pump_freq: float,
        er_fan_count: int,
        er_fan_freq: float,
        seawater_temp: float = 25.0,
        outside_air_temp: float = 35.0
    ) -> Dict[str, float]:
        """
        1 타임스텝 시뮬레이션

        Args:
            engine_load: 엔진 부하율 (%)
            sw_pump_count: SW 펌프 대수
            sw_pump_freq: SW 펌프 주파수 (Hz)
            fw_pump_count: FW 펌프 대수
            fw_pump_freq: FW 펌프 주파수 (Hz)
            er_fan_count: E/R 팬 대수
            er_fan_freq: E/R 팬 주파수 (Hz)
            seawater_temp: 해수 온도 (°C)
            outside_air_temp: 외기 온도 (°C)

        Returns:
            센서 값 딕셔너리
        """
        # 엔진 발열량
        engine_heat = self.calculate_engine_heat_generation(engine_load)

        # SW 펌프 유량
        sw_flow = sw_pump_count * self.sw_pump.get_flow(sw_pump_freq)  # m³/h

        # FW 펌프 유량
        fw_flow = fw_pump_count * self.fw_pump.get_flow(fw_pump_freq)  # m³/h

        # SW 입구 온도 (해수 온도)
        self.T1 = seawater_temp

        # LT F.W Cooler 열교환 (FW → SW)
        # FW 입구는 엔진에서 나온 고온수
        self.T4 = self.T4 + (engine_heat / (self.thermal_mass_fw * self.heat_exchanger.cp_water)) * self.dt

        # No.1 Cooler
        T5_new, T2_new = self.calculate_heat_exchanger(
            T_hot_in=self.T4,
            T_cold_in=self.T1,
            flow_hot=fw_flow / 2,  # 2개 쿨러로 분배
            flow_cold=sw_flow / 2
        )

        # No.2 Cooler (동일 조건)
        _, T3_new = self.calculate_heat_exchanger(
            T_hot_in=self.T4,
            T_cold_in=self.T1,
            flow_hot=fw_flow / 2,
            flow_cold=sw_flow / 2
        )

        # 지수 평활 (1차 시스템 동특성)
        alpha = 0.1  # 시간 상수
        self.T2 = self.T2 * (1 - alpha) + T2_new * alpha
        self.T3 = self.T3 * (1 - alpha) + T3_new * alpha
        self.T5 = self.T5 * (1 - alpha) + T5_new * alpha

        # E/R 환기
        dT6_dt = self.calculate_er_ventilation(
            T_er=self.T6,
            T_outside=outside_air_temp,
            fan_count=er_fan_count,
            fan_frequency=er_fan_freq
        )

        self.T6 = self.T6 + dT6_dt * self.dt

        # 외기 온도
        self.T7 = outside_air_temp

        # SW 압력
        self.PX1 = self.calculate_sw_pressure(
            pump_count=sw_pump_count,
            pump_frequency=sw_pump_freq
        )

        # 센서 노이즈 추가 (정규분포, σ=0.1°C)
        noise = np.random.normal(0, 0.1, 7)

        return {
            "T1": self.T1 + noise[0],
            "T2": self.T2 + noise[1],
            "T3": self.T3 + noise[2],
            "T4": self.T4 + noise[3],
            "T5": self.T5 + noise[4],
            "T6": self.T6 + noise[5],
            "T7": self.T7 + noise[6],
            "PX1": max(0.0, self.PX1 + np.random.normal(0, 0.05)),
            "engine_load": engine_load
        }

    def reset(self):
        """상태 초기화"""
        self.T1 = 25.0
        self.T2 = 35.0
        self.T3 = 35.0
        self.T4 = 45.0
        self.T5 = 35.0
        self.T6 = 43.0
        self.T7 = 40.0
        self.PX1 = 2.5


class VoyagePattern:
    """24시간 운항 패턴 생성기"""

    def __init__(self):
        """초기화"""
        self.patterns = {
            "acceleration": {
                "duration": 30 * 60,  # 30분
                "start_load": 0,
                "end_load": 70
            },
            "steady": {
                "duration": 300 * 60,  # 300분 (5시간)
                "load": 70
            },
            "deceleration": {
                "duration": 30 * 60,  # 30분
                "start_load": 70,
                "end_load": 30
            },
            "berthed": {
                "duration": 60 * 60,  # 60분 (1시간)
                "load": 10
            }
        }

    def get_engine_load(self, time_seconds: int) -> float:
        """
        시간에 따른 엔진 부하 계산

        Args:
            time_seconds: 시뮬레이션 시작부터 경과 시간 (초)

        Returns:
            엔진 부하율 (%)
        """
        # 24시간 주기
        cycle_duration = 24 * 60 * 60  # 24시간
        t = time_seconds % cycle_duration

        # 가속 단계 (0-30분)
        if t < self.patterns["acceleration"]["duration"]:
            progress = t / self.patterns["acceleration"]["duration"]
            load = self.patterns["acceleration"]["start_load"] + \
                   (self.patterns["acceleration"]["end_load"] - self.patterns["acceleration"]["start_load"]) * progress
            return load

        t -= self.patterns["acceleration"]["duration"]

        # 정속 단계 (30-330분)
        if t < self.patterns["steady"]["duration"]:
            return self.patterns["steady"]["load"]

        t -= self.patterns["steady"]["duration"]

        # 감속 단계 (330-360분)
        if t < self.patterns["deceleration"]["duration"]:
            progress = t / self.patterns["deceleration"]["duration"]
            load = self.patterns["deceleration"]["start_load"] + \
                   (self.patterns["deceleration"]["end_load"] - self.patterns["deceleration"]["start_load"]) * progress
            return load

        t -= self.patterns["deceleration"]["duration"]

        # 정박 단계 (360-420분)
        if t < self.patterns["berthed"]["duration"]:
            return self.patterns["berthed"]["load"]

        # 나머지 시간 (420-1440분): 출항 준비 등 (반복)
        # 단순화: 정박 상태 유지
        return self.patterns["berthed"]["load"]

    def get_seawater_temp(self, time_seconds: int, base_temp: float = 25.0) -> float:
        """
        시간에 따른 해수 온도 (일일 변화)

        Args:
            time_seconds: 경과 시간 (초)
            base_temp: 기준 온도 (°C)

        Returns:
            해수 온도 (°C)
        """
        # 24시간 주기 사인파 (낮 최고, 밤 최저)
        daily_variation = 3.0 * np.sin(2 * np.pi * time_seconds / (24 * 3600))
        return base_temp + daily_variation

    def get_outside_air_temp(self, time_seconds: int, base_temp: float = 35.0) -> float:
        """
        시간에 따른 외기 온도 (일일 변화)

        Args:
            time_seconds: 경과 시간 (초)
            base_temp: 기준 온도 (°C)

        Returns:
            외기 온도 (°C)
        """
        # 24시간 주기 사인파 (낮 최고, 밤 최저)
        daily_variation = 5.0 * np.sin(2 * np.pi * time_seconds / (24 * 3600) - np.pi / 2)
        return base_temp + daily_variation
