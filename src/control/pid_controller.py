"""
ESS AI System - 적응형 PID 제어기
- T5 제어: 35±0.5°C (FW 출구)
- T6 제어: 43±1.0°C (E/R 온도)
- 엔진 부하별 게인 스케줄링
- 해수 온도별 보정
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np


@dataclass
class PIDGains:
    """PID 게인"""
    Kp: float  # 비례 게인
    Ki: float  # 적분 게인
    Kd: float  # 미분 게인

    def scale(self, factor: float) -> 'PIDGains':
        """게인 스케일링"""
        return PIDGains(
            Kp=self.Kp * factor,
            Ki=self.Ki * factor,
            Kd=self.Kd * factor
        )


@dataclass
class PIDState:
    """PID 상태"""
    error: float = 0.0
    integral: float = 0.0
    derivative: float = 0.0
    previous_error: float = 0.0
    previous_time: Optional[datetime] = None
    output: float = 0.0


class AdaptivePIDController:
    """
    적응형 PID 제어기
    """

    def __init__(
        self,
        setpoint: float,
        base_gains: PIDGains,
        output_min: float = 40.0,
        output_max: float = 60.0,
        integral_limit: float = 10.0,
        rate_limit: float = 2.0  # Hz/초
    ):
        self.setpoint = setpoint
        self.base_gains = base_gains

        # 출력 범위
        self.output_min = output_min
        self.output_max = output_max

        # Anti-windup
        self.integral_limit = integral_limit

        # 변화율 제한
        self.rate_limit = rate_limit
        self.previous_output: Optional[float] = None
        self.previous_output_time: Optional[datetime] = None

        # 상태
        self.state = PIDState()

        # 현재 게인 (적응형)
        self.current_gains = base_gains

    def compute(
        self,
        measured_value: float,
        dt_seconds: Optional[float] = None,
        current_time: Optional[datetime] = None
    ) -> float:
        """
        PID 제어 계산

        Args:
            measured_value: 측정값
            dt_seconds: 시간 간격 (초), None이면 자동 계산
            current_time: 현재 시간, None이면 now()

        Returns:
            제어 출력 (주파수 Hz)
        """
        if current_time is None:
            current_time = datetime.now()

        # 시간 간격 계산
        if dt_seconds is None:
            if self.state.previous_time is not None:
                dt_seconds = (current_time - self.state.previous_time).total_seconds()
            else:
                dt_seconds = 1.0  # 초기값

        dt_seconds = max(0.1, dt_seconds)  # 최소 0.1초

        # 오차 계산
        error = self.setpoint - measured_value
        self.state.error = error

        # 비례항
        P = self.current_gains.Kp * error

        # 적분항 (Anti-windup)
        self.state.integral += error * dt_seconds
        self.state.integral = np.clip(
            self.state.integral,
            -self.integral_limit,
            self.integral_limit
        )
        I = self.current_gains.Ki * self.state.integral

        # 미분항
        if self.state.previous_time is not None:
            derivative = (error - self.state.previous_error) / dt_seconds
        else:
            derivative = 0.0

        self.state.derivative = derivative
        D = self.current_gains.Kd * derivative

        # PID 출력
        pid_output = P + I + D

        # 출력 제한
        output = np.clip(pid_output, self.output_min, self.output_max)

        # 변화율 제한 (2Hz/초)
        if self.previous_output is not None and self.previous_output_time is not None:
            dt_output = (current_time - self.previous_output_time).total_seconds()
            if dt_output > 0:
                max_change = self.rate_limit * dt_output
                output_change = output - self.previous_output

                if abs(output_change) > max_change:
                    # 변화율 제한 적용
                    if output_change > 0:
                        output = self.previous_output + max_change
                    else:
                        output = self.previous_output - max_change

        # 상태 업데이트
        self.state.previous_error = error
        self.state.previous_time = current_time
        self.state.output = output

        self.previous_output = output
        self.previous_output_time = current_time

        return output

    def set_gains(self, gains: PIDGains) -> None:
        """게인 설정"""
        self.current_gains = gains

    def reset(self) -> None:
        """상태 리셋"""
        self.state = PIDState()
        self.previous_output = None
        self.previous_output_time = None

    def get_control_error(self) -> float:
        """제어 오차"""
        return abs(self.state.error)

    def is_settled(self, tolerance: float = 0.5) -> bool:
        """정착 여부 (오차가 허용범위 내)"""
        return abs(self.state.error) <= tolerance

    def get_state_info(self) -> Dict:
        """상태 정보"""
        return {
            "setpoint": self.setpoint,
            "error": self.state.error,
            "integral": self.state.integral,
            "derivative": self.state.derivative,
            "output": self.state.output,
            "gains": {
                "Kp": self.current_gains.Kp,
                "Ki": self.current_gains.Ki,
                "Kd": self.current_gains.Kd
            },
            "is_settled": self.is_settled()
        }


class AdaptiveGainScheduler:
    """
    적응형 게인 스케줄러
    - 엔진 부하별 게인 조정
    - 해수 온도별 보정
    """

    def __init__(self):
        # 기본 게인 (T5 제어용)
        self.t5_base_gains = PIDGains(Kp=1.5, Ki=0.3, Kd=0.5)

        # 기본 게인 (T6 제어용)
        self.t6_base_gains = PIDGains(Kp=2.0, Ki=0.4, Kd=0.6)

        # 엔진 부하 구간별 스케일 팩터
        self.load_scale_factors = {
            "low": 0.8,  # 0-30% 저부하 (안정성 우선)
            "medium": 1.0,  # 30-70% 중부하 (표준)
            "high": 1.2  # 70-100% 고부하 (응답성 우선)
        }

        # 해수 온도별 보정 계수
        self.seawater_temp_corrections = {
            "tropical": 1.2,  # > 28°C (적극적 냉각)
            "temperate": 1.0,  # 15-28°C (표준)
            "polar": 0.8  # < 15°C (과냉각 방지)
        }

    def get_load_category(self, engine_load_percent: float) -> str:
        """엔진 부하 구간 분류"""
        if engine_load_percent < 30.0:
            return "low"
        elif engine_load_percent < 70.0:
            return "medium"
        else:
            return "high"

    def get_seawater_category(self, seawater_temp: float) -> str:
        """해수 온도 구간 분류"""
        if seawater_temp > 28.0:
            return "tropical"
        elif seawater_temp < 15.0:
            return "polar"
        else:
            return "temperate"

    def calculate_adaptive_gains(
        self,
        base_gains: PIDGains,
        engine_load_percent: float,
        seawater_temp: float
    ) -> PIDGains:
        """
        적응형 게인 계산

        Args:
            base_gains: 기본 게인
            engine_load_percent: 엔진 부하율 (%)
            seawater_temp: 해수 온도 (°C)

        Returns:
            조정된 게인
        """
        # 엔진 부하별 스케일
        load_category = self.get_load_category(engine_load_percent)
        load_scale = self.load_scale_factors[load_category]

        # 해수 온도별 보정
        sw_category = self.get_seawater_category(seawater_temp)
        sw_correction = self.seawater_temp_corrections[sw_category]

        # 최종 스케일 팩터
        total_scale = load_scale * sw_correction

        # 게인 조정
        adjusted_gains = base_gains.scale(total_scale)

        return adjusted_gains

    def get_t5_gains(
        self,
        engine_load_percent: float,
        seawater_temp: float
    ) -> PIDGains:
        """T5 제어용 적응형 게인"""
        return self.calculate_adaptive_gains(
            self.t5_base_gains,
            engine_load_percent,
            seawater_temp
        )

    def get_t6_gains(
        self,
        engine_load_percent: float,
        seawater_temp: float
    ) -> PIDGains:
        """T6 제어용 적응형 게인"""
        return self.calculate_adaptive_gains(
            self.t6_base_gains,
            engine_load_percent,
            seawater_temp
        )


class DualPIDController:
    """
    이중 PID 제어기
    - T5 제어 (FW 출구 온도)
    - T6 제어 (E/R 온도)
    """

    def __init__(self):
        # 적응형 게인 스케줄러
        self.gain_scheduler = AdaptiveGainScheduler()

        # T5 PID (목표: 35±0.5°C)
        self.t5_controller = AdaptivePIDController(
            setpoint=35.0,
            base_gains=self.gain_scheduler.t5_base_gains,
            output_min=40.0,
            output_max=60.0
        )

        # T6 PID (목표: 43±1.0°C)
        self.t6_controller = AdaptivePIDController(
            setpoint=43.0,
            base_gains=self.gain_scheduler.t6_base_gains,
            output_min=40.0,
            output_max=60.0
        )

    def update_adaptive_gains(
        self,
        engine_load_percent: float,
        seawater_temp: float
    ) -> None:
        """적응형 게인 업데이트"""
        # T5 게인 조정
        t5_gains = self.gain_scheduler.get_t5_gains(engine_load_percent, seawater_temp)
        self.t5_controller.set_gains(t5_gains)

        # T6 게인 조정
        t6_gains = self.gain_scheduler.get_t6_gains(engine_load_percent, seawater_temp)
        self.t6_controller.set_gains(t6_gains)

    def compute_control_outputs(
        self,
        t5_measured: float,
        t6_measured: float,
        engine_load_percent: float,
        seawater_temp: float,
        dt_seconds: float = 2.0
    ) -> Dict[str, float]:
        """
        제어 출력 계산

        Returns: {
            "sw_pump_freq": SW 펌프 주파수,
            "er_fan_freq": E/R 팬 주파수
        }
        """
        # 적응형 게인 업데이트
        self.update_adaptive_gains(engine_load_percent, seawater_temp)

        # T5 제어 (SW 펌프)
        sw_pump_freq = self.t5_controller.compute(t5_measured, dt_seconds)

        # T6 제어 (E/R 팬)
        er_fan_freq = self.t6_controller.compute(t6_measured, dt_seconds)

        return {
            "sw_pump_freq": sw_pump_freq,
            "er_fan_freq": er_fan_freq,
            "t5_error": self.t5_controller.get_control_error(),
            "t6_error": self.t6_controller.get_control_error(),
            "t5_settled": self.t5_controller.is_settled(tolerance=0.5),
            "t6_settled": self.t6_controller.is_settled(tolerance=1.0)
        }

    def get_controllers_info(self) -> Dict:
        """제어기 정보"""
        return {
            "t5_controller": self.t5_controller.get_state_info(),
            "t6_controller": self.t6_controller.get_state_info()
        }

    def reset_all(self) -> None:
        """전체 리셋"""
        self.t5_controller.reset()
        self.t6_controller.reset()


def create_dual_pid_controller() -> DualPIDController:
    """이중 PID 제어기 생성"""
    return DualPIDController()
